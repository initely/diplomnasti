import asyncio
from tortoise import Tortoise
from models.task import Task

async def check_task():
    # Подключаемся к базе данных
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models.task']}
    )
    
    # Получаем все задания
    tasks = await Task.all()
    print("\nСписок заданий в базе данных:")
    for task in tasks:
        print(f"ID: {task.id}")
        print(f"Название: {task.name}")
        print(f"Предмет: {task.subjects_name}")
        print(f"Тип: {task.type}")
        print(f"Максимальный балл: {task.max_score}")
        print("-" * 30)
    
    # Закрываем соединение
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(check_task()) 