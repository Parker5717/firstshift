"""Добавляет /stats эндпоинт в progress.py если его нет."""
import sys
sys.path.insert(0, '.')

path = 'app/api/progress.py'
content = open(path, encoding='utf-8').read()

if 'def get_stats' in content:
    print('stats уже есть!')
else:
    stats = '''

@router.get("/stats", summary="Сводная статистика пользователя")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quests_completed = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == current_user.id,
            UserQuestProgress.status == QuestStatus.COMPLETED.value,
        )
        .count()
    )
    scans_total = (
        db.query(ScanEvent)
        .filter(ScanEvent.user_id == current_user.id)
        .count()
    )
    achievements_unlocked = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == current_user.id)
        .count()
    )
    return {
        "username": current_user.username,
        "level": current_user.level,
        "total_xp": current_user.total_xp,
        "quests_completed": quests_completed,
        "scans_total": scans_total,
        "achievements_unlocked": achievements_unlocked,
        "current_streak": current_user.current_streak,
    }
'''
    open(path, 'a', encoding='utf-8').write(stats)
    print('stats добавлен!')

from app.api.progress import router
print('Роуты:', [r.path for r in router.routes])
