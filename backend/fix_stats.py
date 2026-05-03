"""Добавляет декоратор @router.get к функции get_stats."""
path = 'app/api/progress.py'
content = open(path, encoding='utf-8').read()

# Заменяем функцию без декоратора на с декоратором
old = 'def get_stats(\n    db: Session = Depends(get_db),'
new = '@router.get("/stats", summary="Stats")\ndef get_stats(\n    db: Session = Depends(get_db),'

if '@router.get("/stats"' in content:
    print('Декоратор уже есть!')
elif old in content:
    content = content.replace(old, new)
    open(path, 'w', encoding='utf-8').write(content)
    print('Декоратор добавлен!')
else:
    print('Функция не найдена, ищу...')
    # Попробуем найти по другому
    import re
    match = re.search(r'(\ndef get_stats\()', content)
    if match:
        content = content[:match.start()] + '\n\n@router.get("/stats", summary="Stats")' + content[match.start():]
        open(path, 'w', encoding='utf-8').write(content)
        print('Декоратор добавлен через regex!')
    else:
        print('Не найдено!')

from app.api.progress import router
print('Роуты:', [r.path for r in router.routes])
