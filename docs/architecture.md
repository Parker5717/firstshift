# FirstShift — Архитектура продукта

**Стек:** Python 3.11 · FastAPI · SQLAlchemy · SQLite → PostgreSQL · YOLOv8 · OpenCV ArUco · Vanilla JS · Tailwind CDN  
**Деплой:** Windows (start_yolo.bat) → Docker (пилот) → облако (масштаб)  
**Статусы:** ✅ готово · 🔧 изменено в этой сессии · 🔜 в плане

---

## Структура репозитория

```
firstshift/
├── backend/
│   ├── app/
│   │   ├── main.py                        ✅ FastAPI entry point, lifespan, роутеры
│   │   ├── core/
│   │   │   ├── config.py                  ✅ Settings (pydantic-settings), пути, YOLO_MODE
│   │   │   ├── ws_manager.py              ✅ WebSocket connection manager (singleton)
│   │   │   └── auth.py                    🔜 JWT encode/decode, bcrypt (шаг 1)
│   │   ├── api/
│   │   │   ├── deps.py                    ✅ get_current_user (JWT Bearer dependency)
│   │   │   ├── schemas.py                 ✅ Pydantic v2 схемы (LoginIn/Out, QuestOut…)
│   │   │   ├── auth.py                    ✅ POST /api/auth/login (никнейм без пароля)
│   │   │   │                              🔜 → добавить пароль + роль (шаг 1–2)
│   │   │   ├── users.py                   ✅ GET /api/users/me, /api/users/leaderboard
│   │   │   ├── quests.py                  ✅ GET/POST квестов (list, start, complete)
│   │   │   ├── progress.py                ✅ GET ачивок, stats, POST safety_check
│   │   │   ├── markers.py                 ✅ GET /api/markers/{id}/image (PNG ArUco)
│   │   │   ├── vision.py                  🔧 POST /api/vision/detect + quest_events
│   │   │   ├── ws_vision.py               🔧 WS /ws/vision + quest_events в ответе
│   │   │   ├── safety.py                  🔜 таблица safety_checks, офлайн-дедупликация (шаг 5)
│   │   │   ├── admin.py                   🔜 /api/hr/*, /api/mentor/* (шаг 4)
│   │   │   └── notifications.py           🔜 /api/notifications (шаг 10)
│   │   ├── cv/
│   │   │   ├── pipeline.py                ✅ Диспетчер кадра: ArUco + YOLO + PPE
│   │   │   ├── marker_detector.py         ✅ OpenCV ArUco DICT_4X4_50
│   │   │   ├── object_detector.py         ✅ YOLOv8n, COCO→quest class маппинг
│   │   │   ├── ppe_detector.py            ✅ PPE через ArUco ID 10/11 (демо)
│   │   │   │                              🔜 → реальный YOLOv8 helmet/vest (шаг 14)
│   │   │   └── utils.py                   ✅ base64→BGR, ресайз, normalize_bbox
│   │   ├── game/
│   │   │   ├── xp_engine.py               ✅ add_xp, level_from_xp, level_title
│   │   │   ├── quest_trigger.py           🔧 НОВЫЙ: auto-complete по CV-детекции
│   │   │   ├── achievements.py            ✅ check_and_unlock, record_scan_event
│   │   │   ├── report_generator.py        🔜 HTML→PDF через WeasyPrint (шаг 9)
│   │   │   └── content/
│   │   │       ├── quests.yaml            ✅ 6 квестов (discovery/knowledge/speed_run)
│   │   │       └── achievements.yaml      ✅ 5 ачивок
│   │   └── db/
│   │       ├── models.py                  ✅ User, Quest, UserQuestProgress,
│   │       │                                  Achievement, UserAchievement, ScanEvent
│   │       │                              🔜 → добавить role, password_hash,
│   │       │                                  mentor_id, safety_checks, notifications (шаги 1–5)
│   │       ├── database.py                ✅ SQLAlchemy engine, SessionLocal, Base, get_db
│   │       └── seed.py                   ✅ Сидер YAML → таблицы quests/achievements
│   ├── models/                            🔜 веса YOLO (.pt, в .gitignore)
│   │   ├── ppe_yolov8.pt
│   │   └── equipment_yolov8.pt
│   ├── tests/
│   │   ├── test_step1_skeleton.py         ✅ базовый smoke-test
│   │   └── test_step2_content_api.py      ✅ тест контент-API
│   └── requirements.txt                   ✅
│
├── frontend/
│   ├── index.html                         ✅ Лендинг + форма логина
│   ├── app.html                           ✅ Главная SPA: камера + AR + HUD
│   ├── safety.html                        ✅ Safety Check (фронтальная камера)
│   ├── markers.html                       ✅ ArUco маркеры для печати
│   ├── encyclopedia.html                  ✅ Энциклопедия объектов
│   ├── admin.html                         🔜 HR-панель (шаг 6)
│   ├── manifest.json                      🔜 PWA (шаг 13)
│   └── static/
│       ├── css/
│       │   ├── main.css                   ✅ Глобальные стили, CSS-переменные
│       │   └── hud.css                    ✅ Стили AR-оверлея, HUD, попапы
│       ├── js/
│       │   ├── api.js                     ✅ fetch-обёртка, токен, все API-вызовы
│       │   ├── camera.js                  ✅ getUserMedia, переключение камер
│       │   ├── ar-overlay.js              ✅ Canvas: bounding boxes, AR-рендер
│       │   ├── vision-client.js           🔧 WS/REST кадры + обработка quest_events
│       │   ├── quest-engine.js            ✅ Состояние активного квеста, модалка
│       │   ├── xp-bar.js                  ✅ HUD профиль, +XP попап, level-up конфетти
│       │   ├── achievements.js            ✅ Загрузка и отображение ачивок
│       │   ├── speedrun.js                ✅ Таймер и UI speed_run квеста
│       │   ├── quiz.js                    ✅ Модалка с вопросом для knowledge квестов
│       │   ├── mascot.js                  ✅ Маскот Алекс: фразы, энциклопедия объектов
│       │   ├── onboarding.js              ✅ Онбординг-флоу для новых сотрудников
│       │   ├── admin.js                   🔜 HR-панель логика (шаг 6)
│       │   └── app.js                     🔧 Убран YOLO badge
│       └── assets/
│           ├── icons/                     🔜 иконки PWA
│           └── sounds/                    ✅ level-up, scan звуки
│
├── docs/
│   ├── architecture.md                    ← этот файл
│   └── demo-script.md                    ✅
│
├── .env.example                           🔜
├── .gitignore                             🔜
├── docker-compose.yml                     🔜 (шаг 11)
├── start_yolo.bat                         🔧 упрощён, убрана плашка
└── README.md                             ✅

```

