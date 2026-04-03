"""
FastAPI Application - Entry Point
"""

import time
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from app.config import settings
from app.utils.logger import (
    get_logger, 
    set_correlation_id, 
    get_correlation_id,
    log_request,
    log_auth_event
)
from app.utils.validators import FileValidator, DocumentTypeValidator, validate_token_request
from app.models.document_types import (
    DocumentType,
    get_all_document_types,
    get_document_type_definition,
    get_expected_fields
)
from app.models.schemas import (
    DocumentTypesResponse,
    DocumentTypeInfo,
    DocumentTypeDetail,
    FieldInfo,
    HealthResponse,
    ConfigResponse,
    ErrorResponse,
    ErrorCode,
    TokenRequest,
    TokenResponse,
    DocumentProcessResponse
)
from app.azure_client import get_azure_client
from app.auth import (
    get_auth_provider,
    get_current_auth_context,
    require_action,
    AuthContext,
    AuthenticationError,
    AuthorizationError,
    TokenExpiredError
)
from app.services.document_processor import get_document_processor
from app.middleware import (
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    ErrorHandlerMiddleware,
    RequestSizeLimitMiddleware,
    GZipMiddleware,
    LoggingMiddleware,
    RequestValidationMiddleware
)

# Logger principal
logger = get_logger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="Document Processor API",
    description="""
    API para procesamiento de documentos con Azure Form Recognizer.
    
    ## Autenticación
    Todos los endpoints protegidos requieren un token JWT en el header:
    ```
    Authorization: Bearer <token>
    ```
    
    Obtén un token en `/api/v1/auth/token`
    
    ## Tipos de Documento Soportados
    - **curriculum_vitae**: Hoja de vida (modelo prebuilt-resume)
    - **titulo_universitario**: Título universitario (modelo custom)
    - **concentracion_notas**: Certificado de notas (modelo custom)
    - **cedula_identidad**: Cédula de identidad (modelo prebuilt-identityDocument)
    - **cotizacion_afp**: Cotización AFP (modelo custom)
    
    ## Rate Limiting
    - 100 requests por hora por IP
    - Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
    
    ## Compresión
    Respuestas > 1KB se comprimen con GZip automáticamente
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Document Processor API",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# ============================================
# MIDDLEWARES (orden importante)
# ============================================

# 1. Logging primero para capturar todo
app.add_middleware(LoggingMiddleware)

# 2. Timing
app.add_middleware(RequestTimingMiddleware)

# 3. Headers de seguridad
app.add_middleware(SecurityHeadersMiddleware)

# 4. Validación de requests
app.add_middleware(RequestValidationMiddleware)

# 5. Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window
)

# 6. Límite de tamaño
app.add_middleware(RequestSizeLimitMiddleware)

# 7. Compresión GZip
app.add_middleware(GZipMiddleware)

# 8. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-Response-Time-Ms"]
)

# 9. Manejo de errores (debe ir al final)
app.add_middleware(ErrorHandlerMiddleware)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Middleware para asignar correlation_id a cada request"""
    cid = request.headers.get("X-Correlation-ID")
    set_correlation_id(cid)
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = get_correlation_id()
    return response


