"""Патч: добавляет YOLO инициализацию после 'Content seeded' в main.py."""
path = 'app/main.py'
content = open(path, encoding='utf-8').read()

print('yolo_mode встречается:', content.count('yolo_mode'), 'раз')
print('YOLOv8 встречается:', content.count('YOLOv8'), 'раз')

# Ищем строку Content seeded и смотрим что после неё
idx = content.find('Content seeded')
if idx == -1:
    print('Content seeded не найден!')
else:
    print('Контекст вокруг Content seeded:')
    print(repr(content[idx-20:idx+100]))

    # Вставляем YOLO блок сразу после строки с Content seeded
    line_end = content.find('\n', idx)
    insert = """
    if settings.yolo_mode:
        log.info("YOLOv8 режим ВКЛЮЧЕН")
        from app.cv.object_detector import _load_model
        _load_model()
    else:
        log.info("Режим ArUco | SET CASPER_YOLO=1 для YOLOv8")"""

    if 'YOLOv8 режим' not in content:
        content = content[:line_end] + insert + content[line_end:]
        open(path, 'w', encoding='utf-8').write(content)
        print('YOLO инициализация добавлена!')
    else:
        print('YOLOv8 режим уже есть в файле — проверяем позицию:')
        idx2 = content.find('YOLOv8 режим')
        print(repr(content[idx2-50:idx2+100]))
