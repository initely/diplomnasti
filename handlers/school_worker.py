from typing import Any, Dict
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, school_worker_required, child_required, is_parent_of_child, parent_or_school_worker_required, update_child_details
from models.result import Result
from utils.logger import log_request, log_response, log_error
from models.task import Task
from datetime import datetime, timedelta, timezone
from handlers.childrens import get_subject_name

router = APIRouter()
templates = Jinja2Templates(directory="pages")

LOCAL_TIMEZONE = timezone(timedelta(hours=4))  # UTC+4

@router.get("/parents-database", response_class=HTMLResponse, )
async def parents_database(request: Request,  current_user: Dict[str, Any] = Depends(school_worker_required)):
    # Получаем название школы
    school = await current_user.school
    school_name = school.name if school else "Не указана"
    
    return templates.TemplateResponse(
        "school_worker_pages/parents_database.html", 
        {
            "request": request,
            "school_name": school_name
        }
    )

@router.get("/add-parent", response_class=HTMLResponse)
async def add_parent(request: Request,  current_user: Dict[str, Any] = Depends(school_worker_required)):
    # Здесь позже будет логика для добавления нового родителя
    return templates.TemplateResponse("school_worker_pages/add_parent.html", {"request": request})

@router.get("/children-database", response_class=HTMLResponse)
async def children_statistics(request: Request, current_user: Dict[str, Any] = Depends(school_worker_required)):
    # Получаем название школы
    school = await current_user.school
    school_name = school.name if school else "Не указана"
    
    return templates.TemplateResponse(
        "school_worker_pages/children_database.html",
        {
            "request": request,
            "school_name": school_name
        }
    )

