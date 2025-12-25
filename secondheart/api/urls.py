from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'doctors', views.DoctorViewSet)
router.register(r'patients', views.PatientViewSet)
router.register(r'specialties', views.SpecialtyViewSet)
router.register(r'slots', views.ScheduleSlotViewSet)
router.register(r'appointments', views.AppointmentViewSet, basename="Appointments")
router.register(r'working_hours', views.WorkingHoursViewSet)
router.register(r'doctorslots', views.DoctorSlotViewSet, basename="DoctorSlots")

urlpatterns = [
    path('', views.login_view, name="index"),
    path('login/', views.login_view, name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('register/', views.register_view, name="register"),
    path('dashboard/', views.dashboard_view, name="dashboard"),

    path('api/', include(router.urls)),
    path('api/me/', views.current_user_info, name='current_user_info'),
    path('api/change-password/', views.change_password, name='change_password'),
]
