import asyncio
import aiohttp
import random
from faker import Faker
from datetime import datetime, timedelta
import json
import logging
import signal
import sys
from collections import defaultdict
import statistics
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные для сбора статистики
stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'request_times': [],
    'endpoint_stats': defaultdict(lambda: {'total': 0, 'success': 0, 'times': []}),
    'error_codes': defaultdict(int),
    'concurrent_users': 0,
    'max_concurrent_users': 0,
    'connection_errors': 0,
    'timeout_errors': 0
}

# Базовые настройки
BASE_URL = 'http://127.0.0.1:8080'
fake = Faker('ru_RU')

# Уменьшаем нагрузку
MAX_CONNECTIONS = 500  # Уменьшаем количество одновременных соединений
CONNECTION_TIMEOUT = 30  # Увеличиваем таймаут
REQUEST_DELAY = 1.0  # Задержка между запросами

# Глобальные переменные для управления состоянием скрипта
running = True
tasks = set()

SCHOOLS = [
    "Школа №1", "Школа №2", "Гимназия №1", "Лицей №1",
    "Школа №3 им. А.С. Пушкина", "Гимназия №2",
    "Школа №4 с углубленным изучением английского языка",
    "Школа №5", "Лицей №2", "Школа №6"
]

LANGUAGES = ["english", "german", "french", "spanish"]
PHYSICAL_GROUPS = ["main", "preparatory", "special", "exempt"]
SUBJECTS = [
    "mathematics", "russian-language", "nature", "chemistry",
    "reading", "physical-education", "art", "music",
    "informatics", "astronomy", "foreign-language",
    "history", "physics", "social-science"
]

PAGES = [
    "/parents-database",
    "/add-parent",
    "/children-statistics",
    "/subjects",
    "/me"
]

class User:
    """Класс для хранения информации о пользователе"""
    def __init__(self, email, password, full_name, role="parent"):
        self.email = email
        self.password = password
        self.full_name = full_name
        self.role = role
        self.token = None  # Токен авторизации

async def make_request(method, url, **kwargs):
    """
    Универсальная функция для выполнения HTTP-запросов
    Автоматически закрывает соединение после выполнения
    """
    timeout = aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)
    start_time = datetime.now()
    endpoint = url.split('/')[-1]  # Получаем имя эндпоинта для статистики
    
    try:
        # Добавляем задержку между запросами
        await asyncio.sleep(REQUEST_DELAY)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Выполняю {method.upper()} запрос к {url}")
            
            try:
                async with getattr(session, method)(url, **kwargs) as response:
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    # Обновляем статистику
                    stats['total_requests'] += 1
                    stats['request_times'].append(duration)
                    stats['endpoint_stats'][endpoint]['total'] += 1
                    stats['endpoint_stats'][endpoint]['times'].append(duration)
                    
                    if response.status in [200, 201]:  # Считаем 201 успешным ответом
                        stats['successful_requests'] += 1
                        stats['endpoint_stats'][endpoint]['success'] += 1
                    else:
                        stats['failed_requests'] += 1
                        stats['error_codes'][response.status] += 1
                    
                    logger.info(f"Запрос к {url} выполнен за {duration:.2f} сек, статус: {response.status}")
                    
                    if method == 'post':
                        return await response.json()
                    return response.status in [200, 201]  # Возвращаем True для кодов 200 и 201
            except aiohttp.ClientError as e:
                stats['connection_errors'] += 1
                logger.error(f"Ошибка соединения при запросе к {url}: {str(e)}")
                logger.error(f"Трассировка: {traceback.format_exc()}")
                return False
    except asyncio.TimeoutError:
        stats['timeout_errors'] += 1
        stats['failed_requests'] += 1
        stats['error_codes']['timeout'] += 1
        logger.error(f"Таймаут при выполнении запроса к {url}")
        return False
    except Exception as e:
        stats['failed_requests'] += 1
        stats['error_codes']['exception'] += 1
        logger.error(f"Ошибка при выполнении запроса к {url}: {str(e)}")
        logger.error(f"Трассировка: {traceback.format_exc()}")
        return False

