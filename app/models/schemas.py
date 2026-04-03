"""
Pydantic schemas para requests y responses
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.document_types import (
    DocumentType, 
    DocumentTypeDefinition,
    FieldDefinition,
    get_document_type_definition,
    get_all_document_types
)


# ============================================
# ENUMS
# ============================================

class ProcessingStatus(str, Enum):
    """Estados de procesamiento de documento"""
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


class ErrorCode(str, Enum):
    """Códigos de error"""
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_DOCUMENT_TYPE = "INVALID_DOCUMENT_TYPE"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    AZURE_ERROR = "AZURE_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================
# SCHEMAS DE AUTENTICACIÓN
# ============================================

class TokenRequest(BaseModel):
    """Request para solicitar token JWT"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "client_name": "cliente1",
            "action_name": "process_documents",
            "shared_key": "clave-secreta-cliente1"
        }
    })
    
    client_name: str = Field(
        ...,
        description="Nombre del cliente",
        min_length=1,
        max_length=100
    )
    action_name: str = Field(
        ...,
        description="Nombre de la acción permitida",
        min_length=1,
        max_length=100
    )
    shared_key: str = Field(
        ...,
        description="Clave compartida para validación",
        min_length=1,
        max_length=255
    )


class TokenResponse(BaseModel):
    """Response con token JWT"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "token_type": "bearer",
            "expires_in": 1800,
            "client_name": "cliente1",
            "action_name": "process_documents"
        }
    })
    
    access_token: str = Field(..., description="Token JWT de acceso")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Tiempo de expiración en segundos")
    client_name: str = Field(..., description="Nombre del cliente")
    action_name: str = Field(..., description="Acción permitida")


class TokenPayload(BaseModel):
    """Payload decodificado del JWT"""
    client_name: str
    action_name: str
    exp: int
    iat: Optional[int] = None


# ============================================
# SCHEMAS DE DOCUMENTOS
# ============================================

class DocumentTypeInfo(BaseModel):
    """Información de un tipo de documento"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "curriculum_vitae",
            "name": "Curriculum Vitae",
            "description": "Hoja de vida de candidato a empleo",
            "azure_model": "prebuilt-resume",
            "is_custom_model": False,
            "supported_extensions": [".pdf"],
            "max_pages": 5
        }
    })
    
    type: str
    name: str
    description: str
    azure_model: str
    is_custom_model: bool
    supported_extensions: List[str]
    max_pages: int
    
    @classmethod
    def from_definition(cls, definition: DocumentTypeDefinition) -> "DocumentTypeInfo":
        """Crea instancia desde una definición"""
        return cls(
            type=definition.type.value,
            name=definition.name,
            description=definition.description,
            azure_model=definition.azure_model,
            is_custom_model=definition.is_custom_model,
            supported_extensions=definition.supported_extensions,
            max_pages=definition.max_pages
        )


class FieldInfo(BaseModel):
    """Información de un campo"""
    name: str
    description: str
    data_type: str
    required: bool
    example: Optional[Any] = None


class DocumentTypeDetail(BaseModel):
    """Detalle completo de un tipo de documento con sus campos"""
    type: str
    name: str
    description: str
    azure_model: str
    is_custom_model: bool
    supported_extensions: List[str]
    max_pages: int
    fields: List[FieldInfo]


class DocumentTypesResponse(BaseModel):
    """Response con lista de tipos de documento"""
    document_types: List[DocumentTypeInfo]
    total: int


# ============================================
# SCHEMAS DE PROCESAMIENTO
# ============================================

class DocumentProcessRequest(BaseModel):
    """Request para procesar documento (metadata)"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tipo_documento": "curriculum_vitae",
            "cliente_id": "cliente1",
            "metadata": {
                "candidato_id": "12345",
                "proceso_id": "PROC-2024-001"
            }
        }
    })
    
    tipo_documento: str = Field(
        ...,
        description="Tipo de documento a procesar",
        pattern="^(curriculum_vitae|titulo_universitario|concentracion_notas|cedula_identidad|cotizacion_afp)$"
    )
    cliente_id: Optional[str] = Field(
        default=None,
        description="ID del cliente (opcional, para tracking)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata adicional del documento"
    )
    
    @field_validator('tipo_documento')
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Valida que el tipo de documento sea válido"""
        try:
            DocumentType(v)
            return v
        except ValueError:
            valid_types = [t.value for t in DocumentType]
            raise ValueError(f"Tipo de documento inválido. Válidos: {', '.join(valid_types)}")


class ExperienciaLaboral(BaseModel):
    """Experiencia laboral extraída"""
    empresa: Optional[str] = None
    cargo: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    descripcion: Optional[str] = None


class Educacion(BaseModel):
    """Educación extraída"""
    institucion: Optional[str] = None
    carrera: Optional[str] = None
    grado: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None


class Asignatura(BaseModel):
    """Asignatura en concentración de notas"""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    nota: Optional[float] = None
    creditos: Optional[int] = None
    estado: Optional[str] = None


class CurriculumVitaeData(BaseModel):
    """Datos extraídos de un CV"""
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    experiencia_laboral: List[ExperienciaLaboral] = Field(default_factory=list)
    educacion: List[Educacion] = Field(default_factory=list)
    habilidades: List[str] = Field(default_factory=list)
    idiomas: List[Dict[str, str]] = Field(default_factory=list)


