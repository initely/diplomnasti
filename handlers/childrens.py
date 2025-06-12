from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.task import Task
from models.user import User, get_current_user, child_required, is_parent_of_child, parent_or_school_worker_required, update_child_details
from utils.logger import log_request, log_response, log_error
from models.result import Result
import logging
from datetime import datetime, timezone
import re

router = APIRouter()
templates = Jinja2Templates(directory="pages")

logger = logging.getLogger(__name__)

def log_request(request: Request, user: User):
    logger.info(f"Request: {request.method} {request.url.path} from user {user.id}")

def log_response(data: dict):
    logger.info(f"Response: {data}")

def log_error(error: Exception, context: str = ""):
    logger.error(f"Error: {str(error)} {context}")

def get_subject_name(subject: str) -> str:
    """Переводит английское название предмета на русский"""
    subjects = {
        "mathematics": "Математика",
        "russian_language": "Русский язык",
        "nature": "Окружающий мир",
        "chemistry": "Химия",
        "reading": "Чтение",
        "physical_education": "Физкультура",
        "art": "ИЗО",
        "music": "Музыка",
        "informatics": "Информатика",
        "astronomy": "Астрономия",
        "foreign_language": "Иностранный язык",
        "history": "История",
        "physics": "Физика",
        "social_science": "Обществознание"
    }
    return subjects.get(subject.lower(), subject)

def get_available_subjects(user):
    """
    Возвращает список предметов для ребёнка в зависимости от его класса.
    user: объект User с ролью 'child'
    """
    # Базовые предметы (ключ - английское название для БД, значение - русское название для отображения)
    subjects = {
        "mathematics": "Математика",
        "russian_language": "Русский язык",
        "nature": "Окружающий мир",
        "chemistry": "Химия",
        "reading": "Чтение",
        "physical_education": "Физкультура",
        "art": "ИЗО",
        "music": "Музыка",
        "informatics": "Информатика",
        "astronomy": "Астрономия"
    }

    # Получаем номер класса (ожидается строка типа "2А", "7", "8Б" и т.д.)
    current_class = user.current_class or ""
    # Извлекаем только число (номер класса)
    match = re.match(r"(\d+)", current_class)
    class_num = int(match.group(1)) if match else 1

    # Со 2 класса и выше — добавляем "Иностранный язык"
    if class_num >= 2:
        subjects["foreign_language"] = "Иностранный язык"
    # С 3 класса и выше — добавляем "История"
    if class_num >= 3:
        subjects["history"] = "История"
    # С 7 класса и выше — добавляем "Физика"
    if class_num >= 7:
        subjects["physics"] = "Физика"
    # С 8 класса и выше — добавляем "Обществознание"
    if class_num >= 8:
        subjects["social_science"] = "Обществознание"

    return subjects