# ============================================
# MANEJADORES DE EXCEPCIONES ESPECÍFICOS
# ============================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Manejador de excepciones HTTP"""
    error_codes = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.AUTHENTICATION_ERROR,
        403: ErrorCode.AUTHORIZATION_ERROR,
        404: ErrorCode.VALIDATION_ERROR,
        413: ErrorCode.VALIDATION_ERROR,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR
    }
    
    error_code = error_codes.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {
            "success": False,
            "error_code": error_code,
            "message": str(exc.detail) if exc.detail else "Error",
            "correlation_id": get_correlation_id(),
            "status_code": exc.status_code
        }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones"""
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        path=request.url.path,
        correlation_id=get_correlation_id()
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "Error interno del servidor",
            "correlation_id": get_correlation_id(),
            "path": request.url.path
        }
    )


# ============================================
# ENDPOINTS PÚBLICOS
# ============================================

@app.get("/", tags=["General"])
async def root():
    """Información básica de la API"""
    return {
        "name": "Document Processor API",
        "version": "1.0.0",
        "status": "running",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "auth": "/api/v1/auth/token",
            "health": "/health",
            "document_types": "/api/v1/document-types",
            "process": "/api/v1/documents/process"
        },
        "correlation_id": get_correlation_id()
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """
    Health check endpoint para monitoreo del contenedor
    
    Retorna estado del servicio y dependencias.
    """
    azure_client = get_azure_client()
    auth_provider = get_auth_provider()
    processor = get_document_processor()
    
    # Verificar estado de dependencias
    dependencies = {
        "azure": "configured" if azure_client.is_configured else "not_configured",
        "jwt": "configured" if auth_provider._is_configured() else "not_configured",
        "processor": "ready" if processor else "not_ready"
    }
    
    all_ready = all(d in ["configured", "ready"] for d in dependencies.values())
    
    return HealthResponse(
        status="healthy" if all_ready else "degraded",
        service="document-processor-api",
        timestamp=time.time(),
        version="1.0.0"
    )


@app.get("/health/detailed", tags=["General"])
async def health_check_detailed():
    """
    Health check detallado con información de todas las dependencias
    """
    azure_client = get_azure_client()
    auth_provider = get_auth_provider()
    processor = get_document_processor()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "uptime_seconds": time.time(),  # En producción, calcular desde el inicio
        "dependencies": {
            "azure_form_recognizer": {
                "status": "up" if azure_client.is_configured else "down",
                "configured": azure_client.is_configured,
                "timeout_seconds": settings.azure_timeout_seconds,
                "max_retries": settings.azure_max_retries
            },
            "jwt_auth": {
                "status": "up" if auth_provider._is_configured() else "down",
                "configured": auth_provider._is_configured(),
                "expiration_minutes": settings.jwt_expiration_minutes
            },
            "document_processor": {
                "status": "up" if processor else "down",
                "available": processor is not None
            }
        },
        "configuration": {
            "max_file_size_mb": settings.max_file_size_mb,
            "rate_limit_requests": settings.rate_limit_requests,
            "rate_limit_window_minutes": settings.rate_limit_window // 60,
            "log_level": settings.log_level
        },
        "correlation_id": get_correlation_id()
    }


@app.get("/api/v1/config", response_model=ConfigResponse, tags=["Configuración"])
async def get_config():
    """
    Configuración de la API (sin datos sensibles)
    
    Retorna información de configuración actual.
    """
    logger.info("Config endpoint accessed")
    
    return ConfigResponse(
        azure_configured=bool(
            settings.azure_form_recognizer_endpoint and 
            settings.azure_form_recognizer_api_key
        ),
        jwt_configured=bool(settings.jwt_secret_key),
        max_file_size_mb=settings.max_file_size_mb,
        allowed_file_types=settings.allowed_mime_types_list,
        allowed_extensions=settings.allowed_extensions,
        jwt_expiration_minutes=settings.jwt_expiration_minutes,
        azure_timeout_seconds=settings.azure_timeout_seconds,
        azure_max_retries=settings.azure_max_retries,
        log_level=settings.log_level,
        rate_limit_requests=settings.rate_limit_requests,
        rate_limit_window_seconds=settings.rate_limit_window
    )


# ============================================
# ENDPOINTS DE AUTENTICACIÓN
# ============================================

@app.post(
    "/api/v1/auth/token",
    response_model=TokenResponse,
    tags=["Autenticación"],
    responses={
        400: {"model": ErrorResponse, "description": "Datos inválidos"},
        401: {"model": ErrorResponse, "description": "Credenciales inválidas"}
    }
)
async def create_token(request: TokenRequest):
    """
    Genera un token JWT para autenticación
    
    - **client_name**: Nombre del cliente registrado en ALLOWED_CLIENTS
    - **action_name**: Nombre de la acción permitida
    - **shared_key**: Clave compartida del cliente
    
    El token expira en 30 minutos (configurable).
    """
    logger.info(f"Token request for client: {request.client_name}")
    
    # Validar campos requeridos
    is_valid, error_msg = validate_token_request(
        request.client_name,
        request.action_name,
        request.shared_key
    )
    
    if not is_valid:
        log_auth_event(
            event_type="token_request",
            client_name=request.client_name,
            success=False,
            error=error_msg
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR,
                "message": error_msg,
                "correlation_id": get_correlation_id()
            }
        )
    
    # Autenticar cliente
    auth_provider = get_auth_provider()
    
    if not auth_provider.authenticate_client(request.client_name, request.shared_key):
        log_auth_event(
            event_type="authentication",
            client_name=request.client_name,
            success=False,
            error="Invalid credentials"
        )
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error_code": ErrorCode.AUTHENTICATION_ERROR,
                "message": "Invalid client credentials",
                "correlation_id": get_correlation_id()
            }
        )
    
    # Generar token
    try:
        token = auth_provider.generate_token(
            client_name=request.client_name,
            action_name=request.action_name
        )
        
        log_auth_event(
            event_type="token_generated",
            client_name=request.client_name,
            action_name=request.action_name,
            success=True
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.jwt_expiration_minutes * 60,
            client_name=request.client_name,
            action_name=request.action_name
        )
        
    except AuthenticationError as e:
        log_auth_event(
            event_type="token_generation",
            client_name=request.client_name,
            success=False,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error_code": ErrorCode.INTERNAL_ERROR,
                "message": str(e),
                "correlation_id": get_correlation_id()
            }
        )


@app.get(
    "/api/v1/auth/verify",
    tags=["Autenticación"],
    responses={
        401: {"model": ErrorResponse, "description": "Token inválido o expirado"}
    }
)
async def verify_token(auth_context: AuthContext = Depends(get_current_auth_context)):
    """
    Verifica que el token sea válido y retorna información del cliente
    
    Requiere autenticación Bearer.
    """
    from datetime import datetime, timezone
    
    exp_datetime = datetime.fromtimestamp(auth_context.exp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds_remaining = (exp_datetime - now).total_seconds()
    
    return {
        "valid": True,
        "client_name": auth_context.client_name,
        "action_name": auth_context.action_name,
        "expires_at": auth_context.exp,
        "expires_at_iso": exp_datetime.isoformat(),
        "seconds_remaining": int(seconds_remaining),
        "correlation_id": get_correlation_id()
    }


# ============================================
# ENDPOINTS DE TIPOS DE DOCUMENTO
# ============================================

@app.get(
    "/api/v1/document-types",
    response_model=DocumentTypesResponse,
    tags=["Documentos"],
    responses={
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def get_document_types(
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Retorna los tipos de documento soportados
    
    Requiere autenticación Bearer.
    """
    logger.info("Document types endpoint accessed")
    
    definitions = get_all_document_types()
    types = [DocumentTypeInfo.from_definition(d) for d in definitions]
    
    return DocumentTypesResponse(
        document_types=types,
        total=len(types)
    )


