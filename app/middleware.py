"""
Middlewares para la aplicación FastAPI
"""

import time
import gzip
import json
from typing import Optional, Dict, Any
from io import BytesIO
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils.logger import get_logger, log_request, get_correlation_id

logger = get_logger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware para medir tiempo de respuesta"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        response.headers["X-Response-Time-Ms"] = str(int(duration_ms))
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar headers de seguridad"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CSP más permisivo para docs
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'"
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class GZipMiddleware(BaseHTTPMiddleware):
    """
    Middleware para compresión GZip de respuestas
    
    Comprime respuestas > 1KB cuando el cliente acepta gzip
    """
    
    MINIMUM_SIZE = 1024  # 1KB
    
    async def dispatch(self, request: Request, call_next):
        # Verificar si el cliente acepta gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        response = await call_next(request)
        
        # No comprimir si ya está comprimido
        if response.headers.get("content-encoding"):
            return response
        
        # No comprimir respuestas pequeñas
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.MINIMUM_SIZE:
            return response
        
        # No comprimir streams
        if isinstance(response, StreamingResponse):
            return response
        
        # Comprimir respuesta
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body += chunk.encode("utf-8")
            else:
                body += chunk
        
        if len(body) < self.MINIMUM_SIZE:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # Comprimir con gzip
        compressed = gzip.compress(body, compresslevel=6)
        
        # Actualizar headers
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed))
        headers["vary"] = "accept-encoding"
        
        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )


class RateLimitStore:
    """Almacenamiento simple en memoria para rate limiting"""
    
    def __init__(self):
        self._store: Dict[str, list] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutos
    
    def _cleanup_old_entries(self):
        """Limpia entradas antiguas periódicamente"""
        now = time.time()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        
        # Limpiar todas las entradas antiguas
        for key in list(self._store.keys()):
            self._store[key] = [
                timestamp for timestamp in self._store[key]
                if now - timestamp < 3600  # 1 hora
            ]
            if not self._store[key]:
                del self._store[key]
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Verifica si una clave está dentro del límite de requests
        
        Args:
            key: Clave identificadora (ej: IP + endpoint)
            max_requests: Máximo de requests permitidos
            window_seconds: Ventana de tiempo en segundos
            
        Returns:
            True si está dentro del límite
        """
        self._cleanup_old_entries()
        
        now = time.time()
        
        if key not in self._store:
            self._store[key] = []
        
        # Limpiar entradas antiguas
        self._store[key] = [
            timestamp for timestamp in self._store[key]
            if now - timestamp < window_seconds
        ]
        
        # Verificar límite
        if len(self._store[key]) >= max_requests:
            return False
        
        # Agregar nuevo request
        self._store[key].append(now)
        return True
    
    def get_remaining(self, key: str, window_seconds: int) -> int:
        """Obtiene cuántos requests quedan en la ventana"""
        if key not in self._store:
            return settings.rate_limit_requests
        
        now = time.time()
        valid_requests = [
            timestamp for timestamp in self._store[key]
            if now - timestamp < window_seconds
        ]
        
        return max(0, settings.rate_limit_requests - len(valid_requests))
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del store"""
        return {
            "total_keys": len(self._store),
            "total_entries": sum(len(entries) for entries in self._store.values())
        }