@router.get("/subjects", response_class=HTMLResponse)
async def subjects(
    request: Request,
    current_user: User = Depends(child_required)
):
    log_request(request, current_user)
    try:
        available_subjects = get_available_subjects(current_user)
        log_response({
            "message": "Получен список доступных предметов",
            "subjects_count": len(available_subjects)
        })
        return templates.TemplateResponse(
            "children_pages/subjects_of_child.html",
            {
                "request": request,
                "current_user": current_user,
                "available_subjects": available_subjects
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при получении списка предметов")
        raise

@router.get("/subjects/{subject}", response_class=HTMLResponse)
async def subject_page(
    request: Request,
    subject: str,
    current_user: User = Depends(child_required)
):
    log_request(request, current_user)
    try:
        available_subjects = get_available_subjects(current_user)

        if subject not in available_subjects:
            log_error(Exception("Предмет не найден"), f"Subject: {subject}")
            raise HTTPException(status_code=404, detail="Предмет не найден или недоступен для вас")

        subject_name = available_subjects[subject]  # Русское название для отображения
        tasks = await Task.filter(subjects_name=subject).all()  # Используем английское название для поиска
        
        # Получаем список выполненных заданий
        completed_results = await Result.filter(user=current_user).prefetch_related('task')
        completed_tasks = [result.task.id for result in completed_results]
        
        log_response({
            "message": "Открыта страница предмета",
            "subject": subject,
            "subject_name": subject_name
        })
        
        return templates.TemplateResponse(
            "children_pages/tasks.html",
            {
                "request": request,
                "subject": subject,
                "subject_name": subject_name,
                "current_user": current_user,
                "tasks": tasks,
                "completed_tasks": completed_tasks
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы предмета")
        raise

@router.get("/child/{child_id}", response_class=HTMLResponse)
async def child_page(
    request: Request,
    child_id: str,
    current_user: User = Depends(get_current_user)
):
    log_request(request, current_user)
    try:
        # Получаем информацию о ребенке с предзагрузкой школы
        child = await User.get_or_none(id=child_id, role="child")
        if not child:
            log_error(Exception("Ребенок не найден"), f"Child ID: {child_id}")
            raise HTTPException(status_code=404, detail="Ребенок не найден")

        # Загружаем школу
        await child.fetch_related('school')
        
        # Убедимся, что языки загружены
        if not child.languages:
            child.languages = "[]"
            await child.save()

        # Получаем информацию о родителе
        parents = await User.filter(role="parent").all()
        parent_name = None
        for parent in parents:
            children_list = parent.get_children_list()
            if child.id in children_list:
                parent_name = parent.full_name
                break

        log_response({
            "message": "Открыта страница ребенка",
            "child_id": child_id,
            "child_name": child.full_name
        })
        
        return templates.TemplateResponse(
            "statistics/child.html",
            {
                "request": request,
                "child": child,
                "parent_name": parent_name,
                "current_user": current_user
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы ребенка")
        raise

@router.post("/update_child/{child_id}")
async def update_child(
    request: Request,
    child_id: str,
    child_data: dict,
    current_user: User = Depends(parent_or_school_worker_required)
):
    log_request(request, current_user)
    try:
        # Проверяем права доступа в зависимости от роли
        if current_user.role == "parent":
            # Для родителя проверяем, что это его ребенок
            if not await is_parent_of_child(current_user.id, child_id):
                log_error(Exception("Попытка обновления чужого ребенка"), f"Child ID: {child_id}")
                raise HTTPException(status_code=403, detail="Доступ запрещен")
        else:  # psychologist
            # Для работника школы проверяем, что ребенок из той же школы
            child = await User.get(id=child_id)
            if not child:
                raise HTTPException(status_code=404, detail="Ребенок не найден")
            
            # Загружаем школу ребенка
            await child.fetch_related('school')
            # Загружаем школу работника
            await current_user.fetch_related('school')
            
            if not child.school or not current_user.school or child.school.id != current_user.school.id:
                log_error(Exception("Попытка обновления ребенка из другой школы"), f"Child ID: {child_id}")
                raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        success = await update_child_details(child_id, child_data)
        if not success:
            raise HTTPException(status_code=500, detail="Ошибка при обновлении данных")
        
        log_response({
            "message": "Информация о ребенке обновлена",
            "child_id": child_id,
            "updated_by": current_user.role
        })
        
        return {"status": "success"}
    except Exception as e:
        log_error(e, "Ошибка при обновлении информации о ребенке")
        raise

@router.get("/my_statistics", response_class=HTMLResponse)
async def my_statistics(
    request: Request,
    current_user: User = Depends(child_required)
):
    log_request(request, current_user)
    try:
        log_response({
            "message": "Открыта страница статистики",
            "child_id": current_user.id
        })
        
        return templates.TemplateResponse(
            "children_pages/my_statistics.html",
            {
                "request": request,
                "current_user": current_user
            }
        )
    except Exception as e:
        log_error(e, "Ошибка при открытии страницы статистики")
        raise

def make_aware(dt):
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

@router.get("/get_my_statistics")
async def get_my_statistics(
    request: Request,
    offset: int = 0,
    limit: int = 10,
    search: str = "",
    sort_field: str = "started_at",
    sort_direction: str = "desc",
    current_user: User = Depends(child_required)
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

        # Получаем все результаты ребенка
        results = await Result.filter(user_id=current_user.id).prefetch_related('task')
        
        log_response({
            "message": "Получены результаты",
            "results_count": len(results)
        })
        
        # Фильтруем результаты по поисковому запросу
        if search:
            search = search.lower()
            results = [
                r for r in results if (
                    search in str(current_user.current_class).lower() or
                    (r.task and search in get_subject_name(r.task.subjects_name).lower())
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
            elif sort_field == "current_class":
                results.sort(key=lambda x: str(current_user.current_class), reverse=(sort_direction == "desc"))
            elif sort_field == "subject":
                results.sort(key=lambda x: get_subject_name(x.task.subjects_name) if x.task else "", reverse=(sort_direction == "desc"))
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
                if not result.task:
                    log_error(Exception("Задача не найдена"), f"result_id={result.id}")
                    continue
                    
                stat = {
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
