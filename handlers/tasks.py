from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
import json
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import os
from handlers.childrens import get_available_subjects
from models.user import User, child_required, parent_required, is_parent_of_child, parent_or_school_worker_required
from models.task import Task
from models.result import Result
from models.answer import Answer
from models.rest_break_time import RestBreakTime
from utils.logger import log_error, log_request, log_response
from jinja2 import Environment

router = APIRouter()

# Pydantic модель для Task
class TaskModel(BaseModel):
    id: int
    name: str
    subjects_name: str

# Модель для ответа
class AnswerModel(BaseModel):
    answer: str  

# Модель для хранения информации о выполнении задания
class TaskSession(BaseModel):
    start_time: datetime
    pause_time: Optional[datetime] = None
    total_time: timedelta = timedelta(0)
    is_paused: bool = False
    is_break: bool = False
    user_id: int
    task_id: int
    score: int = 0
    task: TaskModel
    pauses: list[tuple[datetime, datetime]] = []
    last_update_time: Optional[datetime] = None

# Хранилище активных сессий
active_sessions: Dict[str, TaskSession] = {}

# Константы
BREAK_DURATION = timedelta(minutes=1)
MAX_WORK_TIME = {
    1: timedelta(minutes=1),    # 1 класс
    2: timedelta(hours=1.5),  # 2 класс
    3: timedelta(hours=2),    # 3 класс
    4: timedelta(hours=2),    # 4 класс
    5: timedelta(hours=2.5),  # 5 класс
    6: timedelta(hours=2.5),  # 6 класс
    7: timedelta(hours=3),    # 7 класс
    8: timedelta(hours=3),    # 8 класс
    9: timedelta(hours=3),    # 9 класс
    10: timedelta(hours=3),   # 10 класс
    11: timedelta(hours=3),   # 11 класс
}

# Определяем локальный часовой пояс
LOCAL_TIMEZONE = timezone(timedelta(hours=4))  # UTC+4

async def check_and_update_break_time(current_user: User) -> bool:
    """Проверяет и обновляет время доступа к заданиям"""
    now = datetime.now(LOCAL_TIMEZONE)  # Получаем время в локальном часовом поясе
    
    # Получаем или создаем запись о перерыве для пользователя
    rest_break = await RestBreakTime.get_or_none(user=current_user)
    if not rest_break:

        print(f"УСТАНАВЛИВАЮ ВРЕМЯ ACCESS TIME: {now}")
        rest_break = await RestBreakTime.create(
            user=current_user,
            access_time=now,
            last_break_time=now,
            total_work_time=0
        )
    print(f"ИТАК now: {now}")
    # Если текущее время меньше времени доступа, значит перерыв еще не закончился
    if now < rest_break.access_time:
        print(f"йоу тебе надо еще отдохнуть {now} < {rest_break.access_time}")
        return False
    
    return True

async def update_break_time_after_task(current_user: User, task_time: float):
    """Обновляет время перерыва после выполнения задания"""
    now = datetime.now(LOCAL_TIMEZONE)  # Получаем время в локальном часовом поясе
    
    # Получаем запись о перерыве
    rest_break = await RestBreakTime.get_or_none(user=current_user)
    if not rest_break:
        rest_break = await RestBreakTime.create(
            user=current_user,
            access_time=now,
            last_break_time=now,
            total_work_time=0
        )
    
    # Обновляем общее время работы
    rest_break.total_work_time += task_time
    
    # Получаем максимальное время работы для класса
    try:
        grade = int(current_user.current_class[0]) if current_user.current_class else 1
        max_work_time = MAX_WORK_TIME[grade].total_seconds()
    except (ValueError, IndexError, KeyError):
        grade = 1
        max_work_time = MAX_WORK_TIME[grade].total_seconds()
    
    # Если превышено максимальное время работы, устанавливаем новый перерыв
    if rest_break.total_work_time >= max_work_time:
        rest_break.access_time = now + BREAK_DURATION
        rest_break.last_break_time = now
        rest_break.total_work_time = 0
    
    await rest_break.save()

@router.post("/start_task/{task_id}")
async def start_task(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    
    # Проверяем время доступа к заданиям
    if not await check_and_update_break_time(current_user):
        raise HTTPException(
            status_code=403,
            detail="Сейчас время перерыва. Попробуйте позже."
        )
    
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id in active_sessions:
        log_error(Exception("Задание уже выполняется"), f"session_id={session_id}")
        raise HTTPException(status_code=400, detail="Задание уже выполняется")
    
    # Проверяем существование задания
    task = await Task.get_or_none(id=task_id)
    if not task:
        log_error(Exception("Задание не найдено"), f"task_id={task_id}")
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, выполнено ли задание
    existing_result = await Result.filter(user=current_user, task=task).first()
    if existing_result:
        log_error(Exception("Задание уже выполнено"), f"task_id={task_id}")
        raise HTTPException(status_code=400, detail="Задание уже выполнено")
    
    # Получаем класс ученика из current_user
    grade = int(current_user.current_class[0]) if current_user.current_class else 1
    
    # Создаем Pydantic модель для Task
    task_model = TaskModel(
        id=task.id,
        name=task.description,
        subjects_name=task.subjects_name,
    )
    
    # Создаем сессию с временем в локальном часовом поясе
    active_sessions[session_id] = TaskSession(
        start_time=datetime.now(LOCAL_TIMEZONE),
        user_id=current_user.id,
        task_id=task_id,
        task=task_model
    )
    
    log_response({
        "status": "success",
        "message": "Задание начато",
        "session_id": session_id,
        "grade": grade
    })
    return {"status": "success", "message": "Задание начато"}

@router.post("/pause_task/{task_id}")
async def pause_task(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        log_error(Exception("Задание не найдено"), f"session_id={session_id}")
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    if not session.is_paused:
        session.pause_time = datetime.now(LOCAL_TIMEZONE)
        session.is_paused = True
        session.total_time += session.pause_time - session.start_time
    
    log_response({
        "status": "success",
        "message": "Задание приостановлено",
        "session_id": session_id,
        "total_time": session.total_time.total_seconds()
    })
    return {"status": "success", "message": "Задание приостановлено"}

@router.post("/resume_task/{task_id}")
async def resume_task(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        log_error(Exception("Задание не найдено"), f"session_id={session_id}")
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    if session.is_paused:
        if session.pause_time:
            session.pauses.append((session.pause_time, datetime.now(LOCAL_TIMEZONE)))
        session.start_time = datetime.now(LOCAL_TIMEZONE)
        session.is_paused = False
        session.pause_time = None
        session.last_update_time = datetime.now(LOCAL_TIMEZONE)  # Обновляем время последнего обновления
    
    log_response({
        "status": "success",
        "message": "Задание возобновлено",
        "session_id": session_id,
        "pauses_count": len(session.pauses)
    })
    return {"status": "success", "message": "Задание возобновлено"}

async def finish_task_internal(session_id: str, current_user: User, task_id: int) -> dict:
    """Внутренняя функция для завершения задания"""
    session = active_sessions[session_id]
    end_time = datetime.now(LOCAL_TIMEZONE)
    
    total_time = session.total_time
    if not session.is_paused:
        total_time += end_time - session.start_time
    
    # Подсчет баллов в зависимости от времени
    time_minutes = total_time.total_seconds() / 60
    score = max(1, 10 - int(time_minutes))  # От 10 до 1 балла
    
    result = await Result.create(
        user=current_user,
        task_id=task_id,
        score=score,
        time_seconds=total_time.total_seconds(),
        started_at=session.start_time,
        ended_at=end_time,
        confirmed=True  # Автоматически подтверждаем результат
    )
    
    # Обновляем время перерыва после выполнения задания
    #await update_break_time_after_task(current_user, total_time.total_seconds())
    
    del active_sessions[session_id]
    
    response_data = {
        "status": "success", 
        "message": "Задание завершено",
        "result": {
            "score": score,
            "time_seconds": total_time.total_seconds(),
            "started_at": session.start_time,
            "ended_at": end_time
        }
    }
    
    log_response({
        "status": "success",
        "message": "Задание завершено",
        "session_id": session_id,
        "score": score,
        "time_seconds": total_time.total_seconds(),
        "pauses_count": len(session.pauses)
    })
    
    return response_data

@router.post("/check_answer/{task_id}")
async def check_answer(
    request: Request,
    task_id: int,
    answer_data: AnswerModel = Body(...),
    current_user: User = Depends(child_required)
):
    log_request(request, current_user)
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        log_error(Exception("Задание не найдено"), f"session_id={session_id}")
        raise HTTPException(status_code=404, detail="Игровая сессия не найдена")
    
    # Получаем задание и правильный ответ
    task = await Task.get_or_none(id=task_id)
    if not task:
        log_error(Exception("Задание не найдено"), f"task_id={task_id}")
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    correct_answer = await Answer.filter(task=task).first()
    if not correct_answer:
        log_error(Exception("Не найден ответ для задания"), f"task_id={task_id}")
        raise HTTPException(status_code=500, detail="Не найден ответ для задания")
    
    # Проверяем ответ
    is_correct = str(answer_data.answer.lower()) == correct_answer.answer
    
    if is_correct:
        # Если ответ правильный, обновляем время работы перед завершением
        session = active_sessions[session_id]
        current_time = datetime.now(LOCAL_TIMEZONE)
        
        # Обновляем общее время работы
        if session.last_update_time:
            time_diff = (current_time - session.last_update_time).total_seconds()
            if time_diff > 0:
                rest_break = await RestBreakTime.get_or_none(user=current_user)
                if rest_break:
                    rest_break.total_work_time += time_diff
                    await rest_break.save()
        
        # Завершаем задание
        response_data = await finish_task_internal(session_id, current_user, task_id)
        response_data["is_correct"] = True
        return response_data
    
    log_response({
        "status": "success",
        "is_correct": is_correct,
        "message": "Неправильно, попробуйте еще раз",
        "correct_answer": correct_answer.answer,
        "user_answer": str(answer_data.answer),
        "session_id": session_id
    })
    
    return {
        "status": "success",
        "is_correct": is_correct,
        "message": "Неправильно, попробуйте еще раз"
    }

@router.websocket("/ws/task/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int, current_user: User = Depends(child_required)):
    await websocket.accept()
    
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        log_error(Exception("Задание не найдено"), f"session_id={session_id}")
        await websocket.close(code=1000, reason="Задание не найдено")
        return
    
    session = active_sessions[session_id]
    try:
        grade = int(current_user.current_class[0]) if current_user.current_class else 1
        if grade not in MAX_WORK_TIME:
            grade = 1
    except (ValueError, IndexError):
        grade = 1
    
    # Получаем или создаем запись о перерыве
    rest_break = await RestBreakTime.get_or_none(user=current_user)
    if not rest_break:
        now = datetime.now(LOCAL_TIMEZONE)
        rest_break = await RestBreakTime.create(
            user=current_user,
            access_time=now,
            last_break_time=now,
            total_work_time=0
        )
    
    # Если сессия была на паузе, возобновляем её
    if session.is_paused:
        if session.pause_time:
            session.pauses.append((session.pause_time, datetime.now(LOCAL_TIMEZONE)))
        session.start_time = datetime.now(LOCAL_TIMEZONE)
        session.is_paused = False
        session.pause_time = None
        session.last_update_time = datetime.now(LOCAL_TIMEZONE)
        
        log_response({
            "status": "info",
            "message": "Сессия автоматически возобновлена после переподключения",
            "session_id": session_id
        })
    
    log_response({
        "status": "success",
        "message": "WebSocket подключение установлено",
        "session_id": session_id,
        "grade": grade,
        "is_paused": session.is_paused
    })
    
    try:
        while True:
            try:
                # Проверяем существование сессии
                if session_id not in active_sessions:
                    log_response({
                        "status": "info",
                        "message": "Сессия завершена, закрываем WebSocket",
                        "session_id": session_id
                    })
                    break
                
                current_time = datetime.now(LOCAL_TIMEZONE)
                
                # Проверяем, не закончился ли перерыв
                if session.is_break and current_time >= rest_break.access_time:
                    print(f"ПЕРЕРЫВ ЗАКОНЧИЛСЯ у {session_id}")
                    session.is_break = False
                    session.is_paused = False
                    session.pause_time = None
                    session.start_time = current_time
                    session.last_update_time = current_time
                    
                    try:
                        await websocket.send_json({
                            "type": "resume",
                            "message": "Перерыв закончился! Можно продолжать работу.",
                            "total_work_time": rest_break.total_work_time
                        })
                    except WebSocketDisconnect:
                        break
                
                if not session.is_paused:
                    # Получаем время работы над текущим заданием
                    session_start_time = session.start_time.astimezone(LOCAL_TIMEZONE)
                    current_task_time = current_time - session_start_time + session.total_time
                    
                    # Обновляем общее время работы только если прошла секунда с последнего обновления
                    if not session.last_update_time or (current_time - session.last_update_time).total_seconds() >= 1:
                        try:
                            # Вычисляем разницу во времени с последнего обновления
                            if session.last_update_time:
                                time_diff = (current_time - session.last_update_time).total_seconds()
                            else:
                                time_diff = 1  # Для первого обновления
                            
                            # Обновляем общее время работы
                            rest_break.total_work_time += time_diff
                            await rest_break.save()
                            
                            # Сохраняем время последнего обновления
                            session.last_update_time = current_time
                            
                            log_response({
                                "status": "debug",
                                "message": f"Обновление времени работы от задачи {task_id}",
                                "time_diff": time_diff,
                                "total_work_time": rest_break.total_work_time
                            })
                        except Exception as e:
                            log_error(e, f"Ошибка при сохранении времени работы: {str(e)}")
                            continue
                    
                    # Проверяем, не превышено ли максимальное время работы
                    if rest_break.total_work_time >= MAX_WORK_TIME[grade].total_seconds():
                        try:
                            session.is_break = True
                            session.is_paused = True
                            session.pause_time = current_time
                            
                            # Устанавливаем новое время доступа
                            rest_break.access_time = current_time + BREAK_DURATION
                            rest_break.last_break_time = current_time
                            rest_break.total_work_time = 0
                            await rest_break.save()
                            
                            try:
                                print(f"ПЕРЕРЫВ у {session_id}")
                                await websocket.send_json({
                                    "type": "break",
                                    "message": "Время для перерыва!",
                                    "break_duration": BREAK_DURATION.total_seconds(),
                                    "total_work_time": rest_break.total_work_time,
                                    "max_work_time": MAX_WORK_TIME[grade].total_seconds()
                                })
                            except WebSocketDisconnect:
                                break
                        except Exception as e:
                            log_error(e, f"Ошибка при установке перерыва: {str(e)}")
                            continue
                
                await asyncio.sleep(1)
                
            except WebSocketDisconnect:
                log_response({
                    "status": "info",
                    "message": "WebSocket соединение разорвано",
                    "session_id": session_id
                })
                break
            except Exception as e:
                log_error(e, f"Ошибка в WebSocket цикле: {str(e)}")
                break
            
    finally:
        # Очищаем ресурсы при закрытии соединения
        if session_id in active_sessions:
            try:
                # Ставим сессию на паузу вместо удаления
                session.is_paused = True
                session.pause_time = datetime.now(LOCAL_TIMEZONE)
                if not session.is_paused:
                    session.total_time += session.pause_time - session.start_time
                
                log_response({
                    "status": "info",
                    "message": "WebSocket отключен, сессия поставлена на паузу",
                    "session_id": session_id,
                    "total_time": session.total_time.total_seconds()
                })
            except Exception as e:
                log_error(e, f"Ошибка при сохранении финального состояния: {str(e)}")
        
        try:
            await websocket.close()
        except:
            pass

templates = Jinja2Templates(directory="pages")

@router.get("/subjects/{subject}/{task_id}", response_class=HTMLResponse)
async def get_task(subject: str, task_id: str, request: Request, current_user: User = Depends(child_required)):
    try:
        # Получаем задание по предмету и локальному ID
        task = await Task.filter(subjects_name=subject, local_id=int(task_id)).first()
        if not task:
            log_error(Exception("Задание не найдено"), f"subject={subject}, task_id={task_id}")
            raise HTTPException(status_code=404, detail="Задание не найдено")
        
        # Загружаем базовый шаблон
        base_template = templates.get_template("tasks/base_task.html")
        
        # Загружаем контент задания
        task_content = templates.get_template(f"tasks/{subject}/task{task_id}/task{task_id}.html")
        
        # Рендерим контент задания
        task_html = task_content.render()
        
        # Рендерим базовый шаблон с контентом задания
        return base_template.render(
            request=request,
            title=f"Задание {task_id}",
            task_content=task_html,
            task_id=task.id,  # Передаем реальный ID
            subject=subject  # Передаем предмет
        )
    except Exception as e:
        log_error(e, f"Ошибка при загрузке задания: subject={subject}, task_id={task_id}")
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/check_task_status/{task_id}")
async def check_task_status(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    
    # Проверяем существование задания
    task = await Task.get_or_none(id=task_id)
    if not task:
        log_error(Exception("Задание не найдено"), f"task_id={task_id}")
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, выполнено ли задание
    existing_result = await Result.filter(user=current_user, task=task).first()
    
    log_response({
        "message": "Проверка статуса задания",
        "task_id": task_id,
        "is_completed": bool(existing_result)
    })
    
    return {"is_completed": bool(existing_result)}

@router.post("/confirm_result/{result_id}")
async def confirm_result(
    request: Request,
    result_id: int,
    current_user: User = Depends(parent_or_school_worker_required)
):
    log_request(request, current_user)
    try:
        # Получаем результат со всеми связанными данными
        result = await Result.get_or_none(id=result_id).prefetch_related('user', 'confirmed_by')
        if not result:
            raise HTTPException(status_code=404, detail="Результат не найден")

        # Проверяем, что результат принадлежит ребенку родителя
        if not await is_parent_of_child(current_user.id, result.user_id):
            raise HTTPException(status_code=403, detail="Доступ запрещен")

        # Проверяем, что результат еще не подтвержден
        if result.confirmed:
            raise HTTPException(status_code=400, detail="Результат уже подтвержден")

        # Обновляем результат
        result.confirmed = True
        result.confirmed_by = current_user
        result.confirmation_date = datetime.now()
        await result.save()

        log_response({
            "message": "Результат подтвержден",
            "result_id": result_id,
            "confirmed_by": current_user.id
        })

        return JSONResponse(content={"message": "Результат успешно подтвержден"})
    except Exception as e:
        log_error(e, "Ошибка при подтверждении результата")
        raise

@router.get("/check_active_session/{task_id}")
async def check_active_session(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    
    session_id = f"{current_user.id}_{task_id}"
    has_active_session = session_id in active_sessions
    
    log_response({
        "message": "Проверка активной сессии",
        "task_id": task_id,
        "has_active_session": has_active_session
    })
    
    return {"has_active_session": has_active_session}

@router.get("/check_break_time/{task_id}")
async def check_break_time(request: Request, task_id: int, current_user: User = Depends(child_required)):
    log_request(request, current_user)
    
    # Получаем запись о перерыве
    rest_break = await RestBreakTime.get_or_none(user=current_user)
    if not rest_break:
        now = datetime.now(LOCAL_TIMEZONE)
        rest_break = await RestBreakTime.create(
            user=current_user,
            access_time=now,
            last_break_time=now,
            total_work_time=0
        )
    
    now = datetime.now(LOCAL_TIMEZONE)
    can_access = now >= rest_break.access_time
    
    log_response({
        "message": "Проверка времени перерыва",
        "task_id": task_id,
        "can_access": can_access,
        "access_time": rest_break.access_time.isoformat()
    })
    
    return {
        "can_access": can_access,
        "access_time": rest_break.access_time.isoformat()
    }