# Instancia global del store de rate limiting
_rate_limit_store = RateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware para rate limiting por IP
    
    Limita requests por IP y endpoint
    """
    
    def __init__(self, app, max_requests: int = None, window_seconds: int = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window
    
    async def dispatch(self, request: Request, call_next):
        # Obtener IP del cliente
        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        
        # Crear clave única
        key = f"{client_ip}:{endpoint}"
        
        # Verificar rate limit
        if not _rate_limit_store.is_allowed(key, self.max_requests, self.window_seconds):
            remaining = _rate_limit_store.get_remaining(key, self.window_seconds)
            
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                endpoint=endpoint,
                correlation_id=get_correlation_id()
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds // 60} minutes.",
                    "retry_after": self.window_seconds,
                    "correlation_id": get_correlation_id()
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time() + self.window_seconds)),
                    "Retry-After": str(self.window_seconds)
                }
            )
        
        # Procesar request
        response = await call_next(request)
        
        # Agregar headers de rate limit
        remaining = _rate_limit_store.get_remaining(key, self.window_seconds)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Obtiene la IP real del cliente considerando proxies"""
        # Verificar headers de proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback a la IP de conexión
        if request.client:
            return request.client.host
        
        return "unknown"


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware para manejo centralizado de errores HTTP"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as exc:
            # Manejar errores HTTP conocidos
            return self._handle_http_error(exc, request)
            
        except Exception as exc:
            # Manejar errores inesperados
            logger.error(
                f"Unhandled exception in middleware: {str(exc)}",
                exc_info=True,
                path=request.url.path,
                correlation_id=get_correlation_id()
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error_code": "INTERNAL_ERROR",
                    "message": "Error interno del servidor",
                    "correlation_id": get_correlation_id()
                }
            )
    
    def _handle_http_error(self, exc: HTTPException, request: Request) -> JSONResponse:
        """Maneja errores HTTP específicos"""
        
        error_responses = {
            400: {
                "error_code": "BAD_REQUEST",
                "message": exc.detail if isinstance(exc.detail, str) else "Solicitud inválida"
            },
            401: {
                "error_code": "AUTHENTICATION_ERROR",
                "message": exc.detail if isinstance(exc.detail, str) else "No autenticado"
            },
            403: {
                "error_code": "AUTHORIZATION_ERROR",
                "message": exc.detail if isinstance(exc.detail, str) else "No autorizado"
            },
            404: {
                "error_code": "NOT_FOUND",
                "message": exc.detail if isinstance(exc.detail, str) else "Recurso no encontrado"
            },
            413: {
                "error_code": "FILE_TOO_LARGE",
                "message": f"Archivo demasiado grande. Máximo: {settings.max_file_size_mb} MB"
            },
            422: {
                "error_code": "VALIDATION_ERROR",
                "message": exc.detail if isinstance(exc.detail, str) else "Error de validación"
            },
            429: {
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": exc.detail if isinstance(exc.detail, str) else "Demasiadas solicitudes"
            },
            500: {
                "error_code": "INTERNAL_ERROR",
                "message": "Error interno del servidor"
            }
        }
        
        error_info = error_responses.get(
            exc.status_code,
            {"error_code": "UNKNOWN_ERROR", "message": "Error desconocido"}
        )
        
        # Si el detail es un dict (nuestro formato), usarlo directamente
        if isinstance(exc.detail, dict):
            content = exc.detail
        else:
            content = {
                "success": False,
                "error_code": error_info["error_code"],
                "message": error_info["message"],
                "correlation_id": get_correlation_id(),
                "status_code": exc.status_code
            }
        
        return JSONResponse(
            status_code=exc.status_code,
            content=content
        )


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para limitar tamaño de requests"""
    
    def __init__(self, app, max_size_bytes: int = None):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes or settings.max_file_size_bytes
    
    async def dispatch(self, request: Request, call_next):
        # Verificar Content-Length
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    logger.warning(
                        "Request too large",
                        size_bytes=size,
                        max_size_bytes=self.max_size_bytes,
                        correlation_id=get_correlation_id()
                    )
                    
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "error_code": "FILE_TOO_LARGE",
                            "message": f"Request too large. Maximum: {settings.max_file_size_mb} MB",
                            "correlation_id": get_correlation_id()
                        }
                    )
            except ValueError:
                pass
        
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware mejorado de logging
    
    Loggea información detallada de cada request/response
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log del request entrante
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown"),
            correlation_id=get_correlation_id()
        )
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log del response exitoso
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                correlation_id=get_correlation_id()
            )
            
            return response
            
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log del error
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                duration_ms=round(duration_ms, 2),
                correlation_id=get_correlation_id(),
                exc_info=True
            )
            
            raise


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware para validaciones adicionales de requests
    
    - Valida Content-Type para uploads
    - Valida tamaño de query params
    """
    
    MAX_QUERY_LENGTH = 2048
    
    async def dispatch(self, request: Request, call_next):
        # Validar longitud de query string
        query_string = str(request.query_params)
        if len(query_string) > self.MAX_QUERY_LENGTH:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Query string too long",
                    "correlation_id": get_correlation_id()
                }
            )
        
        # Validar Content-Type para uploads
        if request.method == "POST" and "/process" in request.url.path:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("multipart/form-data"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error_code": "VALIDATION_ERROR",
                        "message": "Content-Type must be multipart/form-data for file uploads",
                        "correlation_id": get_correlation_id()
                    }
                )
        
        return await call_next(request)
