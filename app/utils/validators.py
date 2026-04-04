"""
Validaciones de archivos y datos de entrada
"""

import os
import magic
from typing import Optional, Tuple
from dataclasses import dataclass

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Resultado de una validación"""
    is_valid: bool
    error_message: str = ""
    mime_type: str = ""
    file_size: int = 0


class FileValidator:
    """Validador de archivos subidos"""
    
    # Mapeo de MIME types a extensiones
    MIME_TO_EXTENSION = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg"
    }
    
    # Extensiones a MIME types (para validación inversa)
    EXTENSION_TO_MIME = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }
    
    @classmethod
    def validate_file_size(cls, file_size: int) -> ValidationResult:
        """
        Valida que el tamaño del archivo no exceda el límite
        
        Args:
            file_size: Tamaño del archivo en bytes
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        max_size = settings.max_file_size_bytes
        
        if file_size > max_size:
            error_msg = (
                f"Archivo demasiado grande. El archivo excede el tamaño máximo permitido de "
                f"{settings.max_file_size_mb} MB "
                f"({file_size / (1024*1024):.2f} MB recibido)"
            )
            # Se omite el logging aquí para evitar errores de logger en el flujo de validación
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                file_size=file_size
            )
        
        return ValidationResult(is_valid=True, file_size=file_size)
    
    @classmethod
    def validate_mime_type(cls, content: bytes, declared_mime: Optional[str] = None) -> ValidationResult:
        """
        Valida el tipo MIME del archivo usando libmagic
        
        Args:
            content: Contenido binario del archivo
            declared_mime: Tipo MIME declarado por el cliente (opcional)
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        try:
            # Detectar MIME type real
            detected_mime = magic.from_buffer(content, mime=True)
            
            # Verificar si el tipo detectado está en la lista permitida
            allowed_types = settings.allowed_mime_types_list
            
            if detected_mime not in allowed_types:
                error_msg = (
                    f"Tipo de archivo no permitido. "
                    f"Detectado: {detected_mime}. "
                    f"Permitidos: {', '.join(allowed_types)}"
                )
                # Se omite el logging aquí para evitar errores de logger en el flujo de validación
                return ValidationResult(
                    is_valid=False,
                    error_message=error_msg,
                    mime_type=detected_mime
                )
            
            # Si se declaró un MIME type, verificar que coincida
            if declared_mime and declared_mime != detected_mime:
                logger.warning(
                    "MIME type mismatch",
                    extra={
                        "extra_data": {
                            "declared": declared_mime,
                            "detected": detected_mime
                        }
                    }
                )
                # No fallamos, solo advertimos
            
            return ValidationResult(is_valid=True, mime_type=detected_mime)
            
        except Exception as e:
            logger.error(f"Error detecting MIME type: {str(e)}")
            return ValidationResult(
                is_valid=False,
                error_message=f"Error al detectar tipo de archivo: {str(e)}"
            )
    
    @classmethod
    def validate_extension(cls, filename: str) -> ValidationResult:
        """
        Valida que la extensión del archivo sea permitida
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        _, ext = os.path.splitext(filename.lower())
        
        allowed_extensions = settings.allowed_extensions
        
        if ext not in allowed_extensions:
            error_msg = (
                f"Extensión de archivo no permitida: {ext}. "
                f"Permitidas: {', '.join(allowed_extensions)}"
            )
            # Se omite el logging aquí para evitar errores de logger en el flujo de validación
            return ValidationResult(is_valid=False, error_message=error_msg)
        
        return ValidationResult(is_valid=True)
    
    @classmethod
    def validate_file(
        cls,
        content: bytes,
        filename: str,
        declared_mime: Optional[str] = None
    ) -> ValidationResult:
        """
        Valida un archivo completo (tamaño, MIME type, extensión)
        
        Args:
            content: Contenido binario del archivo
            filename: Nombre del archivo
            declared_mime: Tipo MIME declarado (opcional)
            
        Returns:
            ValidationResult con el resultado completo
        """
        # Validar tamaño
        size_validation = cls.validate_file_size(len(content))
        if not size_validation.is_valid:
            return size_validation
        
        # Validar extensión
        ext_validation = cls.validate_extension(filename)
        if not ext_validation.is_valid:
            return ext_validation
        
        # Validar MIME type
        mime_validation = cls.validate_mime_type(content, declared_mime)
        if not mime_validation.is_valid:
            return mime_validation
        
        # Todo válido
        return ValidationResult(
            is_valid=True,
            mime_type=mime_validation.mime_type,
            file_size=len(content)
        )
    
    @classmethod
    def get_extension_from_mime(cls, mime_type: str) -> str:
        """Obtiene la extensión correspondiente a un MIME type"""
        return cls.MIME_TO_EXTENSION.get(mime_type, "")
    
    @classmethod
    def get_mime_from_extension(cls, extension: str) -> str:
        """Obtiene el MIME type correspondiente a una extensión"""
        ext = extension.lower() if not extension.startswith(".") else extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        return cls.EXTENSION_TO_MIME.get(ext, "")


