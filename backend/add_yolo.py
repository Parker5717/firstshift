"""Добавляет YOLO инициализацию в main.py если её нет."""
path = 'app/main.py'
content = open(path, encoding='utf-8').read()

if 'yolo_mode' in content:
    print('YOLO уже есть в main.py')
else:
    # Добавляем после "Content seeded"
    old = 'log.info("Content seeded")'
    new = '''log.info("Content seeded")

    # YOLOv8 режим
    if settings.yolo_mode:
        log.info("YOLOv8 режим ВКЛЮЧEN")
        from app.cv.object_detector import _load_model
        _load_model()
    else:
        log.info("Режим: ArUco markers | SET CASPER_YOLO=1 для YOLOv8")'''

    if old in content:
        content = content.replace(old, new)
        open(path, 'w', encoding='utf-8').write(content)
        print('YOLO добавлен в main.py!')
    else:
        print('Строка не найдена, ищем альтернативу...')
        # Ищем Content seeded в любом варианте
        import re
        match = re.search(r'log\.info\(["\']Content seeded["\']\)', content)
        if match:
            pos = match.end()
            insert = '''

    # YOLOv8 режим
    if settings.yolo_mode:
        log.info("YOLOv8 режим ВКЛЮЧЕН")
        from app.cv.object_detector import _load_model
        _load_model()
    else:
        log.info("Режим: ArUco markers | SET CASPER_YOLO=1 для YOLOv8")'''
            content = content[:pos] + insert + content[pos:]
            open(path, 'w', encoding='utf-8').write(content)
            print('YOLO добавлен через regex!')
        else:
            print('Не удалось найти точку вставки!')
            print('Строки с log.info в файле:')
            for i, line in enumerate(content.split('\n')):
                if 'log.info' in line:
                    print(f'  {i}: {line}')
