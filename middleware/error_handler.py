from fastapi import Request, status, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

templates = Jinja2Templates(directory="pages")

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code == 404:
                return templates.TemplateResponse(
                    "error_pages/404.html",
                    {
                        "request": request,
                        "error_message": "Страница не найдена"
                    },
                    status_code=404
                )
            elif response.status_code == 401:
                return templates.TemplateResponse(
                    "error_pages/401.html",
                    {
                        "request": request,
                        "error_message": "Требуется авторизация"
                    },
                    status_code=401
                )
            elif response.status_code == 403:
                return templates.TemplateResponse(
                    "error_pages/403.html",
                    {
                        "request": request,
                        "error_message": "Доступ запрещен"
                    },
                    status_code=403
                )
            return response
        except HTTPException as e:
            if e.status_code == 403:
                return templates.TemplateResponse(
                    "error_pages/403.html",
                    {
                        "request": request,
                        "error_message": e.detail
                    },
                    status_code=403
                )
            elif e.status_code == 401:
                return templates.TemplateResponse(
                    "error_pages/401.html",
                    {
                        "request": request,
                        "error_message": e.detail
                    },
                    status_code=401
                )
            raise e
        except Exception as e:
            return templates.TemplateResponse(
                "error_pages/500.html",
                {
                    "request": request,
                    "error_message": "Произошла ошибка при загрузке страницы"
                },
                status_code=500
            ) 