class DocumentTypeValidator:
    """Validador de tipos de documento"""
    
    # Tipos de documento soportados
    SUPPORTED_TYPES = [
        "curriculum_vitae",
        "titulo_universitario",
        "concentracion_notas",
        "cedula_identidad",
        "cotizacion_afp"
    ]
    
    # Modelos Azure por tipo
    AZURE_MODELS = {
        "curriculum_vitae": "prebuilt-resume",
        "titulo_universitario": "custom",
        "concentracion_notas": "custom",
        "cedula_identidad": "prebuilt-idDocument",
        "cotizacion_afp": "custom"
    }
    
    @classmethod
    def is_valid_type(cls, document_type: str) -> bool:
        """Verifica si un tipo de documento es válido"""
        return document_type in cls.SUPPORTED_TYPES
    
    @classmethod
    def get_supported_types(cls) -> list:
        """Retorna lista de tipos soportados"""
        return cls.SUPPORTED_TYPES.copy()
    
    @classmethod
    def get_azure_model(cls, document_type: str) -> str:
        """Retorna el modelo Azure correspondiente al tipo de documento"""
        return cls.AZURE_MODELS.get(document_type, "")
    
    @classmethod
    def is_prebuilt_model(cls, document_type: str) -> bool:
        """Verifica si el tipo usa un modelo prebuilt de Azure"""
        model = cls.get_azure_model(document_type)
        return model.startswith("prebuilt-")
    
    @classmethod
    def is_custom_model(cls, document_type: str) -> bool:
        """Verifica si el tipo requiere un modelo custom"""
        return cls.get_azure_model(document_type) == "custom"
    
    @classmethod
    def validate(cls, document_type: str) -> ValidationResult:
        """
        Valida un tipo de documento
        
        Args:
            document_type: Tipo de documento a validar
            
        Returns:
            ValidationResult con el resultado
        """
        if not document_type:
            return ValidationResult(
                is_valid=False,
                error_message="El tipo de documento es requerido"
            )
        
        if not cls.is_valid_type(document_type):
            error_msg = (
                f"Tipo de documento no soportado: '{document_type}'. "
                f"Tipos permitidos: {', '.join(cls.SUPPORTED_TYPES)}"
            )
            # Se omite el logging aquí para evitar errores de logger en el flujo de validación
            return ValidationResult(is_valid=False, error_message=error_msg)
        
        return ValidationResult(is_valid=True)


class AzureModelValidator:
    """Validador de modelos Azure prebuilt directos"""

    ALLOWED_PREBUILT_MODELS = {
        "prebuilt-document",
        "prebuilt-read",
        "prebuilt-layout",
        "prebuilt-idDocument",
        "prebuilt-businessCard",
        "prebuilt-healthInsuranceCard",
        "prebuilt-marriageCertificate",
        "prebuilt-invoice",
        "prebuilt-receipt",
        "prebuilt-taxDocument",
        "prebuilt-bankStatement",
        "prebuilt-creditCard",
        "prebuilt-payStub",
        "prebuilt-mortgageDocuments",
        "prebuilt-contract"
    }

    @classmethod
    def is_valid_azure_model(cls, model_id: str) -> bool:
        """Verifica si el ID corresponde a un modelo Azure prebuilt admitido"""
        return model_id in cls.ALLOWED_PREBUILT_MODELS

    @classmethod
    def get_allowed_models(cls) -> list:
        """Retorna la lista de modelos Azure prebuilt admitidos"""
        return sorted(cls.ALLOWED_PREBUILT_MODELS)


def validate_token_request(
    client_name: str,
    action_name: str,
    shared_key: str
) -> Tuple[bool, str]:
    """
    Valida los campos de una solicitud de token
    
    Args:
        client_name: Nombre del cliente
        action_name: Nombre de la acción
        shared_key: Clave compartida
        
    Returns:
        Tuple (es_válido, mensaje_error)
    """
    if not client_name or not client_name.strip():
        return False, "client_name es requerido"
    
    if not action_name or not action_name.strip():
        return False, "action_name es requerido"
    
    if not shared_key or not shared_key.strip():
        return False, "shared_key es requerido"
    
    return True, ""
