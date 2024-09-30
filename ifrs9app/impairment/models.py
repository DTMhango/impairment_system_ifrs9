from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, max_length=100, help_text="Add a description to your project")
    report_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="creator")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    last_modified_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="modifier")
    last_modified_on = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Locked', 'Locked')], default='Active')
    is_archived = models.BooleanField(default=False)

    def save(self):
        if self.is_archived:
            self.status = 'Locked'
        else: 
            self.status = 'Active'
        return super(Project, self).save()

    def __str__(self):
        return self.name


class PDCalculationResult(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='pd_calculations')
    base_transition_matrix = models.JSONField(null=True, blank=True)
    stage_1_cumulative = models.JSONField(null=True, blank=True)
    stage_2_cumulative = models.JSONField(null=True, blank=True)
    stage_1_marginal = models.JSONField(null=True, blank=True)
    stage_2_marginal = models.JSONField(null=True, blank=True)
    cures = models.JSONField(null=True,blank=True)
    recoveries = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Calculation results for {self.project.name} on {self.created_at}"

class EADLGDCalculationResult(models.Model):
    account_no = models.CharField(max_length=50, unique=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='ead_lgd_calculations')
    stage = models.CharField(max_length=10, null=True)
    amortization_schedule = models.JSONField(null=True, blank=True)
    lgd_schedule = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"EAD and LGD results for account {self.account_no} in project {self.project.name}"

class ECLCalculationResult(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='ecl_calculations')
    pd_data = models.ForeignKey(PDCalculationResult, on_delete=models.CASCADE)
    ead_lgd_data = models.ForeignKey(EADLGDCalculationResult, on_delete=models.CASCADE)
    ecl_results = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"ECL results for {self.project.name}"


class HistoricalCustomerLoanData(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pd_data')
    uploaded_file = models.JSONField(null=True, blank=True)
    file_name = models.CharField(max_length=100, null=True, blank=True)
    file_upload_date = models.DateTimeField(auto_now_add=True, null=True)
    is_valid = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Step 1: Mark all previous datasets for the same project as invalid when a new one is created
        if self.is_valid:
            HistoricalCustomerLoanData.objects.filter(project=self.project, is_valid=True).update(is_valid=False)

        # Step 2: Call the original save method to store the new file
        super(HistoricalCustomerLoanData, self).save(*args, **kwargs)

        # Step 3: Delete the oldest files if there are more than 10 datasets for this project
        data_files = HistoricalCustomerLoanData.objects.filter(project=self.project).order_by('file_upload_date')

        # If there are more than 10 data files, delete the oldest ones
        if data_files.count() > 10:
            excess_files = data_files[:-10]  # Get the oldest files beyond the 10 most recent
            for file_to_delete in excess_files:
                file_to_delete.delete()  # This deletes the object and its associated file if applicable

    def __str__(self) -> str:
        return f"{self.file_name} Uploaded on {self.file_upload_date}"

    
class CurrentLoanBook(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='current_loan_data')
    uploaded_file = models.JSONField(null=True, blank=True)
    file_name = models.CharField(max_length=100, null=True, blank=True)
    file_upload_date = models.DateTimeField(auto_now_add=True, null=True)
    is_valid = models.BooleanField(default=True)


    def __str__(self) -> str:
        return f"{self.file_name} Uploaded on {self.file_upload_date}"

