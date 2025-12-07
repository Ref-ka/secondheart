from django.contrib import admin
from .models import (
    Patient,
    Doctor,
    Specialty,
    WorkingHours,
    ScheduleSlot,
    Appointment,
)

admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(Specialty)
admin.site.register(WorkingHours)
admin.site.register(ScheduleSlot)
admin.site.register(Appointment)
