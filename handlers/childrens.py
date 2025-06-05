from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, child_required, is_parent_of_child, parent_or_school_worker_required, update_child_details
from models.result import Result
from utils.logger import log_request, log_response, log_error
from models.task import Task
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="pages")

def get_available_subjects(user):
    """
    Возвращает список предметов для ребёнка в зависимости от его класса.
    user: объект User с ролью 'child'
    """
    # Базовые предметы
    subjects = {
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

    # Получаем номер класса (ожидается строка типа "2А", "7", "8Б" и т.д.)
    current_class = user.current_class or ""
    # Извлекаем только число (номер класса)
    import re
    match = re.match(r"(\d+)", current_class)
    class_num = int(match.group(1)) if match else 1

    # Со 2 класса и выше — добавляем "Иностранный язык"
    if class_num >= 2:
        subjects["foreign-language"] = "Иностранный язык"
    # С 3 класса и выше — добавляем "История"
    if class_num >= 3:
        subjects["history"] = "История"
    # С 7 класса и выше — добавляем "Физика"
    if class_num >= 7:
        subjects["physics"] = "Физика"
    # С 8 класса и выше — добавляем "Обществознание"
    if class_num >= 8:
        subjects["social-science"] = "Обществознание"

    return subjects

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

        subject_name = available_subjects[subject]
        
        log_response({
            "message": "Открыта страница предмета",
            "subject": subject,
            "subject_name": subject_name
        })
        
        return templates.TemplateResponse(
            "children_pages/subject.html",
            {
                "request": request,
                "subject": subject,
                "subject_name": subject_name,
                "current_user": current_user
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
                "created_at": getattr(result, 'created_at', datetime.now()).strftime("%d.%m.%Y %H:%M"),
                "details": result.task.name if result.task else ""
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
