from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_json, name='upload_json'),
    path('analysis/tables-form/', views.tables_form, name='tables_form'),
    path('analysis/linear-form/', views.linear_form, name='linear_form'),
    path('analysis/linear-run/', views.run_linear, name='run_linear'),
    path('analysis/run/', views.run_analysis, name='run_analysis'),
    path('analysis/logistic-form/', views.logistic_form, name='logistic_form'),
    path('analysis/logistic-run/', views.run_logistic, name='run_logistic'),
    path('analysis/logbinomial-form/', views.logbinomial_form, name='logbinomial_form'),
    path('analysis/logbinomial-run/', views.run_logbinomial, name='run_logbinomial'),
]
