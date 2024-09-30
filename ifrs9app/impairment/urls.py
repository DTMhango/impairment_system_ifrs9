from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sign-in/', views.sign_in, name='sign_in'),
    path('sign-out/', views.sign_out, name='sign_out'),
    path('sign-up/', views.sign_up, name='sign_up'),
    path('create-project/', views.create_project, name='create_project'),
    path('project/<int:pk>/data-source/', views.data_source, name='data_source'),
    path('project/<int:pk>/upload_historical/', views.upload_historical_loan_data, name='upload_historical_loan_data'),
    path('project/<int:pk>/upload_current/', views.upload_current_loan_book, name='upload_current_loan_book'),
    path('project/<int:pk>/dashboard/', views.dashboard, name='dashboard'),
    path('project/<int:pk>/cumulative-probability-of-default/', views.cumulative_probability_of_default, name='cumulative_probability_of_default'),
    path('project/<int:pk>/marginal-probability-of-default/', views.marginal_probability_of_default, name='marginal_probability_of_default'),
    path('project/<int:pk>/probability-of-cure-or-recovery/', views.cures_and_recoveries, name='probability_cures_and_recoveries'),
    path('project/<int:pk>/current-loan-book/', views.current_loan_book, name='current_loan_book'),
    path('project/<int:pk>/lgd-analysis/', views.lgd_analysis, name='lgd_analysis'),
    path('project/<int:pk>/ead-analysis/', views.ead_analysis, name='ead_analysis'),
    path('project/<int:pk>/forward-looking-information/', views.fli, name='forward_looking_information'),
    
]