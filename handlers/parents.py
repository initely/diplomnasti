from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, parent_required, is_parent_of_child, get_children_for_parent
from models.school import School
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
    return templates.TemplateResponse(
        "statistics_page/index.html",
        {
            "request": request,
            "current_user": current_user
        }
    )

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
