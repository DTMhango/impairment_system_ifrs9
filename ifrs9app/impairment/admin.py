from django.contrib import admin
from .models import HistoricalCustomerLoanData, Project, PDCalculationResult, EADLGDCalculationResult, ECLCalculationResult, CurrentLoanBook

# Register your models here.
@admin.register(HistoricalCustomerLoanData)
class HistoricalCustomerLoanDataAdmin(admin.ModelAdmin):
    list_display = ('project', 'file_name', 'file_upload_date', 'is_valid')
    exclude = ['uploaded_file']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'report_date', 'created_by', 'status']

@admin.register(PDCalculationResult)
class PDCalculationResultAdmin(admin.ModelAdmin):
    list_display = ('project', 'base_transition_matrix', 'stage_1_cumulative', 'stage_2_cumulative', 'stage_1_marginal', 'stage_2_marginal', 'cures', 'recoveries')


@admin.register(EADLGDCalculationResult)
class EADLGDCalculationResultAdmin(admin.ModelAdmin):
    list_display = ['project', 'account_no', 'stage', 'amortization_schedule', 'lgd_schedule', 'created_at']


@admin.register(CurrentLoanBook)
class CurrentLoanBookAdmin(admin.ModelAdmin):
    list_display = ['project', 'file_name', 'file_upload_date', 'is_valid']
    exclude = ['uploaded_file']


admin.site.register(ECLCalculationResult)