import json
from typing import Any, Dict
from fastapi import APIRouter, FastAPI, HTTPException, Response, status, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from tortoise.contrib.fastapi import register_tortoise
from models.user import User, get_current_user, school_worker_required
from tortoise.exceptions import ValidationError
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel
from models.school import School
from utils.logger import log_request, log_response, log_error

import secrets
import bcrypt

def hash_password(password: str) -> str:
    """
    Хеширует пароль с помощью bcrypt.
    Возвращает хешированное значение в виде строки.
    """
    # Преобразуем пароль в байты
    password_bytes = password.encode('utf-8')
    # Генерируем соль (по умолчанию 12 раундов)
    salt = bcrypt.gensalt()
    # Хешируем пароль с солью
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Приводим результат к виду строки (можно хранить как строку)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие пароля и его хеша.
    Возвращает True, если пароль корректен, иначе False.
    """
    # Преобразуем данные в байты
    plain_password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    # Функция bcrypt.checkpw возвращает True если пароли совпадают
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)




router = APIRouter()

# Инициализация шаблонизатора
templates = Jinja2Templates(directory="pages")

# Добавьте эту модель в начало файла
class ChildCreate(BaseModel):
    surname: str
    name: str
    patronymic: str
    gender: str
    current_class: str
    school: str
    physical_group: str
    first_language: str
    second_language: str
    email: str
    password: str

class ParentCreate(BaseModel):
    full_name: str
    email: str
    password: str
    school: str = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "parent"
    full_name: str
    current_class: str = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str



#Защищённый эндпоинт — личный кабинет

@router.get("/me", response_class=HTMLResponse)
async def get_current_user_info(request: Request, current_user: User = Depends(get_current_user)):
    print("authme")
    try:
        # Базовые данные пользователя
        user_data = {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
            "full_name": current_user.full_name
        }
        
        # Добавляем специфичные данные в зависимости от роли
        if current_user.role == "child":
            user_data.update({
                "current_class": current_user.current_class,
                "languages": json.loads(current_user.languages) if current_user.languages else [],
                "history": json.loads(current_user.history) if current_user.history else {}
            })
        elif current_user.role == "parent":
            user_data.update({
                "children_list": json.loads(current_user.children_list) if current_user.children_list else []
            })
            
        # Возвращаем шаблон с данными пользователя
        return templates.TemplateResponse(
            "user_page/user_settings.html",
            {
                "request": request,  # Требуется для Jinja2Templates
                "user": user_data,
                "role": current_user.role
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении данных пользователя"
        )

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    try:
        # Проверка существования пользователя
        existing_email = await User.filter(email=user_data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        # Хэширование пароля
        hashed = hash_password(user_data.password)

        # Создание нового пользователя
        new_user = await User.create(
            email=user_data.email,
            hashed_password=hashed,
            role="parent",
            full_name=user_data.full_name
        )

        return {"message": "Регистрация прошла успешно", "user_id": new_user.id}
    except ValidationError:
        raise HTTPException(status_code=400, detail="Неверные данные для регистрации")



@router.post("/login")
async def login(login_data: UserLogin, response: Response):
    try:
        # Поиск пользователя по email
        user = await User.filter(email=login_data.email).first()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный email"
            )

        # Проверка пароля
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный пароль"
            )

        # Генерация session_id и сохранение
        new_session_id = await user.refresh_session()
        
        # Устанавливаем cookie
        response.set_cookie(key="session_id", value=new_session_id, httponly=True)
        
        return {
            "message": "Вход выполнен успешно",
            "redirect": "/"
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при входе в систему"
        )


@router.get("/logout")
async def logout(request: Request, response: Response, current_user: Dict[str, Any] = Depends(get_current_user)):
    log_request(request, current_user)
    try:
        current_user.session_id = None
        current_user.last_login_ip = None
        await current_user.save()
        response.delete_cookie("session_id")
        log_response({"message": "Успешный выход из системы"})
        return RedirectResponse(url="/", status_code=303, headers=response.headers)
    except Exception as e:
        log_error(e, "Ошибка при выходе из системы")
        raise HTTPException(status_code=500, detail="Ошибка при выходе из системы")


@router.post("/create_children")
async def create_children(
    request: Request,
    child_data: ChildCreate,
    current_user: User = Depends(get_current_user)
):
    log_request(request, current_user)
    try:
        if current_user.role != "parent":
            log_error(Exception("Попытка создания ребенка не родителем"), f"User ID: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только родители могут добавлять детей"
            )

        existing_user = await User.filter(email=child_data.email).first()
        if existing_user:
            log_error(Exception("Пользователь с таким email уже существует"), f"Email: {child_data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        school = await School.filter(name=child_data.school).first()

        if not school:
            school = await School.create(name=child_data.school)
            log_response({"message": "Создана новая школа", "school_name": child_data.school})

        full_name = f"{child_data.surname} {child_data.name} {child_data.patronymic}"

        new_child = await User.create(
            email=child_data.email,
            hashed_password=hash_password(child_data.password),
            role="child",
            full_name=full_name,
            current_class=child_data.current_class,
            school=school,
            physical_group=child_data.physical_group,
            languages=json.dumps([
                 child_data.first_language,
                 child_data.second_language
            ]),
            gender=child_data.gender
        )

        parent_user = await User.get(id=current_user.id)
        current_children = json.loads(parent_user.children_list) if parent_user.children_list else []
        current_children.append(new_child.id)
        parent_user.children_list = json.dumps(current_children)
        await parent_user.save()

        await school.children.add(new_child)
        
        log_response({
            "message": "Ребёнок успешно добавлен",
            "child_id": new_child.id,
            "parent_id": current_user.id
        })
        
        return {
            "message": "Ребёнок успешно добавлен",
            "child_id": new_child.id
        }

    except Exception as e:
        log_error(e, "Ошибка при создании ребенка")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/create_parent")
async def create_parent(
    request: Request,
    parent_data: ParentCreate,
    current_user: User = Depends(school_worker_required)
):
    log_request(request, current_user)
    try:
        if not current_user.school:
            log_error(Exception("Психолог не привязан к школе"), f"User ID: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Психолог должен быть привязан к школе"
            )

        existing_user = await User.filter(email=parent_data.email).first()
        if existing_user:
            log_error(Exception("Пользователь с таким email уже существует"), f"Email: {parent_data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        # Получаем школу
        school = await School.get(id=current_user.school_id)

        new_parent = await User.create(
            email=parent_data.email,
            hashed_password=hash_password(parent_data.password),
            role="parent",
            full_name=parent_data.full_name,
            school=school
        )

        # Добавляем родителя в список родителей школы
        await school.parents.add(new_parent)
        
        log_response({
            "message": "Родитель успешно добавлен",
            "parent_id": new_parent.id,
            "psychologist_id": current_user.id
        })
        
        return {
            "message": "Родитель успешно добавлен",
            "parent_id": new_parent.id
        }
    except Exception as e:
        log_error(e, f"Error creating parent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании родителя"
        )

@router.post("/change-password")
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user)
):
    try:
        # Проверка текущего пароля
        if not verify_password(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный текущий пароль"
            )

        # Проверка совпадения новых паролей
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Новые пароли не совпадают"
            )

        # Хэширование нового пароля
        new_hashed_password = hash_password(password_data.new_password)
        
        # Обновление пароля
        current_user.hashed_password = new_hashed_password
        await current_user.save()

        return {"message": "Пароль успешно изменен"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при смене пароля"
        )

