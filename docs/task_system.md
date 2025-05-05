# Система выполнения заданий

## Общее описание
Система позволяет ученикам выполнять задания с отслеживанием времени, паузами и перерывами. Реализована с использованием WebSocket для реального времени и REST API для управления заданиями.

## Структура файлов
- `handlers/tasks.py` - основной обработчик заданий
- `pages/task_page/index.html` - страница выполнения задания
- `pages/task_page/task.js` - клиентская логика
- `models/task.py` - модель задания
- `models/result.py` - модель результата

## API Endpoints

### REST API
1. `GET /task/{task_id}` - получение страницы задания
2. `GET /task/{task_id}/info` - получение информации о задании
3. `POST /start_task/{task_id}` - начало выполнения задания
4. `POST /pause_task/{task_id}` - пауза задания
5. `POST /resume_task/{task_id}` - возобновление задания
6. `POST /finish_task/{task_id}` - завершение задания
7. `POST /check_answer/{task_id}` - проверка ответа

### WebSocket
- `ws://host/ws/task/{task_id}` - WebSocket соединение для обновлений времени и состояния

## Модели данных

### TaskModel (Pydantic)
```python
class TaskModel(BaseModel):
    id: int
    name: str
    subjects_name: str
    type: str
    max_score: float
```

### TaskSession (Pydantic)
```python
class TaskSession(BaseModel):
    start_time: datetime
    pause_time: Optional[datetime]
    total_time: timedelta
    is_paused: bool
    is_break: bool
    user_id: int
    task_id: int
    score: int
    task: TaskModel
```

### AnswerModel (Pydantic)
```python
class AnswerModel(BaseModel):
    answer: int
```

## Временные ограничения
```python
MAX_WORK_TIME = {
    1: timedelta(hours=1),    # 1 класс
    2: timedelta(hours=1.5),  # 2 класс
    3: timedelta(hours=2),    # 3 класс
    4: timedelta(hours=2),    # 4 класс
    5: timedelta(hours=2.5),  # 5 класс
    6: timedelta(hours=2.5),  # 6 класс
    7: timedelta(hours=3),    # 7 класс
    8: timedelta(hours=3),    # 8 класс
    9: timedelta(hours=3),    # 9 класс
    10: timedelta(hours=3),   # 10 класс
    11: timedelta(hours=3),   # 11 класс
}
BREAK_DURATION = timedelta(minutes=15)
```

## Текущий статус реализации
- ✅ Базовая структура API
- ✅ WebSocket для обновлений времени
- ✅ Система пауз и перерывов
- ✅ Проверка ответов
- ✅ Сохранение результатов
- ✅ WebSocket соединение работает стабильно
- ✅ Обработка ответов реализована корректно

## Следующие шаги
1. Добавить обработку ошибок на клиенте
2. Улучшить UI/UX
3. Добавить статистику выполнения
4. Добавить возможность просмотра истории выполненных заданий
5. Реализовать систему подсказок

## Как запустить
1. Убедитесь, что все зависимости установлены
2. Запустите сервер: `python main.py`
3. Откройте страницу задания: `http://localhost:8080/task/1`

## Тестирование
1. Создайте тестовое задание через скрипт инициализации
2. Войдите как ученик
3. Откройте страницу задания
4. Проверьте все функции:
   - Начало задания
   - Пауза/возобновление
   - Проверка ответов
   - Перерывы
   - Завершение задания 