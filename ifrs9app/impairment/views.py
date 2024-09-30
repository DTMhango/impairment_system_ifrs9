import django
django.setup()

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404
from .forms import SignUpForm, ProjectForm
from .models import Project, HistoricalCustomerLoanData, PDCalculationResult, CurrentLoanBook, EADLGDCalculationResult, ECLCalculationResult
import pandas as pd
from .data_validation import data_prep, add_dates, staging_map
from .matrix_functions import base_matrices, absorbing_state, extract_pds, cure_rate, multi_to_single, plot_rates_px
from pandarallel import pandarallel
from .ecl_module import LossGivenDefault, create_ead_instance, ECL_Calc, sum_of_ecl, plot_ecl_bar, plot_ecl_pie, plot_bar_loan_type, plot_pie_loan_type, merge_original_balance
from .helpers import run_calculations_for_project, remove_loan_duplicates
from functools import partial
from django.db import transaction



MAT_MULT = 301
MAT_SIZE = 3 # Note: Debating whether to create widget for selections between 3 and 4 or leave hardcoded as 3??? Kaya mweh

staging_map_partial = partial(staging_map, matrix_size = MAT_SIZE)

# @login_required
def home(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            projects_list = Project.objects.all().order_by('report_date')
            paginator = Paginator(projects_list, 10)  # Paginate with 10 projects per page

            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            return render(request, 'impairment/home.html', {'page_obj': page_obj})
        else:
            projects_list = Project.objects.filter(created_by=request.user).order_by('report_date')
            paginator = Paginator(projects_list, 10)  # Paginate with 10 projects per page

            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            return render(request, 'impairment/home.html', {'page_obj': page_obj})
    else:
        return redirect('sign_in')
    

def sign_in(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "You have successfully signed in. Welcome back!", extra_tags='sign_in')
            return redirect('home')
        else:
            messages.error(request, "Invalid Username or Password! Please try again.", extra_tags='error_on_sign_in')
            return render(request, 'impairment/dashboard.html')
    else:
        return render(request, 'impairment/sign-in.html')   
    

def sign_out(request):
    logout(request)
    messages.success(request, "You have been signed out!", extra_tags='sign_out')
    return redirect('sign_in')


def sign_up(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your account has been created successfully! You can now sign in.")
            return redirect('sign_in')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SignUpForm()
    return render(request, 'impairment/sign-up.html', {'form': form})


@login_required
def data_source(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/data_source.html', context)



@login_required
def upload_historical_loan_data(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if request.method == 'POST':
        if 'historical_loan_data' not in request.FILES:
            messages.error(request, 'No file uploaded. Please upload a CSV file.')
            return render(request, 'impairment/data_source.html', {'project': project})
        
        uploaded_file = request.FILES['historical_loan_data']

        if not uploaded_file.name.endswith('.csv'):
            messages.info(request, 'Please Upload a CSV file Only!')
            return render(request, 'impairment/data_source.html')

        try:            
            pd_data = pd.read_csv(uploaded_file)
            
            valuation_date = project.report_date
            
            pd_df, period = data_prep(pd_data, MAT_SIZE, valuation_date)
            matrices = absorbing_state(base_matrices(pd_df), period=period)
            cr_rr = cure_rate(pd_df, MAT_MULT, period=period)

            base_mat = multi_to_single(matrices)
            cures = add_dates(cr_rr[0], valuation_date)
            recoveries = add_dates(cr_rr[1], valuation_date)

            final_output = extract_pds(matrices, MAT_SIZE, MAT_MULT)
            stage_1_marg = add_dates(final_output[0], valuation_date)
            stage_2_marg = add_dates(final_output[1], valuation_date)
            stage_1_cml = add_dates(final_output[2], valuation_date)
            stage_2_cml = add_dates(final_output[3], valuation_date)

            del pd_df, cr_rr
            
            # Check if results already exist for this project
            run_calculations_for_project(project.id, {
                'base_transition_matrix': base_mat.to_dict(orient='records'),
                'stage_1_cumulative': stage_1_cml.to_dict(orient='records'),
                'stage_2_cumulative': stage_2_cml.to_dict(orient='records'),
                'stage_1_marginal': stage_1_marg.to_dict(orient='records'),
                'stage_2_marginal': stage_2_marg.to_dict(orient='records'),
                'cures': cures.to_dict(orient='records'),
                'recoveries': recoveries.to_dict(orient='records'),
            })

            # Ensure the 'date' column is converted properly
            for col in pd_data.columns:
                if 'date' in col:
                    pd_data[col] = pd_data[col].astype(str)

            saved_data_file = pd_data.fillna(0.0).to_dict(orient='records')
            # Save historical data
            historical_data = HistoricalCustomerLoanData.objects.update_or_create(
                uploaded_file=saved_data_file,
                file_name=uploaded_file.name,
                project=project,
                is_valid=True,
            )

            messages.success(request, 'File processing completed successfully.')

        except Exception as e:
            messages.error(request, f"Error reading file: {e}")
            return render(request, 'impairment/data_source.html', {'project': project})


        return redirect('data_source', pk=pk)

    else:
        return render(request, 'impairment/data_source.html', {'project': project})


@login_required
def upload_current_loan_book(request, pk):
    pandarallel.initialize()
    project = get_object_or_404(Project, pk=pk)
    
    if request.method == 'POST':
        uploaded_file = request.FILES['current_loan_book']

        if not uploaded_file.name.endswith('.csv'):
            messages.info(request, 'Please Upload a CSV file Only!')
            return render(request, 'impairment/data_source.html')
        
 
        try:
            uploaded_file = request.FILES['current_loan_book']
            initial_loanbook = pd.read_csv(uploaded_file)

            # Step 1: Remove loan duplicates

            initial_loanbook['staging'] = initial_loanbook['days_past_due'].map(staging_map_partial)  # Map stages
            loanbook = remove_loan_duplicates(initial_loanbook)  # Ensure unique account numbers
            # Step 2: Fetch the related PDCalculationResult (cures and recoveries)
            pd_calculation = PDCalculationResult.objects.get(project=project)
            cures = pd.DataFrame(pd_calculation.cures)
            recoveries = pd.DataFrame(pd_calculation.recoveries)

            def convert_cols(dataframe):
                for col in dataframe.columns:
                    if 'date' not in col.lower():
                        dataframe[col] = dataframe[col].astype(float)
                return dataframe
            
            cures = convert_cols(cures)
            recoveries = convert_cols(recoveries)

            # Step 3: Create EAD instances using parallel_apply
            EAD = pd.DataFrame({"EAD OBJECTS": loanbook.parallel_apply(create_ead_instance, axis=1)})

            # Step 4: Create LGD instances using parallel_apply
            def create_lgd_instance(row):
                return LossGivenDefault(
                    exposure=row['EAD OBJECTS'],
                    cure_rate=cures,
                    recovery_rate=recoveries
                )

            LGD = pd.DataFrame({"LGD OBJECTS": EAD.parallel_apply(create_lgd_instance, axis=1)})

            # Step 5: Extract the amortization schedules and LGD schedules in bulk
            def convert_dates_to_str(schedule):
                # Loop through all columns to ensure flexibility in handling date column names
                for col in schedule.columns:
                    if 'Expected Date' in col:  # More flexible name matching
                        schedule[col] = schedule[col].astype(str)
                return schedule.to_dict(orient='records')

            # Convert amortization schedules
            EAD['amortization_schedule'] = EAD['EAD OBJECTS'].apply(lambda x: convert_dates_to_str(x.amortization))

            # Convert LGD schedules
            LGD['lgd_schedule'] = LGD['LGD OBJECTS'].apply(lambda x: convert_dates_to_str(x.lgd_schedule))


            # Step 6: Combine account numbers from the original loanbook
            results = loanbook[['account_no', 'staging']].copy()
            results['amortization_schedule'] = EAD['amortization_schedule']
            results['lgd_schedule'] = LGD['lgd_schedule']

            # Step 7: Use transaction to save the results in bulk for performance
            with transaction.atomic():
                for _, row in results.iterrows():
                    EADLGDCalculationResult.objects.update_or_create(
                        account_no=row['account_no'],
                        stage=row['staging'],
                        project=project,
                        defaults={
                            'amortization_schedule': row['amortization_schedule'],
                            'lgd_schedule': row['lgd_schedule']
                        }
                    )

            for col in loanbook.columns:
                if 'date' in col.lower():
                    loanbook[col] = loanbook[col].astype(str)

            saved_loanbook = loanbook.fillna(0.0).to_dict(orient='records')

            uploaded_loan_book = CurrentLoanBook.objects.update_or_create(
                project=project,
                file_name = uploaded_file.name,
                uploaded_file = saved_loanbook,                
            )

            messages.success(request, f"EAD and LGD calculations completed for project: {project.name}")

        except PDCalculationResult.DoesNotExist:
            raise ValidationError(f"No PD Calculation Result exists for project: {project.name}")
            
        except Exception as e:
            messages.error(request, f"Error reading file: {e}")
            return render(request, 'impairment/data_source.html', {'project': project})

        return redirect('data_source', pk=pk)

    else:
        return render(request, 'impairment/data_source.html', {'project': project})
    

@login_required
def current_loan_book(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/current_loan_book.html', context)

@login_required
def cumulative_probability_of_default(request, pk):
    project = get_object_or_404(Project, pk=pk)

    try:
        pd_results = get_object_or_404(PDCalculationResult, project=project)
    except Http404:
        # If no PDCalculationResult exists, render the impairment/blank.html view
        return render(request, 'impairment/blank.html', {'project': project})

    stage_1_cumulative = pd.DataFrame(pd_results.stage_1_cumulative)
    stage_2_cumulative = pd_results.stage_2_cumulative

    s2_cml_paginator = Paginator(stage_2_cumulative, 15)
    page_number = request.GET.get('page')
    s2_cml_page_obj = s2_cml_paginator.get_page(page_number)

    context = {
        'project': project,
        'stage_1_cumulative': stage_1_cumulative,
        's2_cml_page_obj': s2_cml_page_obj,
    }
    return render(request, 'impairment/cumulative_pd.html', context)


@login_required
def marginal_probability_of_default(request, pk):
    project = get_object_or_404(Project, pk=pk)

    try:
        pd_results = get_object_or_404(PDCalculationResult, project=project)
    except Http404:
        # If no PDCalculationResult exists, render the impairment/blank.html view
        return render(request, 'impairment/blank.html', {'project': project})

    stage_1_marginal = pd.DataFrame(pd_results.stage_1_marginal)
    stage_2_marginal = pd_results.stage_2_marginal

    s2_marg_paginator = Paginator(stage_2_marginal, 15)
    page_number = request.GET.get('page')
    s2_marg_page_obj = s2_marg_paginator.get_page(page_number)    

    context = {
        'project': project,
        'stage_1_marginal': stage_1_marginal,
        's2_marg_page_obj': s2_marg_page_obj,
    }
    return render(request, 'impairment/marginal_pd.html', context)


@login_required
def cures_and_recoveries(request, pk):
    project = get_object_or_404(Project, pk=pk)

    try:
        pd_results = get_object_or_404(PDCalculationResult, project=project)
    except Http404:
        # If no PDCalculationResult exists, render the impairment/blank.html view
        return render(request, 'impairment/blank.html', {'project': project})

    cures = pd_results.cures
    recoveries = pd_results.recoveries

    cures_paginator = Paginator(cures, 12)
    cures_page_number = request.GET.get('page')
    cures_page_obj = cures_paginator.get_page(cures_page_number)   

    recoveries_paginator = Paginator(recoveries, 12)
    recoveries_page_number = request.GET.get('page')
    recoveries_page_obj = recoveries_paginator.get_page(recoveries_page_number)   

    context = {
        'project': project,
        'cures_page_obj': cures_page_obj,
        'recoveries_page_obj': recoveries_page_obj,
    }
    return render(request, 'impairment/cures_and_recoveries.html', context)


@login_required
def ead_analysis(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/ead_analysis.html', context)


@login_required
def lgd_analysis(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/lgd_analysis.html', context)


@login_required
def fli(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/fli.html', context)


@login_required
def dashboard(request, pk):
    project = get_object_or_404(Project, pk=pk)

    context = {
        'project': project,
    }
    return render(request, 'impairment/dashboard.html', context)


@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)  
            project.created_by = request.user  
            project.last_modified_by = request.user  
            project.save()  
            messages.success(request, "Project Created Successfully!")
            return HttpResponseRedirect(reverse('home'))
    else:
        form = ProjectForm()
    return render(request, 'impairment/create_project.html', {'form': form})


# @login_required
# def project_detail(request, pk):
#     project = get_object_or_404(Project, pk=pk)

#     context = {
#         'project': project,
#     }
#     return render(request, 'impairment/data_source.html', context)