@app.get(
    "/api/v1/document-types/{doc_type}",
    response_model=DocumentTypeDetail,
    tags=["Documentos"],
    responses={
        400: {"model": ErrorResponse, "description": "Tipo inválido"},
        401: {"model": ErrorResponse, "description": "No autenticado"},
        404: {"model": ErrorResponse, "description": "Tipo no encontrado"}
    }
)
async def get_document_type_detail(
    doc_type: str,
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Retorna detalle completo de un tipo de documento con sus campos esperados
    
    - **doc_type**: Tipo de documento (curriculum_vitae, titulo_universitario, etc.)
    
    Requiere autenticación Bearer.
    """
    logger.info(f"Document type detail endpoint accessed: {doc_type}")
    
    try:
        document_type = DocumentType(doc_type)
    except ValueError:
        valid_types = [t.value for t in DocumentType]
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": ErrorCode.INVALID_DOCUMENT_TYPE,
                "message": f"Tipo de documento inválido. Válidos: {', '.join(valid_types)}",
                "correlation_id": get_correlation_id()
            }
        )
    
    definition = get_document_type_definition(document_type)
    if not definition:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR,
                "message": "Tipo de documento no encontrado",
                "correlation_id": get_correlation_id()
            }
        )
    
    fields = [
        FieldInfo(
            name=f.name,
            description=f.description,
            data_type=f.data_type,
            required=f.required,
            example=f.example
        )
        for f in definition.fields
    ]
    
    return DocumentTypeDetail(
        type=definition.type.value,
        name=definition.name,
        description=definition.description,
        azure_model=definition.azure_model,
        is_custom_model=definition.is_custom_model,
        supported_extensions=definition.supported_extensions,
        max_pages=definition.max_pages,
        fields=fields
    )


# ============================================
# ENDPOINTS DE PROCESAMIENTO
# ============================================

@app.post(
    "/api/v1/documents/process",
    response_model=DocumentProcessResponse,
    tags=["Documentos"],
    responses={
        400: {"model": ErrorResponse, "description": "Datos inválidos"},
        401: {"model": ErrorResponse, "description": "No autenticado"},
        413: {"model": ErrorResponse, "description": "Archivo demasiado grande"},
        422: {"model": ErrorResponse, "description": "Error de validación"},
        500: {"model": ErrorResponse, "description": "Error de procesamiento"}
    }
)
async def process_document(
    archivo: UploadFile = File(..., description="Archivo a procesar (PDF, PNG, JPG, JPEG). Máximo 10 MB"),
    tipo_documento: str = Form(..., description="Tipo de documento: curriculum_vitae, titulo_universitario, concentracion_notas, cedula_identidad, cotizacion_afp"),
    cliente_id: Optional[str] = Form(None, description="ID del cliente para tracking (opcional)"),
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Procesa un documento usando Azure Form Recognizer
    
    - **archivo**: Archivo a procesar (PDF, PNG, JPG, JPEG). Máximo 10 MB
    - **tipo_documento**: Tipo de documento
    - **cliente_id**: ID del cliente para tracking (opcional)
    
    **Tipos de documento soportados:**
    - `curriculum_vitae`: Hoja de vida
    - `titulo_universitario`: Título universitario
    - `concentracion_notas`: Certificado de notas
    - `cedula_identidad`: Cédula de identidad
    - `cotizacion_afp`: Cotización AFP
    
    Requiere autenticación Bearer.
    """
    logger.info(
        f"Document processing request",
        document_type=tipo_documento,
        filename=archivo.filename,
        client_name=auth_context.client_name
    )
    
    # Validar tipo de documento
    try:
        document_type = DocumentType(tipo_documento)
    except ValueError:
        valid_types = [t.value for t in DocumentType]
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": ErrorCode.INVALID_DOCUMENT_TYPE,
                "message": f"Tipo de documento inválido. Válidos: {', '.join(valid_types)}",
                "correlation_id": get_correlation_id()
            }
        )
    
    # Validar archivo antes de leer
    if not archivo.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR,
                "message": "Nombre de archivo requerido",
                "correlation_id": get_correlation_id()
            }
        )
    
    # Leer archivo
    try:
        file_content = await archivo.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR,
                "message": f"Error leyendo archivo: {str(e)}",
                "correlation_id": get_correlation_id()
            }
        )
    finally:
        await archivo.close()
    
    # Validar tamaño
    if len(file_content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR,
                "message": f"Archivo demasiado grande. Máximo: {settings.max_file_size_mb} MB",
                "correlation_id": get_correlation_id()
            }
        )
    
    # Procesar documento
    processor = get_document_processor()
    
    result = await processor.process_document(
        document_type=document_type,
        file_content=file_content,
        filename=archivo.filename,
        client_name=auth_context.client_name,
        metadata={"cliente_id": cliente_id} if cliente_id else None
    )
    
    return result


