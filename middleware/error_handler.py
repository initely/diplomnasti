from fastapi import Request, status
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
            return response
        except Exception as e:
            return templates.TemplateResponse(
                "error_pages/500.html",
                {
                    "request": request,
                    "error_message": "Произошла ошибка при загрузке страницы"
                },
                status_code=500
            ) 