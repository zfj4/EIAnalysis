from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_json, name='upload_json'),
    path('analysis/tables-form/', views.tables_form, name='tables_form'),
    path('analysis/run/', views.run_analysis, name='run_analysis'),
]
