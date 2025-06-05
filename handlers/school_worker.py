from typing import Any, Dict
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, school_worker_required, child_required, is_parent_of_child, parent_or_school_worker_required, update_child_details
from models.result import Result
from utils.logger import log_request, log_response, log_error
from models.task import Task
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="pages")



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

async def create_test_data(child_id: str):
    """Создает тестовые данные для демонстрации статистики"""
    try:
        # Создаем тестовые задания
        tasks = [
            await Task.create(
                subjects_name="Математика",
                name="Контрольная работа №1",
                type="score",
                max_score=5
            ),
            await Task.create(
                subjects_name="Русский язык",
                name="Диктант",
                type="score",
                max_score=5
            ),
            await Task.create(
                subjects_name="Физкультура",
                name="Бег 100 метров",
                type="time",
                max_score=None
            )
        ]

        # Создаем результаты для каждого задания
        for i, task in enumerate(tasks):
            # Создаем несколько результатов с разными датами
            for days_ago in range(3):
                date = datetime.now() - timedelta(days=days_ago)
                await Result.create(
                    user_id=child_id,
                    task=task,
                    score=4.5 if task.type == "score" else 12.5,  # 4.5 балла или 12.5 секунд
                    time_seconds=12.5 if task.type == "time" else None,
                    created_at=date
                )

        return True
    except Exception as e:
        log_error(e, "Ошибка при создании тестовых данных")
        return False

@router.get("/statistics", response_class=HTMLResponse)
async def statistics(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse(
        "statistics_page/index.html",
        {
            "request": request,
            "current_user": current_user
        }
    )

@router.get("/get_child_statistics/{child_id}")
async def get_child_statistics(
    request: Request,
    child_id: str,
    current_user: User = Depends(get_current_user)
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
                "max_score": result.task.max_score if result.task else 0,
                "time_seconds": result.time_seconds if result.time_seconds else None,
                "details": result.task.description if result.task else "",
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

@router.get("/get_school_statistics")
async def get_school_statistics(
    request: Request,
    offset: int = 0,
    limit: int = 10,
    search: str = "",
    sort_field: str = "created_at",
    sort_direction: str = "desc",
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

        # Получаем всех детей из школы
        children = await User.filter(
            role="child",
            school=current_user.school
        ).prefetch_related('school')

        # Получаем все результаты для детей
        statistics = []
        for child in children:
            # Получаем все результаты ребенка
            results = await Result.filter(user_id=child.id).prefetch_related('task')
            
            for result in results:
                if not result.task:
                    continue
                    
                statistics.append({
                    'child_id': child.id,
                    'full_name': child.full_name,
                    'current_class': child.current_class,
                    'subject': result.task.subjects_name,
                    'score': result.score,
                    'max_score': result.task.max_score,
                    'time_seconds': result.time_seconds,
                    'details': result.task.description,
                    'confirmed': result.confirmed,
                    'created_at': result.created_at
                })

        # Фильтруем по поисковому запросу
        if search:
            search = search.lower()
            statistics = [stat for stat in statistics if 
                search in stat['full_name'].lower() or 
                search in (stat['current_class'] or "").lower() or
                search in stat['subject'].lower()]

        # Сортируем данные
        if sort_field == 'score':
            statistics.sort(key=lambda x: float(x['score']), reverse=(sort_direction == 'desc'))
        elif sort_field == 'time_seconds':
            statistics.sort(key=lambda x: x['time_seconds'] or 0, reverse=(sort_direction == 'desc'))
        elif sort_field == 'confirmed':
            statistics.sort(key=lambda x: x['confirmed'], reverse=(sort_direction == 'desc'))
        else:
            statistics.sort(key=lambda x: x[sort_field] or '', reverse=(sort_direction == 'desc'))

        # Применяем пагинацию
        total = len(statistics)
        paginated_stats = statistics[offset:offset + limit]

        log_response({
            "message": "Получена статистика школы",
            "total": total,
            "offset": offset,
            "limit": limit,
            "sort_field": sort_field,
            "sort_direction": sort_direction
        })

        return {
            "statistics": paginated_stats,
            "total": total
        }
    except Exception as e:
        log_error(e, "Ошибка при получении статистики школы")
        raise


