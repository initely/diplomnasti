import asyncio
import sys
import os

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError
from migrations.add_task_fields import upgrade

async def run_migrations():
    try:
        # Подключаемся к базе данных
        await Tortoise.init(
            db_url='sqlite://db.sqlite3',
            modules={'models': ['models.user', 'models.school', 'models.task', 'models.result']}
        )
        
        # Получаем соединение с базой данных
        conn = Tortoise.get_connection("default")
        
        # Выполняем миграцию
        await upgrade(conn)
        
        print("Миграция успешно выполнена!")
        
    except DBConnectionError as e:
        print(f"Ошибка подключения к базе данных: {e}")
    except Exception as e:
        print(f"Произошла ошибка при выполнении миграции: {e}")
    finally:
        # Закрываем соединение
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(run_migrations()) 