@router.get("/children_statistics", response_class=HTMLResponse)
async def children_statistics_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    log_request(request, current_user)
    try:
        # Проверяем, что пользователь является работником школы
        if current_user.role != "psychologist":
            raise HTTPException(status_code=403, detail="Доступ запрещен")

        # Загружаем школу работника
        await current_user.fetch_related('school')
        if not current_user.school:
            raise HTTPException(status_code=403, detail="Школа не назначена")

        log_response({
            "message": "Открыта страница статистики детей",
            "school_id": current_user.school.id
        })

        return templates.TemplateResponse(
            "school_worker_pages/children_statistics.html",
            {
                "request": request,
                "current_user": current_user,
                "school_name": current_user.school.name
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы статистики детей")
        raise

@router.get("/get_parents")
async def get_parents(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
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

        # Получаем родителей только из школы текущего пользователя
        school = await current_user.school
        query = User.filter(role="parent", school=school)
        
        # Если есть поисковый запрос, добавляем условия поиска
        if search:
            search = search.lower()
            # Получаем всех родителей, у которых есть совпадения
            parents = await query.all()
            matching_parents = []
            
            for parent in parents:
                # Проверяем совпадения по родителю
                if (parent.email and search in parent.email.lower()) or \
                   (parent.full_name and search in parent.full_name.lower()):
                    matching_parents.append(parent.id)
                else:
                    # Проверяем совпадения по детям
                    children_ids = parent.get_children_list()
                    if children_ids:
                        children = await User.filter(id__in=children_ids).all()
                        for child in children:
                            # Проверяем совпадения по ФИО ребенка и классу
                            if (child.full_name and search in child.full_name.lower()) or \
                               (child.current_class and search in child.current_class.lower()):
                                matching_parents.append(parent.id)
                                break
            
            # Фильтруем по найденным ID
            query = query.filter(id__in=matching_parents)
        
        # Применяем пагинацию
        parents = await query.offset(offset).limit(limit).all()
        
        result = []
        for parent in parents:
            # Получаем список детей
            children_ids = parent.get_children_list()
            children = await User.filter(id__in=children_ids).all() if children_ids else []
            children_info = []
            for child in children:
                children_info.append({
                    "id": child.id,
                    "full_name": child.full_name,
                    "current_class": child.current_class
                })
            result.append({
                "id": parent.id,
                "login": parent.email,
                "full_name": parent.full_name,
                "children": children_info
            })
        
        # Считаем общее количество родителей в школе для пагинации
        total = await query.count()
        
        # Получаем общее количество родителей в школе (без учета поиска)
        total_all = await User.filter(role="parent", school=school).count()
        
        log_response({
            "message": "Список родителей успешно получен",
            "total": total,
            "total_all": total_all,
            "psychologist_id": current_user.id,
            "search_query": search
        })
        
        return JSONResponse({"total": total, "total_all": total_all, "parents": result})
    except Exception as e:
        log_error(e, f"Error getting parents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка родителей"
        )
    

@router.get("/get_children")
async def get_children(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
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

        # Получаем детей только из школы текущего пользователя
        school = await current_user.school
        query = User.filter(role="child", school=school)
        
        # Если есть поисковый запрос, добавляем условия поиска
        if search:
            search = search.lower()
            # Получаем всех детей, у которых есть совпадения
            children = await query.all()
            matching_children = []
            
            for child in children:
                # Получаем информацию о родителе через связь
                parents = await User.filter(role="parent").all()
                parent_name = None
                for parent in parents:
                    children_list = parent.get_children_list()
                    if child.id in children_list:
                        parent_name = parent.full_name
                        break
                
                # Проверяем совпадения по email, ФИО, классу и ФИО родителя
                if (child.email and search in child.email.lower()) or \
                   (child.full_name and search in child.full_name.lower()) or \
                   (child.current_class and search in child.current_class.lower()) or \
                   (parent_name and search in parent_name.lower()):
                    matching_children.append(child.id)
            
            # Фильтруем по найденным ID
            query = query.filter(id__in=matching_children)
        
        # Применяем пагинацию
        children = await query.offset(offset).limit(limit).all()
        
        result = []
        for child in children:
            # Получаем информацию о родителе через связь
            parents = await User.filter(role="parent").all()
            parent_name = None
            for parent in parents:
                children_list = parent.get_children_list()
                if child.id in children_list:
                    parent_name = parent.full_name
                    break
            
            result.append({
                "id": child.id,
                "login": child.email,
                "full_name": child.full_name,
                "current_class": child.current_class,
                "parent_name": parent_name
            })
        
        # Считаем общее количество детей в школе для пагинации
        total = await query.count()
        
        # Получаем общее количество детей в школе (без учета поиска)
        total_all = await User.filter(role="child", school=school).count()
        
        log_response({
            "message": "Список детей успешно получен",
            "total": total,
            "total_all": total_all,
            "psychologist_id": current_user.id,
            "search_query": search
        })
        
        return JSONResponse({"total": total, "total_all": total_all, "children": result})
    except Exception as e:
        log_error(e, f"Error getting children: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка детей"
        )



@router.get("/get_child_statistics/{child_id}")
async def get_child_statistics(
    request: Request,
    child_id: str,
    current_user: User = Depends(school_worker_required)
):
    log_request(request, current_user)
    try:
        # Проверяем права доступа
        if current_user.role == "parent":
            if not await is_parent_of_child(current_user.id, child_id):
                log_error(Exception("Попытка доступа к чужому ребенку"), f"Child ID: {child_id}")
                raise HTTPException(status_code=403, detail="Доступ запрещен")
        elif current_user.role == "psychologist":
            child = await User.get(id=child_id)
            if not child:
                raise HTTPException(status_code=404, detail="Ребенок не найден")
            
            # Загружаем школу ребенка
            await child.fetch_related('school')
            # Загружаем школу работника
            await current_user.fetch_related('school')
            
            if not child.school or not current_user.school or child.school.id != current_user.school.id:
                log_error(Exception("Попытка доступа к ребенку из другой школы"), f"Child ID: {child_id}")
                raise HTTPException(status_code=403, detail="Доступ запрещен")

        # Проверяем, есть ли результаты
        results = await Result.filter(user_id=child_id).prefetch_related('task').order_by('-created_at').all()
        
        # Если результатов нет, создаем тестовые данные
        if not results:
            await create_test_data(child_id)
            results = await Result.filter(user_id=child_id).prefetch_related('task').order_by('-created_at').all()
        
        # Форматируем результаты
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "subject": result.task.subjects_name if result.task else "Неизвестный предмет",
                "score": result.score,
                "time_seconds": result.time_seconds if result.time_seconds else None,
                "description": result.task.description if result.task else "",
                "confirmed": result.confirmed
            })
        
        log_response({
            "message": "Получена статистика ребенка",
            "child_id": child_id,
            "results_count": len(formatted_results)
        })
        
        return formatted_results
    except Exception as e:
        log_error(e, "Ошибка при получении статистики ребенка")
        raise

def make_aware(dt):
    if dt is None:
        return datetime.min.replace(tzinfo=LOCAL_TIMEZONE)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TIMEZONE)
    return dt

@router.get("/get_school_statistics")
async def get_school_statistics(
    request: Request,
    offset: int = 0,
    limit: int = 10,
    search: str = "",
    sort_field: str = "started_at",
    sort_direction: str = "desc",
    current_user: User = Depends(school_worker_required)
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

        # Получаем школу работника
        school = await current_user.school
        if not school:
            log_error(Exception("Школа не найдена"), f"User ID: {current_user.id}")
            return JSONResponse(
                status_code=404,
                content={"error": "Школа не найдена"}
            )

        # Получаем всех детей школы
        children = await User.filter(school_id=school.id, role="child")
        children_dict = {child.id: child for child in children}

        log_response({
            "message": "Получена информация о детях",
            "children_count": len(children)
        })

        # Получаем все результаты для всех детей школы
        results = await Result.filter(user_id__in=list(children_dict.keys())).prefetch_related('task')
        
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
                    "confirmed": result.confirmed,
                    "started_at": result.started_at.isoformat() if result.started_at else None
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
        log_error(e, "Ошибка при получении статистики")
        return JSONResponse(
            status_code=500,
            content={"error": f"Ошибка при получении статистики: {str(e)}"}
        )


