"""
Configuración de la aplicación usando Pydantic Settings
"""

import os
from typing import Dict, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación"""
    
    # ============================================
    # CONFIGURACIÓN AZURE FORM RECOGNIZER
    # ============================================
    azure_form_recognizer_endpoint: str = Field(
        default="",
        alias="AZURE_FORM_RECOGNIZER_ENDPOINT",
        description="Endpoint del servicio Azure Form Recognizer"
    )
    azure_form_recognizer_api_key: str = Field(
        default="",
        alias="AZURE_FORM_RECOGNIZER_API_KEY",
        description="API Key de Azure Form Recognizer"
    )
    
    # ============================================
    # CONFIGURACIÓN JWT
    # ============================================
    jwt_secret_key: str = Field(
        default="",
        alias="JWT_SECRET_KEY",
        description="Clave secreta para firmar tokens JWT"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
        description="Algoritmo de firma JWT"
    )
    jwt_expiration_minutes: int = Field(
        default=30,
        alias="JWT_EXPIRATION_MINUTES",
        description="Tiempo de expiración del token en minutos"
    )
    
    # ============================================
    # CLIENTES PERMITIDOS
    # ============================================
    allowed_clients: str = Field(
        default="",
        alias="ALLOWED_CLIENTS",
        description="Clientes permitidos en formato client:key,client2:key2"
    )
    
    # ============================================
    # CONFIGURACIÓN DE LA APLICACIÓN
    # ============================================
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Nivel de logging (DEBUG, INFO, WARNING, ERROR)"
    )
    max_file_size_mb: int = Field(
        default=10,
        alias="MAX_FILE_SIZE_MB",
        description="Tamaño máximo de archivo en MB"
    )
    allowed_file_types: str = Field(
        default="application/pdf,image/png,image/jpeg",
        alias="ALLOWED_FILE_TYPES",
        description="Tipos MIME de archivos permitidos"
    )
    
    # ============================================
    # CONFIGURACIÓN REDIS (Rate Limiting)
    # ============================================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="URL de conexión a Redis"
    )
    rate_limit_requests: int = Field(
        default=100,
        alias="RATE_LIMIT_REQUESTS",
        description="Número máximo de requests por ventana"
    )
    rate_limit_window: int = Field(
        default=3600,
        alias="RATE_LIMIT_WINDOW",
        description="Ventana de tiempo para rate limiting en segundos"
    )
    
    # ============================================
    # CONFIGURACIÓN DE MODELOS CUSTOM
    # ============================================
    custom_model_titulo: str = Field(
        default="model-titulo-universitario",
        alias="CUSTOM_MODEL_TITULO",
        description="ID del modelo custom para títulos universitarios"
    )
    custom_model_notas: str = Field(
        default="model-concentracion-notas",
        alias="CUSTOM_MODEL_NOTAS",
        description="ID del modelo custom para concentración de notas"
    )
    custom_model_afp: str = Field(
        default="model-cotizacion-afp",
        alias="CUSTOM_MODEL_AFP",
        description="ID del modelo custom para cotizaciones AFP"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    # ============================================
    # PROPIEDADES CALCULADAS
    # ============================================
    
    @property
    def max_file_size_bytes(self) -> int:
        """Retorna el tamaño máximo en bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def allowed_mime_types_list(self) -> List[str]:
        """Retorna lista de tipos MIME permitidos"""
        return [t.strip() for t in self.allowed_file_types.split(",")]
    
    @property
    def allowed_extensions(self) -> List[str]:
        """Retorna lista de extensiones permitidas basadas en MIME types"""
        extension_map = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg"
        }
        return [extension_map.get(mime, "") for mime in self.allowed_mime_types_list if mime in extension_map]
    
    @property
    def clients_dict(self) -> Dict[str, str]:
        """Parsea ALLOWED_CLIENTS en un diccionario {client_name: shared_key}"""
        clients = {}
        if not self.allowed_clients:
            return clients
        
        for client_pair in self.allowed_clients.split(","):
            if ":" in client_pair:
                name, key = client_pair.strip().split(":", 1)
                clients[name.strip()] = key.strip()
        return clients
    
    @property
    def azure_timeout_seconds(self) -> int:
        """Timeout para llamadas a Azure"""
        return 30
    
    @property
    def azure_max_retries(self) -> int:
        """Número máximo de reintentos para Azure"""
        return 2


# Instancia global de configuración
settings = Settings()
