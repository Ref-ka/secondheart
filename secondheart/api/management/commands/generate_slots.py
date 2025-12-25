from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime, date
from secondheart.api.models import Doctor, WorkingHours, ScheduleSlot


class Command(BaseCommand):
    help = 'Генерирует слоты расписания на следующую неделю'

    def handle(self, *args, **options):
        # Начинаем генерировать с завтрашнего дня (или с следующего понедельника)
        today = timezone.now().date()
        start_date = today + timedelta(days=1)
        days_to_generate = 7  # Генерируем на неделю вперед

        doctors = Doctor.objects.filter(is_active=True)

        for doctor in doctors:
            self.stdout.write(f"Обработка доктора: {doctor}")

            for i in range(days_to_generate):
                current_date = start_date + timedelta(days=i)
                # isoweekday возвращает 1 для понедельника, 7 для воскресенья
                day_of_week = current_date.isoweekday()

                # Ищем рабочие часы врача на этот день недели
                try:
                    work_hours = WorkingHours.objects.get(doctor=doctor, day_of_week=day_of_week)
                except WorkingHours.DoesNotExist:
                    # Если врач не работает в этот день, пропускаем
                    continue

                # Логика нарезки времени
                start_dt = datetime.combine(current_date, work_hours.start_time)
                end_dt = datetime.combine(current_date, work_hours.end_time)

                # Текущий слот начинается с начала рабочего дня
                current_slot_start = start_dt

                while current_slot_start < end_dt:
                    current_slot_end = current_slot_start + timedelta(minutes=doctor.appointment_duration)

                    # Если конец слота вылезает за конец рабочего дня, прерываем
                    if current_slot_end > end_dt:
                        break

                    # Проверяем, не создан ли уже такой слот (чтобы не дублировать при повторном запуске)
                    if not ScheduleSlot.objects.filter(
                            doctor=doctor,
                            date=current_date,
                            start_time=current_slot_start.time()
                    ).exists():
                        ScheduleSlot.objects.create(
                            doctor=doctor,
                            date=current_date,
                            start_time=current_slot_start.time(),
                            end_time=current_slot_end.time(),
                            status='free'  # По умолчанию свободен
                        )

                    # Переходим к следующему слоту
                    current_slot_start = current_slot_end

        self.stdout.write(self.style.SUCCESS('Слоты успешно созданы!'))
