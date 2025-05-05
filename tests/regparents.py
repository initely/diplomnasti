import requests
from faker import Faker
import random
import json

BASE_URL = 'http://127.0.0.1:8080'  # Адрес твоего сервера
PSYCHO_EMAIL = 'psyc@mail.ru'  # Должен быть заранее создан
PSYCHO_PASSWORD = 'qwerty123'  # Пароль психолога
NUM_PARENTS = 100
CHILDREN_PER_PARENT = 2

fake = Faker('ru_RU')

# Логин психолога
session = requests.Session()
resp = session.post(f'{BASE_URL}/login', json={
    'email': PSYCHO_EMAIL,
    'password': PSYCHO_PASSWORD
})
assert resp.ok, f'Ошибка входа психолога: {resp.text}'

parent_credentials = []

SCHOOLS = [
    "Школа №1",
    "Школа №2",
    "Гимназия №1",
    "Лицей №1",
    "Школа №3 им. А.С. Пушкина",
    "Гимназия №2",
    "Школа №4 с углубленным изучением английского языка",
    "Школа №5",
    "Лицей №2",
    "Школа №6"
]
LANGUAGES = ["english", "german", "french", "spanish"]

for i in range(NUM_PARENTS):
    parent_email = fake.unique.email()
    parent_password = 'parentpass123'
    parent_full_name = fake.name()
    school = random.choice(SCHOOLS)
    # Создаём родителя
    resp = session.post(f'{BASE_URL}/create_parent', json={
        'full_name': parent_full_name,
        'email': parent_email,
        'password': parent_password,
        'school': school
    })
    if not resp.ok:
        print(f'Ошибка создания родителя {parent_email}: {resp.text}')
        continue
    parent_credentials.append((parent_email, parent_password, parent_full_name))
    print(f'Создан родитель: {parent_email}')

# Для каждого родителя логинимся и создаём ребёнка
for parent_email, parent_password, parent_full_name in parent_credentials:
    parent_session = requests.Session()
    resp = parent_session.post(f'{BASE_URL}/login', json={
        'email': parent_email,
        'password': parent_password
    })
    if not resp.ok:
        print(f'Ошибка входа родителя {parent_email}: {resp.text}')
        continue
    for _ in range(random.randint(1,3)):
        child_surname = fake.last_name()
        child_name = fake.first_name()
        child_patronymic = fake.middle_name()
        child_gender = random.choice(['male', 'female'])
        child_class = f"{random.randint(1, 11)}{random.choice(['А', 'Б', 'В'])}"
        school = random.choice(SCHOOLS)
        physical_group = random.choice(['main', 'preparatory', 'special', 'exempt'])
        langs = random.sample(LANGUAGES, k=2)
        first_language = langs[0]
        second_language = langs[1]
        child_email = fake.unique.email()
        child_password = 'childpass123'
        resp = parent_session.post(f'{BASE_URL}/create_children', json={
            'surname': child_surname,
            'name': child_name,
            'patronymic': child_patronymic,
            'gender': child_gender,
            'current_class': child_class,
            'school': school,
            'physical_group': physical_group,
            'first_language': first_language,
            'second_language': second_language,
            'email': child_email,
            'password': child_password
        })
        if not resp.ok:
            print(f'Ошибка создания ребёнка для {parent_email}: {resp.text}')
        else:
            print(f'Создан ребёнок для {parent_email}: {child_surname} {child_name} {child_patronymic}')
