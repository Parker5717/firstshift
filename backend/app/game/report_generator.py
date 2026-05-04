"""
PDF генератор отчётов по сотруднику.

Использует fpdf2 — чистый Python, не требует системных зависимостей.
Установка: pip install fpdf2

Генерирует:
- Шапка: имя, роль, уровень, XP
- Прогресс-бар онбординга
- Таблица квестов с датами выполнения
- Safety Check история за период
- Ачивки
"""

import json
from datetime import datetime, timezone
from io import BytesIO

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.db.models import (
    Achievement, QuestStatus, SafetyCheck,
    User, UserAchievement, UserQuestProgress,
)
from app.game.xp_engine import level_title


# Цвета FirstShift
COLOR_ACCENT  = (0,   170, 255)   # --accent
COLOR_SUCCESS = (0,   255, 136)   # --success
COLOR_DANGER  = (255, 51,  85)    # --danger
COLOR_DARK    = (7,   11,  20)    # --bg-dark
COLOR_GRAY    = (100, 120, 140)   # text secondary
COLOR_WHITE   = (255, 255, 255)
COLOR_LIGHT   = (230, 235, 245)   # light bg for rows

QUEST_STATUS_LABELS = {
    "completed": "✓ Выполнен",
    "active":    "▶ Активен",
    "available": "○ Доступен",
    "locked":    "🔒 Заблокирован",
    "failed":    "✗ Провален",
}


class FirstShiftPDF(FPDF):
    """FPDF с кастомными хелперами для стиля FirstShift."""

    def header(self):
        # Синяя полоска сверху
        self.set_fill_color(*COLOR_ACCENT)
        self.rect(0, 0, 210, 4, 'F')

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*COLOR_GRAY)
        self.cell(0, 10, f"FirstShift · Отчёт сгенерирован {datetime.now().strftime('%d.%m.%Y %H:%M')} · Стр. {self.page_no()}", align="C")

    def section_title(self, text: str):
        """Заголовок раздела."""
        self.ln(4)
        self.set_fill_color(*COLOR_ACCENT)
        self.set_text_color(*COLOR_WHITE)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 8, f"  {text}", fill=True, ln=True)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def kv_row(self, key: str, value: str, fill: bool = False):
        """Строка ключ-значение."""
        if fill:
            self.set_fill_color(*COLOR_LIGHT)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*COLOR_GRAY)
        self.cell(50, 6, key, fill=fill)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, value, fill=fill, ln=True)

    def progress_bar(self, pct: float, label: str = ""):
        """Горизонтальный прогресс-бар."""
        x, y = self.get_x(), self.get_y()
        bar_w = 120
        bar_h = 5

        # Фон
        self.set_fill_color(200, 210, 220)
        self.rect(x, y, bar_w, bar_h, 'F')

        # Заполнение
        fill_w = bar_w * min(pct, 1.0)
        r, g, b = (0, 200, 100) if pct >= 1.0 else COLOR_ACCENT
        self.set_fill_color(r, g, b)
        if fill_w > 0:
            self.rect(x, y, fill_w, bar_h, 'F')

        # Процент рядом
        self.set_xy(x + bar_w + 4, y - 1)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*COLOR_GRAY)
        self.cell(30, 7, f"{int(pct * 100)}%  {label}")
        self.ln(bar_h + 2)
        self.set_text_color(0, 0, 0)


def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    # Обеспечиваем naive datetime для strftime
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y")


def _fmt_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y %H:%M")