async def register_user(user):
    """Регистрация нового пользователя"""
    url = f"{BASE_URL}/register"
    data = {
        "email": user.email,
        "password": user.password,
        "role": user.role,
        "full_name": user.full_name
    }
    logger.info(f"Регистрирую пользователя {user.email}")
    return await make_request('post', url, json=data)

async def login_user(user):
    """Авторизация пользователя"""
    url = f"{BASE_URL}/login"
    data = {
        "email": user.email,
        "password": user.password
    }
    logger.info(f"Вход пользователя {user.email}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("token")
                logger.error(f"Ошибка входа для {user.email}: статус {response.status}")
    except Exception as e:
        logger.error(f"Ошибка входа для {user.email}: {str(e)}")
    return None

async def logout_user(token):
    """Выход пользователя из системы"""
    url = f"{BASE_URL}/logout"
    headers = {"Authorization": f"Bearer {token}"}
    logger.info("Выход пользователя")
    return await make_request('get', url, headers=headers)

async def create_child(token, parent_email):
    """Создание ребенка для родителя"""
    url = f"{BASE_URL}/create_children"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "surname": fake.last_name(),
        "name": fake.first_name(),
        "patronymic": fake.middle_name(),
        "gender": random.choice(["male", "female"]),
        "current_class": f"{random.randint(1, 11)}{random.choice(['А', 'Б', 'В'])}",
        "school": random.choice(SCHOOLS),
        "physical_group": random.choice(PHYSICAL_GROUPS),
        "first_language": random.choice(LANGUAGES),
        "second_language": random.choice(LANGUAGES),
        "email": fake.unique.email(),
        "password": "childpass123"
    }
    logger.info(f"Создание ребенка для {parent_email}")
    return await make_request('post', url, json=data, headers=headers)

async def visit_random_page(token):
    """Посещение случайной страницы"""
    headers = {"Authorization": f"Bearer {token}"}
    page = random.choice(PAGES)
    if page == "/subjects" and random.random() < 0.5:
        page = f"/subjects/{random.choice(SUBJECTS)}"
    
    logger.info(f"Посещение страницы {page}")
    return await make_request('get', f"{BASE_URL}{page}", headers=headers)

async def get_random_data(token):
    """Получение случайных данных"""
    headers = {"Authorization": f"Bearer {token}"}
    endpoints = ["/get_parents", "/get_children"]
    endpoint = random.choice(endpoints)
    params = {
        "offset": random.randint(0, 100),
        "limit": random.randint(1, 100),
        "search": fake.word() if random.random() < 0.3 else None
    }
    
    logger.info(f"Получение данных с {endpoint}")
    return await make_request('get', f"{BASE_URL}{endpoint}", headers=headers, params=params)

async def user_cycle(semaphore):
    """
    Цикл действий одного пользователя
    Выполняется в рамках семафора для ограничения количества одновременных пользователей
    """
    try:
        async with semaphore:
            if not running:
                return
                
            user = User(
                email=fake.unique.email(),
                password="testpass123",
                full_name=fake.name()
            )
            
            logger.info(f"Начало цикла для пользователя {user.email}")
            
            # Регистрация
            if not await register_user(user):
                logger.error(f"Ошибка регистрации для {user.email}")
                return
            
            # Вход
            token = await login_user(user)
            if not token:
                logger.error(f"Ошибка входа для {user.email}")
                return
            
            # Список возможных действий
            actions = [
                lambda: create_child(token, user.email),
                lambda: visit_random_page(token),
                lambda: get_random_data(token)
            ]
            
            # Выполняем случайное количество действий
            num_actions = random.randint(1, 2)  # Уменьшаем количество действий
            for i in range(num_actions):
                if not running:
                    break
                action = random.choice(actions)
                await action()
                await asyncio.sleep(random.uniform(1.0, 2.0))  # Увеличиваем задержку между действиями
            
            # Выход
            if running:
                await logout_user(token)
            logger.info(f"Завершение цикла для пользователя {user.email}")
    except asyncio.CancelledError:
        logger.info("Задача отменена")
    except Exception as e:
        logger.error(f"Ошибка в цикле пользователя: {str(e)}")
        logger.error(f"Трассировка: {traceback.format_exc()}")

