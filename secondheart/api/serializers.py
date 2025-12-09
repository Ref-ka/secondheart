from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    Patient, Doctor, Specialty, Appointment, WorkingHours, ScheduleSlot
)
from datetime import datetime, timedelta


# --- Базовые сериализаторы ---

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "password"]
        extra_kwargs = {'password': {'write_only': True}}


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = "__all__"


class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = "__all__"

        read_only_fields = ['doctor']

    def validate(self, data):
        """
        Проверяем, что интервалы времени до и после обеда не пересекаются
        """
        user = self.context['request'].user
        doctor = getattr(user, 'doctor_profile', None)

        day_of_week = data.get('day_of_week')
        before_lunch = data.get('before_lunch')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([doctor, day_of_week, before_lunch, start_time, end_time]):
            return data

        # Проверяем базовую корректность времени
        if start_time >= end_time:
            raise serializers.ValidationError({
                "error": "Время окончания должно быть позже времени начала"
            })

        today = datetime.now().date()
        dt1 = datetime.combine(today, start_time)
        dt2 = datetime.combine(today, end_time)

        time_difference = dt2 - dt1
        if (time_difference.seconds % 3600) // 60 < doctor.appointment_duration:
            raise serializers.ValidationError({
                "error": "Разница между окончанием и началом промежутка приема должна быть не меньше, "
                         "чем длительность одного приема."
            })

        # Проверяем пересечение с другим интервалом в тот же день
        # Ищем другой интервал у этого врача в тот же день (до или после обеда)
        other_intervals = WorkingHours.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week
        ).exclude(id=self.instance.id if self.instance else None)

        for interval in other_intervals:
            # Проверяем пересечение временных интервалов
            if start_time <= interval.end_time and end_time >= interval.start_time:
                time_period = "до перерыва" if interval.before_lunch else "после перерыва"
                raise serializers.ValidationError({
                    "error": f"Это время пересекается с интервалом {interval.start_time}-{interval.end_time} ({time_period})"
                })

        return data


# --- Врачи ---

class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    specialty_details = SpecialtySerializer(source='specialty', read_only=True)  # Для отображения
    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.all(),
                                                   write_only=True)  # Для записи по ID

    class Meta:
        model = Doctor
        fields = ["id", "user", "specialty", "specialty_details", "appointment_duration", "is_active"]

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        # Создаем пользователя с хешированием пароля
        user = User.objects.create_user(**user_data)
        doctor = Doctor.objects.create(user=user, **validated_data)
        return doctor


# --- Пациенты ---

class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Patient
        fields = "__all__"

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        user = User.objects.create_user(**user_data)
        patient = Patient.objects.create(user=user, **validated_data)
        return patient


class PatientShortSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name')

    class Meta:
        model = Patient
        fields = ['id', 'full_name', 'phone_number']


# --- Слоты расписания ---

class ScheduleSlotSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    doctor_specialty = serializers.CharField(source='doctor.specialty.name', read_only=True)
    patient_info = serializers.SerializerMethodField()
    appointment_id = serializers.SerializerMethodField() # <--- Добавляем это поле

    class Meta:
        model = ScheduleSlot
        fields = "__all__"

    def get_patient_info(self, obj):
        if hasattr(obj, 'appointment'):
            return PatientShortSerializer(obj.appointment.patient).data
        return None

    # Добавляем метод для получения ID записи
    def get_appointment_id(self, obj):
        if hasattr(obj, 'appointment'):
            return obj.appointment.id
        return None


# --- Запись на прием (Самое важное) ---

class AppointmentSerializer(serializers.ModelSerializer):
    # Эти поля только для чтения (чтобы красиво видеть ответ сервера)
    patient_details = PatientSerializer(source='patient', read_only=True)
    slot_details = ScheduleSlotSerializer(source='slot', read_only=True)

    # Эти поля для записи (принимаем ID)
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all())
    slot = serializers.PrimaryKeyRelatedField(queryset=ScheduleSlot.objects.filter(status='free'))

    class Meta:
        model = Appointment
        fields = ["id", "patient", "slot", "status", "patient_details", "slot_details", "created_at"]

    def create(self, validated_data):
        # Логика: при создании записи, слот должен стать занятым
        slot = validated_data['slot']
        slot.status = 'booked'
        slot.save()

        return super().create(validated_data)