---

## Схема базы данных

### Текущая (SQLite, хакатон)

```
users                    quests                   user_quest_progress
─────────────────        ──────────────────────   ───────────────────────
id PK                    id PK                    id PK
username UNIQUE          slug UNIQUE              user_id FK→users
display_name             title                    quest_id FK→quests
level                    description              status (locked/available/
total_xp                 type                            active/completed/failed)
current_streak           target_class (YOLO)      attempts
created_at               target_marker_id (ArUco) started_at
last_active_at           xp_reward                completed_at
                         prerequisite_slug
achievements             story_chapter
────────────             difficulty
id PK                    params_json
slug UNIQUE
title                    scan_events
description              ───────────────
icon                     id PK
condition_json           user_id FK→users
xp_bonus                 timestamp
                         detected_class
user_achievements        marker_id
─────────────────        confidence
id PK                    quest_id FK→quests
user_id FK→users
achievement_id FK
unlocked_at
```

### Целевая (PostgreSQL, пилот)

```
Добавляются поля и таблицы:

users           + password_hash, role, mentor_id FK→users, tenant_id
quests          + tenant_id (NULL = глобальный шаблон)
scan_events     + tenant_id
achievements    + tenant_id

safety_checks   [НОВАЯ — шаг 5]
────────────────────────────────
id PK
user_id FK→users
tenant_id
timestamp
passed BOOL
helmet BOOL
vest BOOL
goggles BOOL
missing_items_json
client_id UUID UNIQUE(user_id, client_id)   ← дедупликация офлайн
synced_at

notifications   [НОВАЯ — шаг 10]
────────────────────────────────
id PK
recipient_id FK→users
type (level_up / safety_fail / quest_done)
ref_id
payload_json
read_at
created_at

tenants         [НОВАЯ — шаг 12]
────────────────────────────────
id PK
name
slug UNIQUE
created_at
settings_json
```

---

## Ключевые потоки данных