async def shutdown(signal, loop):
    """
    Обработка сигналов завершения работы (Ctrl+C, SIGTERM)
    """
    global running
    logger.info(f"Получен сигнал {signal.name}...")
    running = False  # Устанавливаем флаг завершения
    
    # Отменяем все активные задачи
    for task in tasks:
        task.cancel()
    
    # Ждем завершения всех задач
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()  # Останавливаем event loop

def print_stats():
    """Вывод статистики тестирования"""
    logger.info("\n=== Статистика тестирования ===")
    logger.info(f"Всего запросов: {stats['total_requests']}")
    logger.info(f"Успешных запросов: {stats['successful_requests']}")
    logger.info(f"Неудачных запросов: {stats['failed_requests']}")
    
    if stats['total_requests'] > 0:
        success_rate = (stats['successful_requests'] / stats['total_requests']) * 100
        logger.info(f"Процент успешных запросов: {success_rate:.2f}%")
        
        if stats['request_times']:
            avg_time = statistics.mean(stats['request_times'])
            median_time = statistics.median(stats['request_times'])
            p95_time = statistics.quantiles(stats['request_times'], n=20)[18]  # 95-й перцентиль
            logger.info(f"Среднее время ответа: {avg_time:.2f} сек")
            logger.info(f"Медианное время ответа: {median_time:.2f} сек")
            logger.info(f"95-й перцентиль времени ответа: {p95_time:.2f} сек")
    
    logger.info("\nСтатистика по эндпоинтам:")
    for endpoint, data in stats['endpoint_stats'].items():
        if data['total'] > 0:
            success_rate = (data['success'] / data['total']) * 100
            avg_time = statistics.mean(data['times']) if data['times'] else 0
            logger.info(f"{endpoint}:")
            logger.info(f"  Всего запросов: {data['total']}")
            logger.info(f"  Успешных: {data['success']} ({success_rate:.2f}%)")
            logger.info(f"  Среднее время: {avg_time:.2f} сек")
    
    logger.info("\nКоды ошибок:")
    for code, count in stats['error_codes'].items():
        logger.info(f"  {code}: {count}")
    
    logger.info(f"\nОшибки соединения: {stats['connection_errors']}")
    logger.info(f"Ошибки таймаута: {stats['timeout_errors']}")
    logger.info(f"Максимальное количество одновременных пользователей: {stats['max_concurrent_users']}")
    logger.info("=============================\n")

async def main():
    """
    Основная функция скрипта
    """
    # Настройка обработки сигналов завершения
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    # Устанавливаем время начала и окончания теста
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=1)
    
    logger.info(f"Начало теста. Время окончания: {end_time}")
    
    # Создаем семафор для ограничения количества одновременных пользователей
    semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
    
    # Инициализируем множество задач
    global tasks
    tasks = set()
    
    try:
        # Основной цикл работы
        while running and datetime.now() < end_time:
            # Обновляем статистику по количеству пользователей
            current_users = len(tasks)
            stats['concurrent_users'] = current_users
            stats['max_concurrent_users'] = max(stats['max_concurrent_users'], current_users)
            
            # Создаем новые задачи, если их меньше максимального количества
            while len(tasks) < MAX_CONNECTIONS and running:
                task = asyncio.create_task(user_cycle(semaphore))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
                logger.info(f"Создана новая задача. Всего задач: {len(tasks)}")
            
            # Очищаем завершенные задачи
            tasks = {t for t in tasks if not t.done()}
            
            # Ждем немного перед созданием новых задач
            await asyncio.sleep(0.5)
        
        # Дожидаемся завершения всех задач
        logger.info("Ожидание завершения всех задач...")
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        logger.info("Основной цикл отменен")
    finally:
        print_stats()  # Выводим финальную статистику
        logger.info("Тест завершен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Ошибка в основном цикле: {str(e)}")
    finally:
        logger.info("Программа завершена")
