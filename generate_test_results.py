import asyncio
from tortoise import Tortoise
from models.result import Result
from models.user import User
from models.task import Task
from datetime import datetime, timedelta
import random
import math

async def generate_test_data():
    # Подключаемся к базе данных
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models.user', 'models.task', 'models.result']}
    )
    
    # Получаем пользователей
    users = await User.filter(id__in=[3, 4, 954, 964, 965, 973, 989])
    # Получаем пользователя для confirmed_by (берем первого из списка)
    confirmer = users[0]
    
    # Создаем тестовые задания
    tasks = [
        await Task.create(
            subjects_name="Математика",
            description="Контрольная работа №1",
            local_id=1,
            type="score",
            max_score=10
        ),
        await Task.create(
            subjects_name="Математика",
            description="Контрольная работа №2",
            local_id=2,
            type="score",
            max_score=10
        ),
        await Task.create(
            subjects_name="Русский язык",
            description="Диктант",
            local_id=1,
            type="score",
            max_score=10
        ),
        await Task.create(
            subjects_name="Русский язык",
            description="Сочинение",
            local_id=2,
            type="score",
            max_score=10
        ),
        await Task.create(
            subjects_name="Физкультура",
            description="Бег 100 метров",
            local_id=1,
            type="time",
            max_score=10
        ),
        await Task.create(
            subjects_name="Физкультура",
            description="Прыжки в длину",
            local_id=2,
            type="time",
            max_score=10
        ),
        await Task.create(
            subjects_name="Информатика",
            description="Программирование на Python",
            local_id=1,
            type="score",
            max_score=10
        ),
        await Task.create(
            subjects_name="Информатика",
            description="Работа с базами данных",
            local_id=2,
            type="score",
            max_score=10
        )
    ]
    
    # Создаем список всех возможных комбинаций пользователь-задание
    all_combinations = [(user, task) for user in users for task in tasks]
    # Перемешиваем комбинации
    random.shuffle(all_combinations)
    
    # Перемешиваем так, чтобы не было подряд двух одинаковых пользователей
    def no_consecutive_same_user(pairs):
        result = []
        last_user = None
        pool = pairs[:]
        while pool:
            for i, (user, task) in enumerate(pool):
                if user != last_user:
                    result.append((user, task))
                    last_user = user
                    pool.pop(i)
                    break
            else:
                # Если не нашли, просто вставляем любой
                result.append(pool.pop(0))
                last_user = result[-1][0]
        return result

    all_combinations = no_consecutive_same_user(all_combinations)

    # В первых 10 делаем хотя бы 2 неподтверждённых
    first_10 = all_combinations[:10]
    for i in range(2):
        user, task = first_10[i]
        all_combinations[i] = (user, task, False)  # False = неподтверждён
    for i in range(2, 10):
        user, task = all_combinations[i]
        all_combinations[i] = (user, task, True)
    for i in range(10, len(all_combinations)):
        user, task = all_combinations[i]
        # Для физкультуры 30% шанс неподтверждения, иначе подтверждён
        is_confirmed = not (task.subjects_name == "Физкультура" and random.random() < 0.3)
        all_combinations[i] = (user, task, is_confirmed)

    # Генерируем результаты
    for user, task, is_confirmed in all_combinations:
        # Генерируем время выполнения (от 30 до 120 секунд)
        time_seconds = round(random.uniform(30, 120), 1)
        # Вычисляем балл: от 10 отнимаем количество полных минут (округление вниз)
        minutes = math.floor(time_seconds / 60)
        score = 10 - minutes
        score = max(0, min(10, score))  # Ограничиваем балл от 0 до 10
        
        # Генерируем случайную дату в пределах последних 30 дней
        date = datetime.now() - timedelta(days=random.randint(0, 30))
        
        await Result.create(
            user=user,
            task=task,
            score=score,
            time_seconds=time_seconds,
            confirmed=is_confirmed,
            confirmed_by=confirmer if is_confirmed else None,
            confirmation_date=date if is_confirmed else None,
            created_at=date
        )
    
    print("Тестовые данные успешно сгенерированы!")
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(generate_test_data()) 