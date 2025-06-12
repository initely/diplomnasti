# models/user.py

from typing import Any, Dict, Optional
import uuid
from fastapi import Cookie, Depends, HTTPException, status, Response
from tortoise.models import Model
from fastapi.responses import RedirectResponse

from tortoise import fields, models
import json

from models.school import School





class User(models.Model):
    id = fields.IntField(pk=True)
    
    # Общие поля
    email = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=128, description="Хэшированный пароль")
    session_id = fields.CharField(max_length=128, null=True, description="Идентификатор сессии пользователя")
    
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    # Поле для указания типа пользователя.
    # Возможные значения: "child", "parent", "psychologist", "admin"
    role = fields.CharField(max_length=20)
    
    # Для всех пользователей, кроме админа, можно привязать школу (необязательно)
    school = fields.ForeignKeyField(
        "models.School", 
        related_name="users", 
        null=True,
        on_delete=fields.SET_NULL,
        description="Школа, с которой связан пользователь"
    )
    
    # Поля для Ребёнка:
    full_name = fields.CharField(max_length=255, null=True, description="ФИО")
    current_class = fields.CharField(max_length=50, null=True, description="Текущий класс")
    # История: в каких классах был и какие тесты проходил (хранится как JSON)
    history = fields.TextField(null=True, description="История классов и тестов (JSON)")
    # Иностранные языки: список из 2-х языков (хранится как JSON-массив)
    languages = fields.TextField(null=True, description="Иностранные языки (JSON)")
    gender = fields.CharField(max_length=10, null=True)
    physical_group = fields.CharField(max_length=50, null=True)
    
    # Поле для Родителя:
    # Список идентификаторов детей (хранится как JSON-массив)
    children_list = fields.TextField(null=True, description="Список id детей (JSON)")
    
    # Для работника школы (психолога) никакие дополнительные поля делать не обязательно,
    # т.к. ФИО и ссылка на школу уже есть. Школа, где работает психолог, хранится в поле school
    # Список идентификаторов родителей, с которыми работает сотрудник (хранится как JSON-массив)
    parents_list = fields.TextField(null=True, description="Список id родителей (JSON)")

    
    class Meta:
        table = "user"
    
    def __str__(self):
        return f"{self.email} ({self.role})"
    
    # Вспомогательные методы для работы с JSON-полями
    def get_history(self) -> dict:
        return json.loads(self.history) if self.history else {}
        
    def get_languages(self) -> list:
        return json.loads(self.languages) if self.languages else []
        
    def get_children_list(self) -> list:
        return json.loads(self.children_list) if self.children_list else []
        
    def get_parents_list(self) -> list:
        return json.loads(self.parents_list) if self.parents_list else []

    async def refresh_session(self):
        self.session_id = str(uuid.uuid4())
        await self.save()
        return self.session_id

class RedirectException(Exception):
    def __init__(self):
        self.redirect_url = "/"

async def get_current_user(response: Response, session_id: Optional[str] = Cookie(None)) -> Optional[Dict[str, Any]]:
    if not session_id:
        response.delete_cookie("session_id")
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация"
        )

    user = await User.filter(session_id=session_id).first()
    if not user:
        response.delete_cookie("session_id")
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация"
        )
        
    return user

# Зависимость для проверки роли администратора
def admin_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access forbidden: Admins only")
    return current_user

# Добавляем после child_required
def child_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.role != "child":
        raise HTTPException(
            status_code=403, 
            detail="Доступ запрещен: только для детей"
        )
    return current_user

def parent_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.role != "parent":
        raise HTTPException(
            status_code=403, 
            detail="Доступ запрещен: только для родителей"
        )
    return current_user


def school_worker_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.role != "psychologist":
        raise HTTPException(
            status_code=403, 
            detail="Доступ запрещен: только для Психолога"
        )
    return current_user

def parent_or_school_worker_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.role not in ["parent", "psychologist"]:
        raise HTTPException(
            status_code=403, 
            detail="Доступ запрещен: только для родителей и работников школы"
        )
    return current_user

async def is_parent_of_child(parent_id: int, child_uid: str) -> bool:
    parent = await User.get(id=parent_id)
    children_list = parent.get_children_list()
    return int(child_uid) in children_list

# Этот метод можно использовать в parents.py
async def get_children_for_parent(parent_id: int) -> list:
    parent = await User.get(id=parent_id)
    children_ids = parent.get_children_list()
    
    # Получаем информацию о всех детях из списка
    children = await User.filter(id__in=children_ids).values(
        'id',
        'full_name',
        'current_class',
        'school_id',
        'gender',
        'physical_group',
        'languages'
    )
    
    # Преобразуем данные в нужный формат
    formatted_children = []
    for child in children:
        names = child['full_name'].split() if child['full_name'] else ['', '', '']
        formatted_children.append({
            'uid': child['id'],
            'surname': names[0] if len(names) > 0 else '',
            'name': names[1] if len(names) > 1 else '',
            'patronymic': names[2] if len(names) > 2 else '',
            'current_class': child['current_class'],
            'school_id': child['school_id'],
            'gender': child['gender'],
            'physical_group': child['physical_group'],
            'languages': json.loads(child['languages']) if child['languages'] else []
        })
    
    return formatted_children

async def update_child_details(child_uid: str, child_data: dict) -> bool:
    try:
        child = await User.get(id=child_uid)
        print(child_data)
        # Обновляем основные поля
        
        schoolname=child_data["school"].strip()

        if 'school' in child_data:
            
            school = await School.filter(name=schoolname).first()

            if not school:
                school = await School.create(name=schoolname)
            
            child.school = school
            
        if 'gender' in child_data:
            child.gender = child_data['gender']
        
        if 'current_class' in child_data:
            child.current_class = child_data['current_class']
            
        if 'physical_group' in child_data:
            child.physical_group = child_data['physical_group']
            
        if 'languages' in child_data:
            # Сохраняем языки как JSON строку
            child.languages = json.dumps(child_data['languages'])
        
        if 'email' in child_data:
            child.email =child_data["email"]

        await child.save()
        return True
        
    except Exception as e:
        print(f"Error updating child details: {e}")
        return False


