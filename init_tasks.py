import asyncio
from tortoise import Tortoise
from models.task import Task

async def init():
    # Подключаемся к базе данных
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models.task']}
    )
    
    # Создаем тестовое математическое задание
    math_task = await Task.create(
        subjects_name="Математика",
        name="Сложение чисел",
        type="score",
        max_score=10
    )
    
    print(f"Создано задание: {math_task}")
    
    # Закрываем соединение
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(init())