# ============================================
# ENDPOINTS DE AZURE
# ============================================

@app.get(
    "/api/v1/azure/models",
    tags=["Azure"],
    responses={
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def get_azure_models(
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Retorna información de los modelos Azure configurados
    
    Requiere autenticación Bearer.
    """
    logger.info("Azure models endpoint accessed")
    
    azure_client = get_azure_client()
    models = azure_client.list_available_models()
    
    return {
        "models": models,
        "azure_configured": azure_client.is_configured,
        "timeout_seconds": settings.azure_timeout_seconds,
        "max_retries": settings.azure_max_retries,
        "correlation_id": get_correlation_id()
    }


@app.get(
    "/api/v1/azure/status",
    tags=["Azure"],
    responses={
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def get_azure_status(
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Retorna el estado de la conexión con Azure
    
    Requiere autenticación Bearer.
    """
    logger.info("Azure status endpoint accessed")
    
    azure_client = get_azure_client()
    
    return {
        "configured": azure_client.is_configured,
        "endpoint": settings.azure_form_recognizer_endpoint[:30] + "..." if settings.azure_form_recognizer_endpoint else None,
        "timeout_seconds": settings.azure_timeout_seconds,
        "max_retries": settings.azure_max_retries,
        "correlation_id": get_correlation_id()
    }


# ============================================
# ENDPOINTS DE UTILIDAD
# ============================================

@app.get(
    "/api/v1/stats",
    tags=["Utilidades"],
    responses={
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def get_stats(
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Retorna estadísticas del sistema
    
    Requiere autenticación Bearer.
    """
    from app.middleware import _rate_limit_store
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "correlation_id": get_correlation_id(),
        "rate_limit_stats": _rate_limit_store.get_stats(),
        "configuration": {
            "max_file_size_mb": settings.max_file_size_mb,
            "rate_limit_requests": settings.rate_limit_requests,
            "rate_limit_window_minutes": settings.rate_limit_window // 60,
            "jwt_expiration_minutes": settings.jwt_expiration_minutes,
            "azure_timeout_seconds": settings.azure_timeout_seconds,
            "azure_max_retries": settings.azure_max_retries
        },
        "document_types": {
            "total": len(list(DocumentType)),
            "types": [t.value for t in DocumentType]
        }
    }


@app.get(
    "/api/v1/ping",
    tags=["Utilidades"]
)
async def ping():
    """
    Endpoint simple para verificar que la API responde
    
    No requiere autenticación.
    """
    return {
        "status": "pong",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "correlation_id": get_correlation_id()
    }


@app.get(
    "/robots.txt",
    response_class=PlainTextResponse,
    tags=["General"]
)
async def robots_txt():
    """Archivo robots.txt para SEO"""
    return """User-agent: *
Disallow: /
"""


# ============================================
# ENDPOINT DE PRUEBA
# ============================================

@app.get(
    "/api/v1/test-validation",
    tags=["Testing"],
    responses={
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def test_validation(
    auth_context: AuthContext = Depends(get_current_auth_context)
):
    """
    Endpoint de prueba para validadores y componentes
    
    Requiere autenticación Bearer.
    """
    logger.info("Test validation endpoint accessed")
    
    # Test de validación de tipo de documento
    test_types = [
        "curriculum_vitae",
        "titulo_universitario",
        "tipo_invalido"
    ]
    
    validation_results = []
    for doc_type in test_types:
        result = DocumentTypeValidator.validate(doc_type)
        validation_results.append({
            "type": doc_type,
            "is_valid": result.is_valid,
            "error": result.error_message if not result.is_valid else None
        })
    
    # Test de modelos y campos
    model_tests = []
    for doc_type in DocumentType:
        definition = get_document_type_definition(doc_type)
        fields = get_expected_fields(doc_type)
        model_tests.append({
            "type": doc_type.value,
            "name": definition.name if definition else "",
            "azure_model": definition.azure_model if definition else "",
            "is_custom": definition.is_custom_model if definition else False,
            "fields_count": len(fields),
            "required_fields": [f.name for f in fields if f.required]
        })
    
    # Test de cliente Azure
    azure_client = get_azure_client()
    
    # Test de autenticación
    auth_provider = get_auth_provider()
    
    # Test de procesador
    processor = get_document_processor()
    
    return {
        "message": "Validadores y modelos funcionando correctamente",
        "correlation_id": get_correlation_id(),
        "authenticated_client": auth_context.client_name,
        "authenticated_action": auth_context.action_name,
        "document_type_tests": validation_results,
        "model_tests": model_tests,
        "azure_client": {
            "configured": azure_client.is_configured,
            "timeout": settings.azure_timeout_seconds,
            "max_retries": settings.azure_max_retries
        },
        "auth": {
            "jwt_configured": auth_provider._is_configured(),
            "clients_configured": list(settings.clients_dict.keys()),
            "expiration_minutes": settings.jwt_expiration_minutes
        },
        "document_processor": {
            "available": processor is not None,
            "supported_types": [t["type"] for t in processor.get_supported_types()] if processor else []
        },
        "file_validation": {
            "max_file_size_mb": settings.max_file_size_mb,
            "max_file_size_bytes": settings.max_file_size_bytes,
            "allowed_mime_types": settings.allowed_mime_types_list,
            "allowed_extensions": settings.allowed_extensions
        }
    }


# ============================================
# INICIO DE LA APLICACIÓN
# ============================================

if __name__ == "__main__":
    logger.info("Starting Document Processor API")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )
