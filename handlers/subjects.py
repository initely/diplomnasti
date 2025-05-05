from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any
from models.user import User, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="pages")

@router.get("/subjects", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "subjects_page/index.html", 
        {
            "request": request,
            "current_user": current_user
        }
    )

@router.get("/subjects/{subject}", response_class=HTMLResponse)
async def subject_page(
    request: Request, 
    subject: str,
    current_user: User = Depends(get_current_user)
):
    # Список доступных предметов
    available_subjects = {
        "mathematics": "Математика",
        "russian-language": "Русский язык", 
        "nature": "Окружающий мир",
        "chemistry": "Химия",
        "reading": "Чтение",
        "physical-education": "Физкультура",
        "art": "ИЗО",
        "music": "Музыка",
        "informatics": "Информатика",
        "astronomy": "Астрономия"
    }
    
    # Проверяем есть ли такой предмет
    if subject not in available_subjects:
        raise HTTPException(status_code=404, detail="Предмет не найден")
        
    # Получаем название предмета на русском
    subject_name = available_subjects[subject]
    
    return templates.TemplateResponse(
        "subjects_page/subject.html",
        {
            "request": request,
            "subject": subject,
            "subject_name": subject_name,
            "current_user": current_user
        }
    )
