from django.urls import path
from . import views

app_name = 'lock_app'

urlpatterns = [
    # 3 Vistas Principales del Frontend
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('unlock/', views.unlock_view, name='unlock'),

    # Endpoints API
    path('api/serial-status/', views.serial_status_api, name='serial_status'),
    path('api/register/', views.register_user, name='register_user'),
    path('api/authenticate/', views.authenticate_user, name='authenticate_user'),
]
