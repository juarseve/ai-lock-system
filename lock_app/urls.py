from django.urls import path
from . import views

app_name = 'lock_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/authenticate/', views.authenticate_user, name='authenticate_user'),
    path('api/register/', views.register_user, name='register_user'),
]
