from datetime import datetime, timedelta
from typing import Dict, Optional
import json
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import os
from handlers.childrens import get_available_subjects
from models.user import User, child_required
from models.task import Task
from models.result import Result
from utils.logger import log_error, log_request, log_response

router = APIRouter()

# Pydantic модель для Task
class TaskModel(BaseModel):
    id: int
    name: str
    subjects_name: str
    type: str
    max_score: float

# Модель для ответа
class AnswerModel(BaseModel):
    answer: int

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

# Хранилище активных сессий
active_sessions: Dict[str, TaskSession] = {}

# Константы
BREAK_DURATION = timedelta(minutes=15)
MAX_WORK_TIME = {
    1: timedelta(hours=1),    # 1 класс
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

@router.get("/task/{task_id}")
async def get_task_page(task_id: int, current_user: User = Depends(child_required)):
    # Проверяем существование задания
    task = await Task.get_or_none(id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    return FileResponse("pages/task_page/index.html")

@router.get("/task/{task_id}/info")
async def get_task_info(task_id: int, current_user: User = Depends(child_required)):
    # Получаем информацию о задании
    task = await Task.get_or_none(id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    return TaskModel(
        id=task.id,
        name=task.name,
        subjects_name=task.subjects_name,
        type=task.type,
        max_score=task.max_score
    )

@router.post("/start_task/{task_id}")
async def start_task(task_id: int, current_user: User = Depends(child_required)):
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id in active_sessions:
        raise HTTPException(status_code=400, detail="Задание уже выполняется")
    
    # Проверяем существование задания
    task = await Task.get_or_none(id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Получаем класс ученика из current_user
    grade = int(current_user.current_class[0]) if current_user.current_class else 1
    
    # Создаем Pydantic модель для Task
    task_model = TaskModel(
        id=task.id,
        name=task.name,
        subjects_name=task.subjects_name,
        type=task.type,
        max_score=task.max_score
    )
    
    active_sessions[session_id] = TaskSession(
        start_time=datetime.now(),
        user_id=current_user.id,
        task_id=task_id,
        task=task_model
    )
    return {"status": "success", "message": "Задание начато"}

@router.post("/pause_task/{task_id}")
async def pause_task(task_id: int, current_user: User = Depends(child_required)):
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    if not session.is_paused:
        session.pause_time = datetime.now()
        session.is_paused = True
        session.total_time += session.pause_time - session.start_time
    
    return {"status": "success", "message": "Задание приостановлено"}

@router.post("/resume_task/{task_id}")
async def resume_task(task_id: int, current_user: User = Depends(child_required)):
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    if session.is_paused:
        session.start_time = datetime.now()
        session.is_paused = False
        session.pause_time = None
    
    return {"status": "success", "message": "Задание возобновлено"}

@router.post("/finish_task/{task_id}")
async def finish_task(task_id: int, current_user: User = Depends(child_required)):
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    
    # Получаем оригинальный объект Task
    task = await Task.get(id=task_id)
    
    # Создаем запись о результате
    await Result.create(
        user=current_user,
        task=task,
        score=session.score,
        time_seconds=session.total_time.total_seconds()
    )
    
    # Удаляем сессию
    del active_sessions[session_id]
    
    return {"status": "success", "message": "Задание завершено"}

@router.post("/check_answer/{task_id}")
async def check_answer(
    task_id: int,
    answer_data: AnswerModel = Body(...),
    current_user: User = Depends(child_required)
):
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    session = active_sessions[session_id]
    session.score += 1
    
    return {"status": "success", "score": session.score}

@router.websocket("/ws/task/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int, current_user: User = Depends(child_required)):
    await websocket.accept()
    
    session_id = f"{current_user.id}_{task_id}"
    
    if session_id not in active_sessions:
        await websocket.close(code=1000, reason="Задание не найдено")
        return
    
    session = active_sessions[session_id]
    # Получаем класс ученика, если не указан, используем 1 класс
    try:
        grade = int(current_user.current_class[0]) if current_user.current_class else 1
        if grade not in MAX_WORK_TIME:
            grade = 1
    except (ValueError, IndexError):
        grade = 1
    
    try:
        while True:
            current_time = datetime.now()
            
            if not session.is_paused:
                elapsed_time = current_time - session.start_time + session.total_time
                
                # Проверка на необходимость перерыва
                if elapsed_time >= MAX_WORK_TIME[grade]:
                    session.is_break = True
                    session.is_paused = True
                    session.pause_time = current_time
                    await websocket.send_json({
                        "type": "break",
                        "message": "Время для перерыва!",
                        "break_duration": BREAK_DURATION.total_seconds()
                    })
                
                # Отправка информации о времени
                await websocket.send_json({
                    "type": "time_update",
                    "elapsed_time": elapsed_time.total_seconds(),
                    "max_time": MAX_WORK_TIME[grade].total_seconds(),
                    "is_paused": session.is_paused,
                    "is_break": session.is_break,
                    "score": session.score,
                    "max_score": session.task.max_score
                })
            
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        if session_id in active_sessions:
            del active_sessions[session_id] 


templates = Jinja2Templates(directory="pages")

@router.get("/testtask")
def testtask(request: Request):
    return templates.TemplateResponse(
        "testtask/testtask.html", 
        {
            "request": request        }
    )
@router.get("/subjects/{subject}/{task_id}", response_class=HTMLResponse)
async def subject_page(
    request: Request,
    subject: str,
    task_id: int,
    current_user: User = Depends(child_required)
):
    log_request(request, current_user)
    try:
        available_subjects = get_available_subjects(current_user)

        if subject not in available_subjects:
            log_error(Exception("Предмет не найден"), f"Subject: {subject}")
            raise HTTPException(status_code=404, detail="Предмет не найден или недоступен для вас")

        subject_name = available_subjects[subject]

        task = await Task.get_or_none(id=task_id)
        if not task:
            log_error(Exception("Задание не найдено"), f"Task ID: {task_id}")
            raise HTTPException(status_code=404, detail="Задание не найдено")


        return templates.TemplateResponse(
            "testtask/testtask.html", 
            {
                "request": request,
                "subject": subject,
                "subject_name": subject_name,
                "current_user": current_user
            }
        )


        log_response({
            "message": "Открыта страница c заданием",
            "subject": subject,
            "subject_name": subject_name
        })

    except Exception as e:
        log_error(e, "Ошибка при открытии страницы предмета")
        raise