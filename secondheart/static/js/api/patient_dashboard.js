let currentPatientId = null;
let allDoctors = []; // Храним врачей локально для быстрой фильтрации

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/me/')
        .then(r => r.json())
        .then(data => {
            currentPatientId = data.profile_id;
            loadAppointments();
            loadSpecialties();
            loadDoctors();
        });
});

// --- ЛОГИКА ВКЛАДКИ "МОИ ЗАПИСИ" ---

function loadAppointments() {
    const tbody = document.getElementById('appointmentsTableBody');
    const loader = document.getElementById('appointmentsLoader');
    const noMsg = document.getElementById('noAppointmentsMsg');

    tbody.innerHTML = '';
    loader.classList.remove('d-none');
    noMsg.classList.add('d-none');

    // В реальном проекте лучше фильтровать на бэкенде, но здесь фильтруем на клиенте
    fetch(`/api/appointments/`)
        .then(r => r.json())
        .then(appointments => {
            loader.classList.add('d-none');

            // Фильтруем записи только текущего пациента
            const myAppointments = appointments.filter(app => app.patient === currentPatientId);

            if (myAppointments.length === 0) {
                noMsg.classList.remove('d-none');
                return;
            }

            myAppointments.forEach(app => {
                const row = document.createElement('tr');

                // Определяем цвет статуса
                let statusBadge = '<span class="badge bg-secondary">Неизвестно</span>';
                if (app.status === 'scheduled') statusBadge = '<span class="badge bg-primary">Запланировано</span>';
                else if (app.status === 'completed') statusBadge = '<span class="badge bg-success">Завершено</span>';
                else if (app.status === 'cancelled') statusBadge = '<span class="badge bg-danger">Отменено</span>';

                // Кнопка отмены (только если статус scheduled)
                let actionBtn = '';
                if (app.status === 'scheduled') {
                    actionBtn = `<button class="btn btn-outline-danger btn-sm" onclick="cancelAppointment(${app.id})">Отменить</button>`;
                }

                row.innerHTML = `
                    <td>
                        <div class="fw-bold">${app.slot_details.date}</div>
                        <small class="text-muted">${app.slot_details.start_time} - ${app.slot_details.end_time}</small>
                    </td>
                    <td>${app.slot_details.doctor_name}</td>
                    <td>${app.slot_details.doctor_specialty}</td>
                    <td>${statusBadge}</td>
                    <td>${actionBtn}</td>
                `;
                tbody.appendChild(row);
            });
        });
}

async function cancelAppointment(id) {
    if (!confirm('Вы уверены, что хотите отменить запись?')) return;

    const response = await fetch(`/api/appointments/${id}/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });

    if (response.ok) {
        loadAppointments(); // Перезагрузить таблицу
        // Если мы сейчас на вкладке бронирования и выбран этот врач, обновим слоты
        const activeDoc = document.querySelector('.list-group-item.active');
        if (activeDoc) activeDoc.click();
    } else {
        alert('Ошибка при отмене записи.');
    }
}

// --- ЛОГИКА ВКЛАДКИ "ЗАПИСЬ" ---

function loadSpecialties() {
    fetch('/api/specialties/')
        .then(r => r.json())
        .then(specialties => {
            const select = document.getElementById('specialtyFilter');
            specialties.forEach(spec => {
                const opt = document.createElement('option');
                opt.value = spec.id;
                opt.innerText = spec.name;
                select.appendChild(opt);
            });
        });
}

function loadDoctors() {
    fetch('/api/doctors/')
        .then(r => r.json())
        .then(doctors => {
            allDoctors = doctors;
            renderDoctors(doctors);
        });
}

function renderDoctors(doctors) {
    const list = document.getElementById('doctorsList');
    list.innerHTML = '';

    if (doctors.length === 0) {
        list.innerHTML = '<div class="text-muted p-2">Врачей не найдено.</div>';
        return;
    }

    doctors.forEach(doc => {
        const item = document.createElement('a');
        item.className = 'list-group-item list-group-item-action';
        item.style.cursor = 'pointer';
        item.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${doc.user.first_name} ${doc.user.last_name}</h6>
            </div>
            <small class="text-muted">${doc.specialty_details.name}</small>
        `;
        item.onclick = (e) => {
            // Подсветка активного
            document.querySelectorAll('#doctorsList .list-group-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            loadSlots(doc.id, doc.user.last_name);
        };
        list.appendChild(item);
    });
}

function filterDoctors() {
    const specId = document.getElementById('specialtyFilter').value;
    if (specId === 'all') {
        renderDoctors(allDoctors);
    } else {
        const filtered = allDoctors.filter(d => d.specialty_details.id == specId);
        renderDoctors(filtered);
    }
}

function loadSlots(doctorId, doctorName) {
    const container = document.getElementById('slotsContainer');
    container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div></div>';

    fetch(`/api/slots/?doctor=${doctorId}&status=free`)
        .then(r => r.json())
        .then(slots => {
            container.innerHTML = '';
            if (slots.length === 0) {
                container.innerHTML = `<div class="alert alert-warning">У доктора ${doctorName} нет свободных слотов.</div>`;
                return;
            }

            // Группировка слотов по дате
            const slotsByDate = {};
            slots.forEach(slot => {
                if (!slotsByDate[slot.date]) slotsByDate[slot.date] = [];
                slotsByDate[slot.date].push(slot);
            });

            // Отрисовка по группам
            for (const [date, daySlots] of Object.entries(slotsByDate)) {
                const dateGroup = document.createElement('div');
                dateGroup.className = 'mb-4';
                dateGroup.innerHTML = `<h6 class="border-bottom pb-2 mb-3 text-primary">${formatDate(date)}</h6>`;

                const row = document.createElement('div');
                row.className = 'd-flex flex-wrap gap-2';

                daySlots.sort((a, b) => a.start_time.localeCompare(b.start_time)); // Сортировка по времени

                daySlots.forEach(slot => {
                    const btn = document.createElement('button');
                    btn.className = 'btn btn-outline-success btn-sm';
                    btn.style.minWidth = '80px';
                    // Обрезаем секунды из времени (HH:MM:SS -> HH:MM)
                    const timeShort = slot.start_time.substring(0, 5);
                    btn.innerText = timeShort;
                    btn.onclick = () => bookSlot(slot.id, date, timeShort);
                    row.appendChild(btn);
                });

                dateGroup.appendChild(row);
                container.appendChild(dateGroup);
            }
        });
}

async function bookSlot(slotId, date, time) {
    if (!confirm(`Записаться на ${date} в ${time}?`)) return;

    const response = await fetch('/api/appointments/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            patient: currentPatientId,
            slot: slotId
        })
    });

    if (response.ok) {
        alert('Успешно! Вы записаны.');
        // Переключаемся на вкладку "Мои записи"
        const tabTrigger = new bootstrap.Tab(document.querySelector('#appointments-tab'));
        tabTrigger.show();
        loadAppointments(); // Обновляем список записей

        // Очищаем выбор слотов
        document.getElementById('slotsContainer').innerHTML = '<div class="alert alert-success">Запись создана. Выберите врача для новой записи.</div>';
        document.querySelectorAll('#doctorsList .list-group-item').forEach(el => el.classList.remove('active'));
    } else {
        alert('Ошибка записи. Возможно, слот уже занят.');
        // Обновляем слоты текущего врача, чтобы убрать занятый
        const activeDoc = document.querySelector('.list-group-item.active');
        if (activeDoc) activeDoc.click();
    }
}

// Вспомогательная функция для красивой даты
function formatDate(dateString) {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('ru-RU', options);
}