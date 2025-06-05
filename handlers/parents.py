from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, parent_required, is_parent_of_child, get_children_for_parent
from models.school import School
from models.result import Result
from utils.logger import log_request, log_response, log_error

router = APIRouter()
templates = Jinja2Templates(directory="pages")

@router.get("/children-profiles", response_class=HTMLResponse)
async def children_profiles(
    request: Request,
    current_user: User = Depends(parent_required)
):
    return templates.TemplateResponse(
        "parent_pages/children_profiles.html",
        {
            "request": request,
            "current_user": current_user
        }
    )

@router.get("/add-child", response_class=HTMLResponse)
async def add_child(
    request: Request,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        log_response({"message": "Открыта страница добавления ребенка"})
        return templates.TemplateResponse(
            "parent_pages/add_child.html",
            {
                "request": request,
                "current_user": current_user
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы добавления ребенка")
        raise

@router.get("/statistics", response_class=HTMLResponse)
async def parent_statistics(
    request: Request,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        # Проверяем, есть ли у родителя привязанные дети
        children_ids = current_user.get_children_list()
        if not children_ids:
            raise HTTPException(status_code=404, detail="У вас нет привязанных детей")

        log_response({
            "message": "Открыта страница статистики детей",
            "parent_id": current_user.id
        })

        return templates.TemplateResponse(
            "parent_pages/child_statistics.html",
            {
                "request": request,
                "current_user": current_user
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы статистики детей")
        raise

@router.get("/get_childs")
async def get_childs(
    request: Request,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        children = await get_children_for_parent(current_user.id)
        log_response({
            "message": "Получен список детей",
            "children_count": len(children)
        })
        return children
    except Exception as e:
        log_error(e, "Ошибка при получении списка детей")
        raise

@router.get("/child_subjects/{child_uid}")
async def child_subjects(
    child_uid: str,
    request: Request,
    current_user: User = Depends(parent_required)
):
    # Проверка, что ребенок принадлежит этому родителю
    if not await is_parent_of_child(current_user.id, child_uid):
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    return templates.TemplateResponse(
        "parent_pages/child_subjects.html",
        {
            "request": request,
            "current_user": current_user,
            "child_uid": child_uid
        }
    )

@router.get("/get_child_info/{child_uid}")
async def get_child_info(
    request: Request,
    child_uid: str,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        if not await is_parent_of_child(current_user.id, child_uid):
            log_error(Exception("Попытка доступа к чужому ребенку"), f"Child ID: {child_uid}")
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        child = await User.get(id=child_uid)
        
        school_name = None
        if child.school_id:
            school = await child.school
            school_name = school.name if school else None
        
        response_data = {
            "school": school_name,
            "gender": child.gender,
            "current_class": child.current_class,
            "physical_group": child.physical_group,
            "languages": child.get_languages(),
            "email": child.email
        }
        
        log_response({
            "message": "Получена информация о ребенке",
            "child_id": child_uid
        })
        
        return response_data
    except Exception as e:
        log_error(e, "Ошибка при получении информации о ребенке")
        raise

@router.get("/child_statistics", response_class=HTMLResponse)
async def child_statistics_page(
    request: Request,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        # Получаем список детей родителя
        children_ids = current_user.get_children_list()
        if not children_ids:
            raise HTTPException(status_code=404, detail="У вас нет привязанных детей")

        # Получаем первого ребенка (в будущем можно добавить выбор ребенка)
        child = await User.get(id=children_ids[0])
        if not child:
            raise HTTPException(status_code=404, detail="Ребенок не найден")

        log_response({
            "message": "Открыта страница статистики ребенка",
            "child_id": child.id
        })

        return templates.TemplateResponse(
            "parent_pages/child_statistics.html",
            {
                "request": request,
                "current_user": current_user,
                "child": child
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы статистики ребенка")
        raise

@router.get("/get_child_statistics")
async def get_child_statistics(
    request: Request,
    offset: int = 0,
    limit: int = 10,
    search: str = "",
    sort_field: str = "created_at",
    sort_direction: str = "desc",
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        # Получаем список детей родителя
        children_ids = current_user.get_children_list()
        if not children_ids:
            raise HTTPException(status_code=404, detail="У вас нет привязанных детей")

        # Получаем всех детей родителя
        children = await User.filter(id__in=children_ids)
        children_dict = {child.id: child for child in children}

        # Получаем все результаты для всех детей родителя
        results = await Result.filter(user_id__in=children_ids).prefetch_related('task')
        
        # Фильтруем результаты по поисковому запросу
        if search:
            search = search.lower()
            results = [
                r for r in results if (
                    search in children_dict[r.user_id].full_name.lower() or
                    search in str(children_dict[r.user_id].current_class).lower() or
                    search in r.task.subjects_name.lower()
                )
            ]
        
        # Сортируем результаты
        if sort_field == "created_at":
            results.sort(key=lambda x: x.created_at, reverse=(sort_direction == "desc"))
        elif sort_field == "score":
            results.sort(key=lambda x: x.score, reverse=(sort_direction == "desc"))
        elif sort_field == "time_seconds":
            results.sort(key=lambda x: x.time_seconds or 0, reverse=(sort_direction == "desc"))
        elif sort_field == "confirmed":
            results.sort(key=lambda x: x.confirmed, reverse=(sort_direction == "desc"))
        elif sort_field == "full_name":
            results.sort(key=lambda x: children_dict[x.user_id].full_name, reverse=(sort_direction == "desc"))
        elif sort_field == "current_class":
            results.sort(key=lambda x: str(children_dict[x.user_id].current_class), reverse=(sort_direction == "desc"))
        elif sort_field == "subject":
            results.sort(key=lambda x: x.task.subjects_name, reverse=(sort_direction == "desc"))
        elif sort_field == "description":
            results.sort(key=lambda x: x.task.description or "", reverse=(sort_direction == "desc"))
        
        # Применяем пагинацию
        total = len(results)
        paginated_results = results[offset:offset + limit]
        
        # Форматируем результаты для ответа
        statistics = []
        for result in paginated_results:
            child = children_dict[result.user_id]
            statistics.append({
                "child_id": child.id,
                "full_name": child.full_name,
                "current_class": child.current_class,
                "subject": result.task.subjects_name,
                "score": result.score,
                "max_score": result.task.max_score,
                "time_seconds": result.time_seconds,
                "description": result.task.description,
                "confirmed": result.confirmed,
                "created_at": result.created_at.isoformat()
            })
        
        log_response({
            "message": "Получена статистика детей",
            "total": total,
            "offset": offset,
            "limit": limit
        })
        
        return {
            "total": total,
            "statistics": statistics
        }
    except Exception as e:
        log_error(e, "Ошибка при получении статистики детей")
        raise