def generate_employee_report(
    db: Session,
    user: User,
    period_days: int = 7,
) -> bytes:
    """
    Сгенерировать PDF-отчёт по сотруднику.

    Args:
        db:          сессия БД
        user:        объект пользователя
        period_days: период Safety Check (7 = неделя, 30 = месяц)

    Returns:
        PDF как bytes
    """
    pdf = FirstShiftPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Шапка ────────────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*COLOR_DARK)
    name = user.display_name or user.username
    pdf.cell(0, 12, name, ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COLOR_GRAY)
    role_labels = {"employee": "Сотрудник", "mentor": "Наставник", "hr": "HR", "admin": "Администратор"}
    pdf.cell(0, 6, f"@{user.username}  ·  {role_labels.get(user.role, user.role)}  ·  Создан: {_fmt_date(user.created_at)}", ln=True)
    pdf.ln(4)

    # Горизонтальный разделитель
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # ── Общий прогресс ───────────────────────────────────────────────────────
    pdf.section_title("📊 Профиль и прогресс")

    pdf.kv_row("Уровень:", f"{user.level}  —  {level_title(user.level)}", fill=True)
    pdf.kv_row("Всего XP:",    str(user.total_xp))
    pdf.kv_row("Последняя активность:", _fmt_datetime(user.last_active_at), fill=True)

    # Квесты
    total_q = db.query(UserQuestProgress).filter(UserQuestProgress.user_id == user.id).count()
    done_q  = db.query(UserQuestProgress).filter(
        UserQuestProgress.user_id == user.id,
        UserQuestProgress.status == QuestStatus.COMPLETED.value,
    ).count()
    pct = done_q / total_q if total_q else 0

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*COLOR_GRAY)
    pdf.cell(50, 6, "Прогресс онбординга:")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)
    pdf.set_x(60)
    pdf.progress_bar(pct, f"{done_q}/{total_q} квестов")

    # ── Квесты ───────────────────────────────────────────────────────────────
    pdf.section_title("🎯 Квесты")

    progress_list = (
        db.query(UserQuestProgress)
        .filter(UserQuestProgress.user_id == user.id)
        .join(UserQuestProgress.quest)
        .all()
    )

    if not progress_list:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(0, 6, "Нет данных", ln=True)
    else:
        # Заголовок таблицы
        pdf.set_fill_color(*COLOR_DARK)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(75, 7, "Квест", fill=True, border=0)
        pdf.cell(35, 7, "Статус", fill=True, border=0)
        pdf.cell(30, 7, "XP", fill=True, border=0)
        pdf.cell(45, 7, "Выполнен", fill=True, border=0, ln=True)
        pdf.set_text_color(0, 0, 0)

        for i, p in enumerate(progress_list):
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(*COLOR_LIGHT)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(75, 6, p.quest.title[:40], fill=fill)
            pdf.cell(35, 6, QUEST_STATUS_LABELS.get(p.status, p.status), fill=fill)
            pdf.cell(30, 6, f"+{p.quest.xp_reward} XP" if p.status == "completed" else "—", fill=fill)
            pdf.cell(45, 6, _fmt_date(p.completed_at), fill=fill, ln=True)

    # ── Safety Check ─────────────────────────────────────────────────────────
    pdf.section_title(f"🛡️ Safety Check — последние {period_days} дней")

    from datetime import timedelta
    period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
    checks = (
        db.query(SafetyCheck)
        .filter(
            SafetyCheck.user_id == user.id,
            SafetyCheck.timestamp >= period_start,
        )
        .order_by(SafetyCheck.timestamp.desc())
        .all()
    )

    if not checks:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(0, 6, f"Нет данных за последние {period_days} дней", ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        # Сводка
        passed = sum(1 for c in checks if c.passed)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, f"Всего проверок: {len(checks)}   Успешных: {passed}   Нарушений: {len(checks) - passed}", ln=True)
        pdf.ln(2)

        # Таблица
        pdf.set_fill_color(*COLOR_DARK)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(60, 7, "Дата и время", fill=True)
        pdf.cell(30, 7, "Результат", fill=True)
        pdf.cell(30, 7, "Каска", fill=True)
        pdf.cell(30, 7, "Жилет", fill=True)
        pdf.cell(35, 7, "Отсутствует", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)

        for i, c in enumerate(checks):
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(*COLOR_LIGHT)
            missing = json.loads(c.missing_items or "[]")
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(60, 6, _fmt_datetime(c.timestamp), fill=fill)

            # Статус с цветом
            if c.passed:
                pdf.set_text_color(0, 150, 80)
                pdf.cell(30, 6, "✓ Пройдена", fill=fill)
            else:
                pdf.set_text_color(200, 50, 50)
                pdf.cell(30, 6, "✗ Нарушение", fill=fill)
            pdf.set_text_color(0, 0, 0)

            pdf.cell(30, 6, "Да" if c.helmet else "Нет", fill=fill)
            pdf.cell(30, 6, "Да" if c.vest   else "Нет", fill=fill)
            pdf.cell(35, 6, ", ".join(missing) if missing else "—", fill=fill, ln=True)

    # ── Ачивки ────────────────────────────────────────────────────────────────
    pdf.section_title("🏆 Достижения")

    ach_list = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == user.id)
        .join(UserAchievement.achievement)
        .order_by(UserAchievement.unlocked_at.desc())
        .all()
    )

    total_ach = db.query(Achievement).count()

    if not ach_list:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(0, 6, "Нет разблокированных достижений", ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(0, 6, f"Разблокировано: {len(ach_list)} из {total_ach}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        for i, ua in enumerate(ach_list):
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(*COLOR_LIGHT)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(100, 6, ua.achievement.title, fill=fill)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*COLOR_GRAY)
            pdf.cell(50, 6, f"+{ua.achievement.xp_bonus} XP", fill=fill)
            pdf.cell(0, 6, _fmt_date(ua.unlocked_at), fill=fill, ln=True)
            pdf.set_text_color(0, 0, 0)

    # ── Итоговая строка ───────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*COLOR_GRAY)
    pdf.cell(0, 6,
        f"Отчёт сформирован для: {name} (@{user.username})  ·  "
        f"Период Safety Check: {period_days} дней  ·  "
        f"FirstShift v0.2",
        ln=True
    )

    # Возвращаем bytes
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