### CV-квест (работает после фикса)
```
телефон (задняя камера)
  → JPEG base64 каждую секунду
  → WS /ws/vision  (или REST /api/vision/detect как fallback)
      → cv/pipeline.py
          → marker_detector  →  список ArUco {marker_id, bbox}
          → object_detector  →  список YOLO {detected_class, confidence, bbox}
      → game/quest_trigger.py
          → берём все ACTIVE квесты пользователя (один JOIN)
          → сравниваем target_marker_id / target_class
          → совпадение → complete_quest → add_xp → unlock_next → check_achievements
      → ответ: {markers, objects, ppe, quest_events}
  ← фронт: AROverlay рисует боксы
           vision-client: если quest_events → XPBar.showXPGain + QuestEngine.load()
                          если нет → показывает кнопку «✅ Засчитать» (ручной fallback)
```

### Safety Check + офлайн (шаги 5, 7, 8)
```
ОНЛАЙН:
  телефон (фронтальная камера)
    → ppe_detector → {helmet, vest, goggles, all_ok}
    → POST /api/safety/check → safety_checks таблица

ОФЛАЙН:
  результат → IndexedDB {client_id: UUID, ...}
  Service Worker: Background Sync → при появлении сети → POST /api/safety/check
  сервер: UNIQUE(user_id, client_id) → если дубль → 200 OK, не создаём запись

HR:
  GET /api/hr/safety/today → кто прошёл / нет
```

### Роли и доступ (шаги 1–4)
```
JWT payload: { sub: user_id, role: "employee"|"mentor"|"hr"|"admin",
               tenant_id: 1, exp: ... }

employee  → /api/me/*, /api/quests/*, /api/vision/*
mentor    → + /api/mentor/employees (только своих подопечных)
hr        → + /api/hr/* (все сотрудники предприятия)
admin     → всё + /api/admin/* (системное)

Dependency require_role("hr", "admin"):
  → декодирует JWT → проверяет role → 403 если не подходит
```

---

## План реализации

| Шаг | Что делаем | Файлы | Срок |
|-----|-----------|-------|------|
| ✅ 0 | quests.yaml заполнен | content/quests.yaml | готово |
| 🔜 1 | JWT с паролем + bcrypt | db/models.py, api/auth.py, core/auth.py | шаг 1 |
| 🔜 2 | Поле role + require_role | db/models.py, api/deps.py | шаг 2 |
| 🔜 3 | mentor_id + /api/mentor/ | db/models.py, api/admin.py | шаг 3 |
| 🔜 4 | /api/hr/ эндпоинты | api/admin.py | шаг 4 |
| 🔜 5 | Таблица safety_checks | db/models.py, api/safety.py | шаг 5 |
| 🔜 6 | Admin-панель UI | admin.html, static/js/admin.js | шаг 6 |
| 🔜 7 | Service Worker + IndexedDB | frontend/sw.js | шаг 7 |
| 🔜 8 | Офлайн-дедупликация | api/safety.py | шаг 8 |
| 🔜 9 | PDF-отчёт (WeasyPrint) | game/report_generator.py | шаг 9 |
| 🔜 10 | Уведомления наставнику | db/models.py, api/notifications.py | шаг 10 |
| 🔜 11 | PostgreSQL + Alembic | db/database.py, alembic/ | шаг 11 |
| 🔜 12 | tenant_id мультитенант | все модели | шаг 12 |
| 🔜 13 | PWA манифест | manifest.json, sw.js | шаг 13 |
| 🔜 14 | Fine-tune YOLO | cv/object_detector.py, models/ | шаг 14 |
| 🔜 15 | Аналитика HR | api/admin.py, static/js/admin.js | шаг 15 |

---

## Решения принятые сознательно

| Решение | Почему |
|---------|--------|
| SQLite → пилот, PostgreSQL → продакшн | Zero-config для разработки, реальная БД для клиента |
| Alembic с шага 11 | До пилота схема меняется ежедневно — drop-and-recreate быстрее |
| Admin UI в том же FastAPI приложении (/admin) | Меньше CORS, один деплой, проще для первого клиента |
| WeasyPrint для PDF | HTML+CSS → PDF, можно нормально стилизовать |
| mentor_id в users (не отдельная таблица) | У одного employee один наставник — простая схема достаточна |
| Vanilla JS без фреймворков | Телефоны на заводе могут быть слабые, минимум JS-бандла |
| ArUco как демо-fallback для PPE | Стабильная работа на демо без реального снаряжения |
