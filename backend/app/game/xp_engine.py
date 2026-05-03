"""
XP и система уровней CASPER AR Assistant.

Формула: level = floor(sqrt(total_xp / 50)) + 1

Пороги:
  Уровень 1:  0    XP  — Стажёр
  Уровень 2:  50   XP  — Помощник оператора
  Уровень 3:  200  XP  — Молодой оператор
  Уровень 4:  450  XP  — Техник
  Уровень 5:  800  XP  — Молодой специалист
  Уровень 6:  1250 XP  — Специалист
  ...

Квадратный корень даёт плавное замедление роста — первые уровни берутся быстро
(чтобы новичок сразу чувствовал прогресс), потом темп снижается.
"""

import math

# Названия уровней — видны в профиле и на лидерборде
LEVEL_TITLES: dict[int, str] = {
    1: "Стажёр",
    2: "Помощник оператора",
    3: "Молодой оператор",
    4: "Техник",
    5: "Молодой специалист",
    6: "Специалист",
    7: "Старший специалист",
    8: "Мастер цеха",
}
DEFAULT_TITLE = "Мастер цеха"  # для уровней выше 8


def level_from_xp(total_xp: int) -> int:
    """Текущий уровень по накопленному XP. Минимум 1."""
    if total_xp <= 0:
        return 1
    return int(math.floor(math.sqrt(total_xp / 50))) + 1


def xp_for_level(level: int) -> int:
    """Минимальное количество XP для достижения уровня `level`."""
    if level <= 1:
        return 0
    return 50 * (level - 1) ** 2


def xp_to_next_level(total_xp: int) -> int:
    """Сколько XP не хватает до следующего уровня."""
    current = level_from_xp(total_xp)
    needed = xp_for_level(current + 1)
    return max(0, needed - total_xp)


def level_progress_pct(total_xp: int) -> float:
    """Прогресс внутри текущего уровня в процентах (0.0 – 1.0)."""
    current = level_from_xp(total_xp)
    current_floor = xp_for_level(current)
    next_floor = xp_for_level(current + 1)
    span = next_floor - current_floor
    if span <= 0:
        return 1.0
    return min(1.0, (total_xp - current_floor) / span)


def level_title(level: int) -> str:
    """Название уровня для отображения."""
    return LEVEL_TITLES.get(level, DEFAULT_TITLE)


def add_xp(current_xp: int, amount: int) -> tuple[int, int, bool]:
    """
    Начислить XP и вернуть (new_total_xp, new_level, leveled_up).

    Использование:
        new_xp, new_level, leveled_up = add_xp(user.total_xp, quest.xp_reward)
        if leveled_up:
            ... показать анимацию level-up ...
    """
    old_level = level_from_xp(current_xp)
    new_total = current_xp + amount
    new_level = level_from_xp(new_total)
    return new_total, new_level, new_level > old_level
