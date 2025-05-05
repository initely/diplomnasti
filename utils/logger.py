import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request
import json
from models.user import User

# Настройка формата логов
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def log_request(request: Request, user: Optional[User] = None):
    """Логирование входящего запроса"""
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "method": request.method,
        "url": str(request.url),
        "client_host": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "user": {
            "id": user.id if user else None,
            "email": user.email if user else None,
            "role": user.role if user else None
        } if user else None
    }
    
    logger.info(f"Входящий запрос: {json.dumps(log_data, ensure_ascii=False)}")

def log_response(response_data: Any, status_code: int = 200):
    """Логирование исходящего ответа"""
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code,
        "response": response_data
    }
    
    logger.info(f"Исходящий ответ: {json.dumps(log_data, ensure_ascii=False)}")

def log_error(error: Exception, context: str = ""):
    """Логирование ошибок"""
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context
    }
    
    logger.error(f"Ошибка: {json.dumps(log_data, ensure_ascii=False)}") 