class TituloUniversitarioData(BaseModel):
    """Datos extraídos de un título universitario"""
    institucion: Optional[str] = None
    carrera: Optional[str] = None
    nombre_titular: Optional[str] = None
    rut_titular: Optional[str] = None
    fecha_emision: Optional[str] = None
    numero_titulo: Optional[str] = None
    grado_academico: Optional[str] = None
    duracion_anios: Optional[int] = None


class ConcentracionNotasData(BaseModel):
    """Datos extraídos de concentración de notas"""
    institucion: Optional[str] = None
    carrera: Optional[str] = None
    nombre_estudiante: Optional[str] = None
    rut_estudiante: Optional[str] = None
    fecha_emision: Optional[str] = None
    periodo_academico: Optional[str] = None
    asignaturas: List[Asignatura] = Field(default_factory=list)
    promedio_ponderado: Optional[float] = None
    promedio_semestral: Optional[float] = None
    total_creditos: Optional[int] = None
    total_asignaturas: Optional[int] = None


class CedulaIdentidadData(BaseModel):
    """Datos extraídos de cédula de identidad"""
    nombre: Optional[str] = None
    rut: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    nacionalidad: Optional[str] = None
    sexo: Optional[str] = None
    fecha_emision: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    numero_documento: Optional[str] = None
    lugar_nacimiento: Optional[str] = None


class CotizacionAFPData(BaseModel):
    """Datos extraídos de cotización AFP"""
    institucion: Optional[str] = None
    rut_afiliado: Optional[str] = None
    nombre_afiliado: Optional[str] = None
    fecha_cotizacion: Optional[str] = None
    periodo: Optional[str] = None
    tipo_cotizacion: Optional[str] = None
    monto_cotizacion_obligatoria: Optional[float] = None
    monto_cotizacion_voluntaria: Optional[float] = None
    monto_total: Optional[float] = None
    rentabilidad: Optional[float] = None
    saldo_total: Optional[float] = None
    numero_cuenta: Optional[str] = None


# Tipo unión para todos los datos de documento
DocumentData = Union[
    CurriculumVitaeData,
    TituloUniversitarioData,
    ConcentracionNotasData,
    CedulaIdentidadData,
    CotizacionAFPData,
    Dict[str, Any]
]


class DocumentProcessResponse(BaseModel):
    """Response del procesamiento de documento"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "document_type": "curriculum_vitae",
            "processed_at": "2024-01-15T10:30:00Z",
            "data": {
                "nombre": "Juan Pérez",
                "email": "juan.perez@email.com",
                "telefono": "+56912345678",
                "experiencia_laboral": [],
                "educacion": [],
                "habilidades": ["Python", "FastAPI"]
            },
            "confidence_score": 0.94,
            "processing_time_ms": 1250,
            "correlation_id": "abc12345"
        }
    })
    
    success: bool = Field(..., description="Indica si el procesamiento fue exitoso")
    status: ProcessingStatus = Field(..., description="Estado del procesamiento")
    document_type: str = Field(..., description="Tipo de documento procesado")
    processed_at: str = Field(..., description="Fecha/hora de procesamiento (ISO 8601)")
    data: Dict[str, Any] = Field(..., description="Datos extraídos del documento")
    confidence_score: float = Field(
        ..., 
        description="Puntaje de confianza (0-1)",
        ge=0.0,
        le=1.0
    )
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento en ms")
    correlation_id: str = Field(..., description="ID de correlación del request")
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Advertencias durante el procesamiento"
    )
    extracted_fields_count: Optional[int] = Field(
        default=None,
        description="Número de campos extraídos"
    )
    missing_fields: Optional[List[str]] = Field(
        default=None,
        description="Campos esperados que no se pudieron extraer"
    )


# ============================================
# SCHEMAS DE ERROR
# ============================================

class ErrorDetail(BaseModel):
    """Detalle de un error de validación"""
    field: Optional[str] = None
    message: str
    value: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Response de error estándar"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "INVALID_DOCUMENT_TYPE",
            "message": "Tipo de documento no soportado",
            "details": [
                {"field": "tipo_documento", "message": "Valor inválido", "value": "invalid_type"}
            ],
            "correlation_id": "abc12345",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    })
    
    success: bool = Field(default=False)
    error_code: ErrorCode = Field(..., description="Código de error")
    message: str = Field(..., description="Mensaje de error legible")
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detalles adicionales del error"
    )
    correlation_id: str = Field(..., description="ID de correlación")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="Fecha/hora del error"
    )
    path: Optional[str] = Field(default=None, description="Path del request")


# ============================================
# SCHEMAS DE HEALTH Y CONFIG
# ============================================

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    service: str
    timestamp: float
    version: Optional[str] = None


class ConfigResponse(BaseModel):
    """Response de configuración (sin datos sensibles)"""
    azure_configured: bool
    jwt_configured: bool
    max_file_size_mb: int
    allowed_file_types: List[str]
    allowed_extensions: List[str]
    jwt_expiration_minutes: int
    azure_timeout_seconds: int
    azure_max_retries: int
    log_level: str
    rate_limit_requests: int
    rate_limit_window_seconds: int


# ============================================
# SCHEMAS DE AZURE
# ============================================

class AzureProcessingResult(BaseModel):
    """Resultado del procesamiento en Azure"""
    success: bool
    raw_response: Optional[Dict[str, Any]] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    model_used: str = ""
    processing_time_ms: int = 0
    error_message: Optional[str] = None
    pages_processed: int = 0
