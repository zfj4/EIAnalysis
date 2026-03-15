from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_json, name='upload_json'),
    path('analysis/tables-form/', views.tables_form, name='tables_form'),
    path('analysis/means-form/', views.means_form, name='means_form'),
    path('analysis/means-run/', views.run_means, name='run_means'),
    path('analysis/linear-form/', views.linear_form, name='linear_form'),
    path('analysis/linear-run/', views.run_linear, name='run_linear'),
    path('analysis/run/', views.run_analysis, name='run_analysis'),
    path('analysis/logistic-form/', views.logistic_form, name='logistic_form'),
    path('analysis/logistic-run/', views.run_logistic, name='run_logistic'),
    path('analysis/logbinomial-form/', views.logbinomial_form, name='logbinomial_form'),
    path('analysis/logbinomial-run/', views.run_logbinomial, name='run_logbinomial'),
    path('analysis/frequencies-form/', views.frequencies_form, name='frequencies_form'),
    path('analysis/frequencies-run/', views.run_frequencies, name='run_frequencies'),
    path('management/filter-form/', views.filter_form, name='filter_form'),
    path('management/filter-options/', views.filter_options, name='filter_options'),
    path('management/filter-value-input/', views.filter_value_input, name='filter_value_input'),
    path('management/filter-run/', views.run_filter, name='run_filter'),
    path('management/filter-clear/', views.clear_filters, name='clear_filters'),
    path('management/filter-condition-row/', views.filter_condition_row, name='filter_condition_row'),
]
