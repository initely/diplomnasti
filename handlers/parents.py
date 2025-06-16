from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, parent_required, is_parent_of_child, get_children_for_parent, parent_or_school_worker_required
from models.school import School
from models.result import Result
from utils.logger import log_request, log_response, log_error
from datetime import datetime, timezone, timedelta
from handlers.childrens import get_subject_name

router = APIRouter()
templates = Jinja2Templates(directory="pages")

LOCAL_TIMEZONE = timezone(timedelta(hours=4))  # UTC+4

def make_aware(dt):
    if dt is None:
        return datetime.min.replace(tzinfo=LOCAL_TIMEZONE)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TIMEZONE)
    return dt

@router.get("/children-profiles", response_class=HTMLResponse)
async def children_profiles(
    request: Request,
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        # Получаем список детей
        children = await get_children_for_parent(current_user.id)
        
        # Получаем список всех школ
        schools = await School.all()
        schools_list = [{"id": school.id, "name": school.name} for school in schools]
        
        log_response({
            "message": "Открыта страница профилей детей",
            "children_count": len(children)
        })
        
        return templates.TemplateResponse(
            "parent_pages/children_profiles.html",
            {
                "request": request,
                "current_user": current_user,
                "children": children,
                "schools": schools_list
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы профилей детей")
        raise

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

@router.get("/get_child_statistics")
async def get_child_statistics(
    request: Request,
    offset: int = 0,
    limit: int = 10,
    search: str = "",
    sort_field: str = "started_at",
    sort_direction: str = "desc",
    current_user: User = Depends(parent_required)
):
    log_request(request, current_user)
    try:
        log_response({
            "message": "Начало обработки запроса статистики",
            "params": {
                "offset": offset,
                "limit": limit,
                "search": search,
                "sort_field": sort_field,
                "sort_direction": sort_direction
            }
        })

        # Получаем список детей родителя
        children_ids = current_user.get_children_list()
        if not children_ids:
            log_error(Exception("Нет привязанных детей"), f"Parent ID: {current_user.id}")
            return JSONResponse(
                status_code=404,
                content={"error": "У вас нет привязанных детей"}
            )

        log_response({
            "message": "Получены ID детей",
            "children_ids": children_ids
        })

        # Получаем всех детей родителя
        children = await User.filter(id__in=children_ids)
        children_dict = {child.id: child for child in children}

        log_response({
            "message": "Получена информация о детях",
            "children_count": len(children)
        })

        # Получаем все результаты для всех детей родителя
        results = await Result.filter(user_id__in=children_ids).prefetch_related('task')
        
        log_response({
            "message": "Получены результаты",
            "results_count": len(results)
        })
        
        # Фильтруем результаты по поисковому запросу
        if search:
            search = search.lower()
            results = [
                r for r in results if (
                    search in children_dict[r.user_id].full_name.lower() or
                    search in str(children_dict[r.user_id].current_class).lower() or
                    (r.task and search in r.task.subjects_name.lower())
                )
            ]
            log_response({
                "message": "Отфильтрованы результаты",
                "filtered_count": len(results)
            })
        
        # Сортируем результаты
        try:
            if sort_field == "started_at":
                results.sort(key=lambda x: make_aware(x.started_at), reverse=(sort_direction == "desc"))
            elif sort_field == "score":
                results.sort(key=lambda x: x.score or 0, reverse=(sort_direction == "desc"))
            elif sort_field == "time_seconds":
                results.sort(key=lambda x: x.time_seconds or 0, reverse=(sort_direction == "desc"))
            elif sort_field == "confirmed":
                results.sort(key=lambda x: x.confirmed, reverse=(sort_direction == "desc"))
            elif sort_field == "full_name":
                results.sort(key=lambda x: children_dict[x.user_id].full_name, reverse=(sort_direction == "desc"))
            elif sort_field == "current_class":
                results.sort(key=lambda x: str(children_dict[x.user_id].current_class), reverse=(sort_direction == "desc"))
            elif sort_field == "subject":
                results.sort(key=lambda x: x.task.subjects_name if x.task else "", reverse=(sort_direction == "desc"))
            elif sort_field == "description":
                results.sort(key=lambda x: x.task.description if x.task else "", reverse=(sort_direction == "desc"))
        except Exception as e:
            log_error(e, f"Ошибка при сортировке результатов: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Ошибка при сортировке результатов: {str(e)}"}
            )
        
        log_response({
            "message": "Отсортированы результаты",
            "sort_field": sort_field,
            "sort_direction": sort_direction
        })
        
        # Применяем пагинацию
        total = len(results)
        paginated_results = results[offset:offset + limit]
        
        log_response({
            "message": "Применена пагинация",
            "total": total,
            "offset": offset,
            "limit": limit,
            "paginated_count": len(paginated_results)
        })
        
        # Форматируем результаты для ответа
        statistics = []
        for result in paginated_results:
            try:
                child = children_dict[result.user_id]
                if not result.task:
                    log_error(Exception("Задача не найдена"), f"result_id={result.id}")
                    continue
                    
                stat = {
                    "id": result.id,
                    "child_id": child.id,
                    "full_name": child.full_name,
                    "current_class": child.current_class,
                    "subject": get_subject_name(result.task.subjects_name),
                    "score": result.score,
                    "time_seconds": result.time_seconds,
                    "description": result.task.description,
                    "confirmed": result.confirmed
                }
                statistics.append(stat)
                log_response({
                    "message": "Добавлен результат в статистику",
                    "result_id": result.id,
                    "stat": stat
                })
            except Exception as e:
                log_error(e, f"Ошибка при обработке результата result_id={result.id}")
                continue
        
        response_data = {
            "total": total,
            "statistics": statistics
        }
        
        log_response({
            "message": "Подготовлен ответ",
            "response_data": response_data
        })
        
        return JSONResponse(content=response_data)
    except Exception as e:
        log_error(e, "Ошибка при получении статистики детей")
        return JSONResponse(
            status_code=500,
            content={"error": f"Ошибка при получении статистики: {str(e)}"}
        )

@router.get("/statistics/{result_id}", response_class=HTMLResponse)
async def result_details(
    request: Request,
    result_id: int,
    current_user: User = Depends(parent_or_school_worker_required)
):
    log_request(request, current_user)
    try:
        # Получаем результат
        result = await Result.filter(id=result_id).prefetch_related('task', 'user', 'confirmed_by').first()
        if not result:
            raise HTTPException(status_code=404, detail="Результат не найден")

        # Проверяем права доступа в зависимости от роли
        if current_user.role == "parent":
            # Для родителя проверяем, что результат принадлежит его ребенку
            if not await is_parent_of_child(current_user.id, result.user_id):
                raise HTTPException(status_code=403, detail="Доступ запрещен")
        else:  # psychologist
            # Для работника школы проверяем, что ребенок из той же школы
            child = await User.get(id=result.user_id)
            if not child:
                raise HTTPException(status_code=404, detail="Ребенок не найден")
            
            # Загружаем школу ребенка
            await child.fetch_related('school')
            # Загружаем школу работника
            await current_user.fetch_related('school')
            
            if not child.school or not current_user.school or child.school.id != current_user.school.id:
                log_error(Exception("Попытка доступа к результату ребенка из другой школы"), f"Child ID: {result.user_id}")
                raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        # Получаем информацию о ребенке
        child = await User.get(id=result.user_id)
        
        log_response({
            "message": "Открыта страница деталей результата",
            "result_id": result_id,
            "child_id": child.id
        })
        
        return templates.TemplateResponse(
            "parent_pages/result_details.html",
            {
                "request": request,
                "result": result,
                "child": child,
                "current_user": current_user,
                "get_subject_name": get_subject_name
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы деталей результата")
        raise

@router.get("/children-profiles")
async def children_profiles(request: Request, current_user: User = Depends(get_current_user)):
    try:
        # Получаем список детей для текущего пользователя
        children = await get_children_for_parent(current_user.id)
        
        # Получаем список всех школ
        schools = await School.all()
        schools_list = [{"id": school.id, "name": school.name} for school in schools]
        
        # Логируем ответ
        print(f"DEBUG: Получены данные о {len(children)} детях")
        
        return templates.TemplateResponse(
            "parent_pages/children_profiles.html",
            {
                "request": request,
                "current_user": current_user,
                "children": children,
                "schools": schools_list
            }
        )
    except Exception as e:
        print(f"Ошибка при получении данных: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
