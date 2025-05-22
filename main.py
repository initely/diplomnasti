import json
import aiosqlite
from fastapi import FastAPI, Form, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uuid
from handlers import auth
from handlers.childrens import router as childrens_router
from handlers.parents import router as parents_router
from handlers.school_worker import router as school_worker_router
from handlers.tasks import router as tasks_router
from middleware.logging_middleware import LoggingMiddleware
from utils.logger import log_request, log_response, log_error

from models.user import User, get_current_user, RedirectException
from typing import Optional, Dict, Any

from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DBConnectionError

app = FastAPI()

# Добавляем middleware для логирования
app.add_middleware(LoggingMiddleware)

app.include_router(auth.router)
app.include_router(childrens_router)
app.include_router(parents_router)
app.include_router(school_worker_router)
app.include_router(tasks_router)

# Настройка статических файлов
app.mount("/pages", StaticFiles(directory="pages"), name="pages")
app.mount("/icons", StaticFiles(directory="icons"), name="icons")

app.mount("/db", StaticFiles(directory="db"), name="images")

# Настройка шаблонов
templates = Jinja2Templates(directory="pages")

# ----------------- Эндпоинты -----------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, current_user: Optional[Dict[str, Any]] = None):
    log_request(request, current_user)
    try:
        session_id = request.cookies.get("session_id")
        if session_id:  
            current_user = await User.filter(session_id=session_id).first()
            if current_user:
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
                response = templates.TemplateResponse(
                    "main_page/main_authorized.html",
                    {
                        "request": request,
                        "user": user_data,
                        "role": current_user.role
                    }
                )
                log_response({"template": "main_authorized.html", "user_role": current_user.role})
                return response
    except Exception as e:
        log_error(e, "Ошибка при проверке авторизации")
    
    # Если пользователь не авторизован или произошла ошибка
    response = templates.TemplateResponse("main_page/main_unauthorized.html", {"request": request, "current_user": None})
    log_response({"template": "main_unauthorized.html"})
    return response

# Регистрация Tortoise ORM с использованием helper-функции от fastapi
try:
    register_tortoise(
        app,
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models.user', 'models.school', 'models.task', 'models.result']},
        generate_schemas=True,
        add_exception_handlers=True,
    )
except DBConnectionError as e:
    log_error(e, "Ошибка подключения к базе данных")
    print("Ошибка подключения к базе данных")

@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    log_request(request)
    log_response({"redirect_url": exc.redirect_url}, status_code=303)
    return RedirectResponse(url=exc.redirect_url, status_code=303)

@app.get("/available_schools")
async def get_available_schools(request: Request):
    log_request(request)
    # Здесь можно подключить реальную базу данных
    # Пока возвращаем тестовый список школ
    schools = [
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
    log_response({"schools_count": len(schools)})
    return schools

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)


