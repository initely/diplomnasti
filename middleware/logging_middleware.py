from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from utils.logger import log_request, log_response, log_error

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            # Логируем входящий запрос
            log_request(request)
            
            # Выполняем запрос
            response = await call_next(request)
            
            # Логируем ответ
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            log_response({
                "status_code": response.status_code,
                "process_time": process_time
            })
            
            return response
            
        except Exception as e:
            # Логируем ошибку
            log_error(e, f"Ошибка при обработке запроса {request.method} {request.url}")
            raise 