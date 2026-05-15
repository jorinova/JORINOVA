from django.urls import path
from . import views

app_name = 'laboratory'

urlpatterns = [
    path('', views.index, name='index'),
    path('serology/', views.serology_index, name='serology'),
    path('hematology/', views.dept_index, {'dept': 'hematology'}, name='hematology'),
    path('chemistry/', views.dept_index, {'dept': 'chemistry'}, name='chemistry'),
    path('microbiology/', views.dept_index, {'dept': 'microbiology'}, name='microbiology'),
    path('coagulation/', views.dept_index, {'dept': 'coagulation'}, name='coagulation'),
    path('new-request/', views.new_request, name='new_request'),
    path('labels/', views.label_center, name='labels'),
    path('labels/<str:lab_id>/', views.label_center, name='labels_for'),
]
