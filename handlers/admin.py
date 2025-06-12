from typing import Any, Dict
from fastapi import APIRouter, Request, Query, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, admin_required
from models.school import School
from utils.logger import log_request, log_response, log_error
from datetime import datetime
from handlers.auth import hash_password

router = APIRouter()
templates = Jinja2Templates(directory="pages")

@router.get("/school_workers_database", response_class=HTMLResponse)
async def school_workers_database(request: Request, current_user: Dict[str, Any] = Depends(admin_required)):
    return templates.TemplateResponse(
        "admin_pages/school_workers_database.html",
        {"request": request}
    )

@router.get("/add_school_worker", response_class=HTMLResponse)
async def add_school_worker(request: Request, current_user: Dict[str, Any] = Depends(admin_required)):
    return templates.TemplateResponse(
        "admin_pages/add_school_worker.html",
        {"request": request}
    )

@router.get("/get_schools")
async def get_schools(current_user: User = Depends(admin_required)):
    try:
        schools = await School.all()
        return [{"id": school.id, "name": school.name} for school in schools]
    except Exception as e:
        log_error(e, "Ошибка при получении списка школ")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка школ"
        )

@router.post("/create_school_worker")
async def create_school_worker(
    request: Request,
    data: Dict[str, Any],
    current_user: User = Depends(admin_required)
):
    log_request(request, current_user)
    try:
        # Проверяем, существует ли пользователь с таким email
        existing_user = await User.filter(email=data["email"]).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        # Проверяем, существует ли школа
        school = await School.get(id=data["school_id"])
        if not school:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Школа не найдена"
            )

        # Создаем нового пользователя
        user = await User.create(
            email=data["email"],
            full_name=data["full_name"],
            hashed_password= hash_password(data["password"]),
            role="psychologist",
            school=school
        )

        log_response({
            "message": "Работник школы успешно создан",
            "user_id": user.id,
            "school_id": school.id
        })

        return {"message": "Работник школы успешно создан", "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, "Ошибка при создании работника школы")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании работника школы"
        )

@router.get("/get_school_workers")
async def get_school_workers(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
    current_user: User = Depends(admin_required)
):
    log_request(request, current_user)
    try:
        # Получаем всех работников школ
        query = User.filter(role="psychologist").prefetch_related('school')
        
        # Если есть поисковый запрос, добавляем условия поиска
        if search:
            search = search.lower()
            # Получаем всех работников, у которых есть совпадения
            workers = await query.all()
            matching_workers = []
            
            for worker in workers:
                # Проверяем совпадения по email, ФИО и названию школы
                if (worker.email and search in worker.email.lower()) or \
                   (worker.full_name and search in worker.full_name.lower()) or \
                   (worker.school and search in worker.school.name.lower()):
                    matching_workers.append(worker.id)
            
            # Фильтруем по найденным ID
            query = query.filter(id__in=matching_workers)
        
        # Применяем пагинацию
        workers = await query.offset(offset).limit(limit).all()
        
        result = []
        for worker in workers:
            result.append({
                "id": worker.id,
                "email": worker.email,
                "full_name": worker.full_name,
                "school_name": worker.school.name if worker.school else "Не указана"
            })
        
        # Считаем общее количество работников для пагинации
        total = await query.count()
        
        # Получаем общее количество работников (без учета поиска)
        total_all = await User.filter(role="psychologist").count()
        
        log_response({
            "message": "Список работников школ успешно получен",
            "total": total,
            "total_all": total_all,
            "search_query": search
        })
        
        return JSONResponse({"total": total, "total_all": total_all, "workers": result})
    except Exception as e:
        log_error(e, f"Error getting school workers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка работников школ"
        )
