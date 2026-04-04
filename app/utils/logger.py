"""
Logging estructurado en formato JSON para trazabilidad
"""

import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

from app.config import settings

# Context variable para correlation_id (se mantiene por request)
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class JSONFormatter(logging.Formatter):
    """Formatter que genera logs en formato JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get() or "",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Agregar campos extras si existen
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def get_correlation_id() -> str:
    """Obtiene o genera un correlation_id"""
    current = correlation_id.get()
    if not current:
        new_id = str(uuid.uuid4())[:8]
        correlation_id.set(new_id)
        return new_id
    return current


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Establece un correlation_id específico o genera uno nuevo"""
    if cid is None:
        cid = str(uuid.uuid4())[:8]
    correlation_id.set(cid)
    return cid


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger configurado con formato JSON"""
    logger = logging.getLogger(name)
    
    # Configurar solo si no tiene handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
        # Nivel desde configuración
        level = getattr(logging, settings.log_level.upper(), logging.INFO)
        logger.setLevel(level)
        
        # Evitar propagación duplicada
        logger.propagate = False
    
    return logger


class LoggerMixin:
    """Mixin para agregar logging a cualquier clase"""
    
    def __init__(self):
        self._logger: Optional[logging.Logger] = None
    
    @property
    def logger(self) -> logging.Logger:
        """Lazy loading del logger"""
        if self._logger is None:
            self._logger = get_logger(self.__class__.__module__)
        return self._logger
    
    def log_info(self, message: str, **kwargs):
        """Log de nivel INFO con datos extras"""
        if "message" in kwargs:
            kwargs["error_message"] = kwargs.pop("message")
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def log_warning(self, message: str, **kwargs):
        """Log de nivel WARNING con datos extras"""
        if "message" in kwargs:
            kwargs["error_message"] = kwargs.pop("message")
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def log_error(self, message: str, **kwargs):
        """Log de nivel ERROR con datos extras"""
        if "message" in kwargs:
            kwargs["error_message"] = kwargs.pop("message")
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)
    
    def log_debug(self, message: str, **kwargs):
        """Log de nivel DEBUG con datos extras"""
        if "message" in kwargs:
            kwargs["error_message"] = kwargs.pop("message")
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)


def log_request(
    method: str,
    path: str,
    client_ip: str,
    status_code: int,
    duration_ms: float,
    user_agent: Optional[str] = None,
    client_name: Optional[str] = None
):
    """Log estructurado para requests HTTP"""
    logger = get_logger("api.request")
    
    log_data = {
        "extra_data": {
            "event": "http_request",
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "user_agent": user_agent or "",
            "client_name": client_name or "",
            "correlation_id": correlation_id.get() or ""
        }
    }
    
    logger.info(f"{method} {path} - {status_code}", extra=log_data)


def log_azure_request(
    document_type: str,
    model_used: str,
    success: bool,
    duration_ms: float,
    error: Optional[str] = None
):
    """Log específico para llamadas a Azure Form Recognizer"""
    logger = get_logger("azure.request")
    
    log_data = {
        "extra_data": {
            "event": "azure_request",
            "document_type": document_type,
            "model_used": model_used,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "error": error or "",
            "correlation_id": correlation_id.get() or ""
        }
    }
    
    if success:
        logger.info(f"Azure request completed - {document_type}", extra=log_data)
    else:
        logger.error(f"Azure request failed - {document_type}: {error}", extra=log_data)


def log_document_processed(
    document_type: str,
    confidence_score: float,
    processing_time_ms: float,
    file_size_bytes: int,
    client_name: Optional[str] = None
):
    """Log para documentos procesados exitosamente"""
    logger = get_logger("document.processed")
    
    log_data = {
        "extra_data": {
            "event": "document_processed",
            "document_type": document_type,
            "confidence_score": round(confidence_score, 3),
            "processing_time_ms": round(processing_time_ms, 2),
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
            "client_name": client_name or "",
            "correlation_id": correlation_id.get() or ""
        }
    }
    
    logger.info(f"Document processed - {document_type}", extra=log_data)


def log_auth_event(
    event_type: str,
    client_name: str,
    success: bool,
    action_name: Optional[str] = None,
    error: Optional[str] = None
):
    """Log para eventos de autenticación"""
    logger = get_logger("auth.event")
    
    log_data = {
        "extra_data": {
            "event": f"auth_{event_type}",
            "client_name": client_name,
            "action_name": action_name or "",
            "success": success,
            "error": error or "",
            "correlation_id": correlation_id.get() or ""
        }
    }
    
    if success:
        logger.info(f"Auth {event_type} success - {client_name}", extra=log_data)
    else:
        logger.warning(f"Auth {event_type} failed - {client_name}: {error}", extra=log_data)
