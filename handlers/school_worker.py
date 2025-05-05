from typing import Any, Dict
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from models.user import User, get_current_user, school_worker_required
from utils.logger import log_request, log_response, log_error
import json
from fastapi import status

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

@router.get("/children-statistics", response_class=HTMLResponse)
async def children_statistics(request: Request, current_user: Dict[str, Any] = Depends(school_worker_required)):
    # Получаем название школы
    school = await current_user.school
    school_name = school.name if school else "Не указана"
    
    return templates.TemplateResponse(
        "school_worker_pages/children_statistics.html",
        {
            "request": request,
            "school_name": school_name
        }
    )
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


