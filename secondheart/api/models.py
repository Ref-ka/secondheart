from django.db import models
from django.contrib.auth.models import User


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="patient_profile")
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=20)
    emergency_contact = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name()


class Specialty(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor_profile")
    is_active = models.BooleanField(default=True)
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    appointment_duration = models.PositiveIntegerField(default=30, help_text="Длительность приема в минутах")

    def __str__(self):
        return f"Доктор {self.user.get_full_name()}, специальность: {self.specialty}"


class WorkingHours(models.Model):
    doctor = models.ForeignKey("Doctor", on_delete=models.CASCADE, related_name='working_hours')

    day_of_week = models.PositiveSmallIntegerField(
        choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'),
                 (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')]
    )

    before_lunch = models.BooleanField(default=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('day_of_week', 'before_lunch', 'doctor')


class ScheduleSlot(models.Model):
    STATUS_CHOICES = [
        ('free', 'Free'),
        ('booked', 'Booked'),
        ('completed', 'Completed'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='free')


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    slot = models.OneToOneField(ScheduleSlot, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
