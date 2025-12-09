from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime, timedelta, date, time
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import render, redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, status
from django_filters.rest_framework import DjangoFilterBackend
from .models import Doctor, Patient, Specialty, Appointment, ScheduleSlot, WorkingHours
from . import serializers
from django.db import transaction

import logging

from .serializers import WorkingHoursSerializer

logger = logging.getLogger(__name__)


class WorkingHoursViewSet(viewsets.ModelViewSet):
    queryset = WorkingHours.objects.all()
    serializer_class = serializers.WorkingHoursSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Доктор видит только свои настройки графика
        return WorkingHours.objects.filter(doctor__user=self.request.user)

    def perform_create(self, serializer: WorkingHoursSerializer):
        # При создании автоматически привязываем к текущему доктору
        doctor = self.request.user.doctor_profile
        serializer.save(doctor=doctor)


class DoctorSlotViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ScheduleSlotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Доктор видит свои слоты
        return ScheduleSlot.objects.filter(doctor__user=self.request.user)

    # Запрещаем ручное создание слотов через стандартный POST (опционально)
    # def create(self, request, *args, **kwargs):
    #     return Response({"detail": "Use 'generate_schedule' action."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=['post'])
    def generate_schedule(self, request):
        """
        Генерирует слоты на 2 недели.
        1. Удаляет будущие СВОБОДНЫЕ слоты (чтобы обновить график).
        2. Оставляет ЗАНЯТЫЕ слоты (чтобы не отменить записи).
        3. Создает новые слоты согласно WorkingHours, пропуская занятое время.
        """
        doctor = request.user.doctor_profile
        days_ahead = 14
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        # Используем транзакцию, чтобы генерация была атомарной (всё или ничего)
        with transaction.atomic():
            # 1. Удаляем только СВОБОДНЫЕ слоты в этом диапазоне.
            # Это позволяет врачу изменить график работы и перегенерировать слоты,
            # не теряя при этом уже записанных пациентов.
            ScheduleSlot.objects.filter(
                doctor=doctor,
                date__range=[today, end_date],
                status='free'
            ).delete()

            created_count = 0

            for i in range(days_ahead + 1):  # +1 чтобы захватить последний день
                current_date = today + timedelta(days=i)
                weekday = current_date.isoweekday()  # 1=Mon, 7=Sun

                # Получаем ВСЕ интервалы работы на этот день (например, до обеда и после)
                working_hours_list = WorkingHours.objects.filter(
                    doctor=doctor,
                    day_of_week=weekday
                )

                if not working_hours_list.exists():
                    continue

                for wh in working_hours_list:
                    start_dt = datetime.combine(current_date, wh.start_time)
                    end_dt = datetime.combine(current_date, wh.end_time)

                    current_slot_start = start_dt

                    while current_slot_start + timedelta(minutes=doctor.appointment_duration) <= end_dt:
                        slot_end = current_slot_start + timedelta(minutes=doctor.appointment_duration)

                        # Проверяем, нет ли уже слота на это время (например, статус 'booked' или 'completed')
                        # Мы удалили только 'free', так что если слот остался - значит он занят.
                        exists = ScheduleSlot.objects.filter(
                            doctor=doctor,
                            date=current_date,
                            start_time=current_slot_start.time()
                        ).exists()

                        if not exists:
                            ScheduleSlot.objects.create(
                                doctor=doctor,
                                date=current_date,
                                start_time=current_slot_start.time(),
                                end_time=slot_end.time(),
                                status='free'
                            )
                            created_count += 1

                        current_slot_start = slot_end

        return Response({
            "message": "Расписание обновлено.",
            "created_slots": created_count,
            "period": f"{today} - {end_date}"
        })

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        queryset = self.get_queryset()

        free_slots = queryset.filter(status="free")

        deleted_count, _ = free_slots.delete()

        return Response(
            {"message": f"Удалено {deleted_count} свободных слотов."},
            status=status.HTTP_204_NO_CONTENT
        )


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = serializers.DoctorSerializer


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = serializers.PatientSerializer


class SpecialtyViewSet(viewsets.ModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = serializers.SpecialtySerializer


class ScheduleSlotViewSet(viewsets.ModelViewSet):
    queryset = ScheduleSlot.objects.all()
    serializer_class = serializers.ScheduleSlotSerializer
    # Добавляем фильтрацию, чтобы клиент мог запросить только свободные слоты
    # Пример запроса: /api/slots/?doctor=1&status=free&date=2023-10-27
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['doctor', 'date', 'status']


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Если это пациент - возвращаем только его записи
        if hasattr(user, 'patient_profile'):
            return Appointment.objects.filter(patient=user.patient_profile)
        # Если это врач - возвращаем записи, где он является врачом
        elif hasattr(user, 'doctor_profile'):
            return Appointment.objects.filter(slot__doctor=user.doctor_profile)
        # Иначе (админ) возвращаем всё
        return Appointment.objects.all()

    def perform_destroy(self, instance):
        slot = instance.slot
        slot.status = 'free'
        slot.save()
        instance.delete()

    def perform_update(self, serializer):
        appointment = serializer.save()  # Обновили Appointment
        slot = appointment.slot

        # Синхронизация статусов
        if appointment.status == 'completed':
            slot.status = 'completed'
        elif appointment.status == "scheduled":
            slot.status = 'booked'
        else:
            slot.status = 'free'

        slot.save()


# --- API для получения инфо о текущем пользователе ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_info(request):
    user = request.user
    data = {
        'id': user.id,
        'username': user.username,
        'role': None,
        'profile_id': None
    }

    # Проверяем, кто это: врач или пациент
    if hasattr(user, 'patient_profile'):
        data['role'] = 'patient'
        data['profile_id'] = user.patient_profile.id
    elif hasattr(user, 'doctor_profile'):
        data['role'] = 'doctor'
        data['profile_id'] = user.doctor_profile.id

    return JsonResponse(data)


# --- Представления для HTML страниц ---

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    # Просто отдаем шаблон, логика регистрации будет через JS и API
    return render(request, 'register.html')


@login_required(login_url='/login/')
def dashboard_view(request):
    user = request.user
    if hasattr(user, 'patient_profile'):
        return render(request, 'patient_dashboard.html')
    elif hasattr(user, 'doctor_profile'):
        return render(request, 'doctor_dashboard.html')
    else:
        # Если пользователь есть, но профиля нет (например, админ)
        return render(request, 'index.html', {'message': 'У вас нет профиля врача или пациента'})
