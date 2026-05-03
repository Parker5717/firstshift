# FirstShift — AR-платформа адаптации сотрудников

**FirstShift** превращает онбординг на производстве в AR-квест прямо в браузере смартфона. Новый сотрудник сканирует оборудование камерой — система распознаёт объекты через YOLOv8 и ArUco, засчитывает квесты, начисляет XP и формирует цифровой журнал инструктажей для HR.

> Пилот: предприятие, Сахалин, август 2026.

---

## Возможности

- **AR-квесты** — сотрудник наводит камеру на оборудование, YOLOv8 и ArUco-маркеры автоматически засчитывают выполнение
- **Safety Check** — ежедневная проверка СИЗ через фронтальную камеру с фиксацией в цифровом журнале
- **Геймификация** — XP, уровни, ачивки, лидерборд; маскот Алекс с голосовыми подсказками
- **HR-панель** — прогресс каждого сотрудника, статус Safety Check, PDF-отчёт одной кнопкой
- **Офлайн-режим** — Service Worker + IndexedDB, синхронизация при появлении сети
- **Без установки** — PWA, открывается в браузере смартфона по ссылке

---

## Стек

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2.0 |
| CV | YOLOv8n (ultralytics) · OpenCV ArUco |
| База данных | SQLite (dev) → PostgreSQL (prod) |
| Frontend | Vanilla JS · Tailwind CDN · Canvas API |
| Transport | REST API + WebSocket |
| Auth | JWT (python-jose) · bcrypt |

---

## Быстрый старт (Windows)

### 1. Клонировать и создать окружение

```cmd
git clone https://github.com/Parker5717/firstshift.git
cd firstshift\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настроить переменные окружения

```cmd
copy .env.example .env
```

Открой `.env` и задай `SECRET_KEY` — любая случайная строка.

### 3. Запустить сервер

```cmd
cd ..
start_yolo.bat
```

Сервер запустится на `http://localhost:8000`.  
Для доступа с телефона используй ngrok (см. `ngrok.bat`).

---

## Структура проекта

```
firstshift/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── core/                # config, ws_manager, auth
│   │   ├── api/                 # роутеры (auth, quests, vision, hr…)
│   │   ├── cv/                  # CV pipeline: ArUco + YOLOv8 + PPE
│   │   ├── game/                # XP engine, quest trigger, achievements
│   │   └── db/                  # ORM models, database, seeder
│   └── requirements.txt
├── frontend/
│   ├── app.html                 # Главная SPA (камера + AR + HUD)
│   ├── safety.html              # Safety Check
│   ├── admin.html               # HR-панель
│   └── static/js/               # camera, vision-client, quest-engine…
├── docs/
│   └── architecture.md          # Полная архитектура продукта
├── start_yolo.bat
└── README.md
```

Подробная архитектура: [`docs/architecture.md`](docs/architecture.md)

---

## Роли пользователей

| Роль | Доступ |
|------|--------|
| `employee` | Камера, квесты, Safety Check, профиль |
| `mentor` | + прогресс своих подопечных |
| `hr` | + все сотрудники, Safety Check журнал, PDF-отчёты |
| `admin` | Системное управление |

---

## Roadmap

- [x] ArUco маркеры + YOLOv8 детекция
- [x] Геймификация (XP, уровни, ачивки)
- [x] Safety Check через фронтальную камеру
- [x] WebSocket стрим кадров
- [x] Автозасчитывание квестов через CV
- [ ] JWT auth с ролями (в разработке)
- [ ] HR Admin-панель
- [ ] Офлайн Safety Check (Service Worker)
- [ ] PDF-отчёты
- [ ] PostgreSQL + мультитенантность
- [ ] Fine-tune YOLOv8 под оборудование клиента

---

## Автор

Parker — основатель FirstShift, Южно-Сахалинск  
Проект участвует в программе [ITMO Stars](https://stars.itmo.ru/) (дедлайн: 18 июля 2026)
