"""
Cliente Azure Form Recognizer con manejo de timeouts y retry logic
"""

import time
from typing import Optional, Dict, Any, BinaryIO
from dataclasses import dataclass

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import (
    HttpResponseError,
    ServiceRequestError,
    ClientAuthenticationError,
    ResourceNotFoundError
)

from app.config import settings
from app.models.document_types import DocumentType, get_document_type_definition
from app.models.schemas import AzureProcessingResult
from app.utils.logger import LoggerMixin, log_azure_request, get_correlation_id


@dataclass
class AzureConfig:
    """Configuración de conexión Azure"""
    endpoint: str
    api_key: str
    timeout_seconds: int = 30
    max_retries: int = 2


class AzureFormRecognizerClient(LoggerMixin):
    """
    Cliente para Azure Form Recognizer con:
    - Timeout configurable (default 30s)
    - Retry logic (default 2 reintentos)
    - Manejo de errores específicos
    - Logging estructurado
    """
    
    # Modelos prebuilt de Azure
    PREBUILT_MODELS = {
        DocumentType.CURRICULUM_VITAE: "prebuilt-resume",
        DocumentType.CEDULA_IDENTIDAD: "prebuilt-identityDocument",
    }
    
    # Modelos custom (IDs desde configuración)
    CUSTOM_MODELS = {
        DocumentType.TITULO_UNIVERSITARIO: settings.custom_model_titulo,
        DocumentType.CONCENTRACION_NOTAS: settings.custom_model_notas,
        DocumentType.COTIZACION_AFP: settings.custom_model_afp,
    }
    
    def __init__(self, config: Optional[AzureConfig] = None):
        """
        Inicializa el cliente de Azure Form Recognizer
        
        Args:
            config: Configuración de Azure (opcional, usa settings por defecto)
        """
        super().__init__()
        
        self.config = config or AzureConfig(
            endpoint=settings.azure_form_recognizer_endpoint,
            api_key=settings.azure_form_recognizer_api_key,
            timeout_seconds=settings.azure_timeout_seconds,
            max_retries=settings.azure_max_retries
        )
        
        self._client: Optional[DocumentAnalysisClient] = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Inicializa el cliente de Azure"""
        if not self.config.endpoint or not self.config.api_key:
            self.log_warning(
                "Azure credentials not configured",
                endpoint_configured=bool(self.config.endpoint),
                api_key_configured=bool(self.config.api_key)
            )
            return
        
        try:
            credential = AzureKeyCredential(self.config.api_key)
            self._client = DocumentAnalysisClient(
                endpoint=self.config.endpoint,
                credential=credential
            )
            self.log_info(
                "Azure Form Recognizer client initialized",
                endpoint=self.config.endpoint,
                timeout=self.config.timeout_seconds,
                max_retries=self.config.max_retries
            )
        except Exception as e:
            self.log_error(
                f"Failed to initialize Azure client: {str(e)}",
                endpoint=self.config.endpoint
            )
            raise
    
    @property
    def is_configured(self) -> bool:
        """Verifica si el cliente está configurado correctamente"""
        return (
            self._client is not None and
            bool(self.config.endpoint) and
            bool(self.config.api_key)
        )
    
    def _get_model_id(self, document_type: DocumentType) -> str:
        """
        Obtiene el ID del modelo Azure para un tipo de documento
        
        Args:
            document_type: Tipo de documento
            
        Returns:
            ID del modelo Azure
        """
        if document_type in self.PREBUILT_MODELS:
            return self.PREBUILT_MODELS[document_type]
        
        if document_type in self.CUSTOM_MODELS:
            return self.CUSTOM_MODELS[document_type]
        
        # Fallback a documento genérico
        return "prebuilt-document"
    
    def _is_prebuilt_model(self, model_id: str) -> bool:
        """Verifica si es un modelo prebuilt"""
        return model_id.startswith("prebuilt-")
    
    def _process_with_retry(
        self,
        document_type: DocumentType,
        file_content: bytes,
        model_id: str
    ) -> AzureProcessingResult:
        """
        Procesa un documento con lógica de retry
        
        Args:
            document_type: Tipo de documento
            file_content: Contenido binario del archivo
            model_id: ID del modelo Azure
            
        Returns:
            AzureProcessingResult con el resultado
        """
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.log_debug(
                    f"Azure request attempt {attempt + 1}/{self.config.max_retries + 1}",
                    document_type=document_type.value,
                    model_id=model_id
                )
                
                # Iniciar análisis
                poller = self._client.begin_analyze_document(
                    model_id=model_id,
                    document=file_content
                )
                
                # Esperar resultado con timeout
                result = poller.result(timeout=self.config.timeout_seconds)
                
                # Extraer datos
                extracted_data = self._extract_data_from_result(result, document_type)
                confidence = self._calculate_confidence(result)
                
                self.log_info(
                    f"Azure request successful on attempt {attempt + 1}",
                    document_type=document_type.value,
                    model_id=model_id,
                    pages=len(result.pages) if result.pages else 0,
                    confidence=confidence
                )
                
                return AzureProcessingResult(
                    success=True,
                    raw_response=self._result_to_dict(result),
                    extracted_data=extracted_data,
                    confidence_score=confidence,
                    model_used=model_id,
                    pages_processed=len(result.pages) if result.pages else 0
                )
                
            except TimeoutError as e:
                last_error = f"Timeout after {self.config.timeout_seconds}s: {str(e)}"
                self.log_warning(
                    f"Azure request timeout (attempt {attempt + 1})",
                    document_type=document_type.value,
                    timeout=self.config.timeout_seconds
                )
                
            except HttpResponseError as e:
                last_error = f"HTTP error {e.status_code}: {e.message}"

                if e.status_code == 404 and model_id == "prebuilt-identityDocument":
                    # Fallback a modelo genérico cuando el recurso no reconoce el modelo de identidad
                    self.log_warning(
                        "Azure model not found, falling back to prebuilt-document",
                        extra={
                            "extra_data": {
                                "document_type": document_type.value,
                                "model_id": model_id,
                                "fallback_model_id": "prebuilt-document",
                                "status_code": e.status_code,
                                "error": e.message
                            }
                        }
                    )
                    model_id = "prebuilt-document"
                    continue

                self.log_error(
                    f"Azure HTTP error (attempt {attempt + 1})",
                    status_code=e.status_code,
                    error=e.message,
                    document_type=document_type.value
                )
                # No reintentar errores 4xx
                if e.status_code and 400 <= e.status_code < 500:
                    break

            except ServiceRequestError as e:
                last_error = f"Service request error: {str(e)}"
                self.log_error(
                    f"Azure service request error (attempt {attempt + 1})",
                    error=str(e),
                    document_type=document_type.value
                )
                
            except ClientAuthenticationError as e:
                last_error = f"Authentication error: {str(e)}"
                self.log_error(
                    "Azure authentication error",
                    error=str(e),
                    document_type=document_type.value
                )
                # No reintentar errores de autenticación
                break
                
            except ResourceNotFoundError as e:
                last_error = f"Resource not found: {str(e)}"
                if model_id == "prebuilt-identityDocument":
                    self.log_warning(
                        "Azure model not found (ResourceNotFoundError), falling back to prebuilt-document",
                        extra={
                            "extra_data": {
                                "document_type": document_type.value,
                                "model_id": model_id,
                                "fallback_model_id": "prebuilt-document",
                                "error": str(e)
                            }
                        }
                    )
                    model_id = "prebuilt-document"
                    continue

                self.log_error(
                    "Azure resource not found",
                    error=str(e),
                    model_id=model_id
                )
                # No reintentar si el modelo no existe
                break
                
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                self.log_error(
                    f"Azure unexpected error (attempt {attempt + 1})",
                    error=str(e),
                    document_type=document_type.value,
                    exc_info=True
                )
            
            # Esperar antes de reintentar (backoff exponencial)
            if attempt < self.config.max_retries:
                wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s...
                self.log_debug(f"Waiting {wait_time}s before retry")
                time.sleep(wait_time)
        
        # Todos los intentos fallaron
        self.log_error(
            "All Azure request attempts failed",
            document_type=document_type.value,
            model_id=model_id,
            last_error=last_error,
            total_attempts=self.config.max_retries + 1
        )
        
        return AzureProcessingResult(
            success=False,
            error_message=last_error,
            model_used=model_id
        )
    
    def _extract_data_from_result(
        self,
        result: Any,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Extrae datos estructurados del resultado de Azure
        
        Args:
            result: Resultado de Azure Form Recognizer
            document_type: Tipo de documento
            
        Returns:
            Diccionario con datos extraídos
        """
        extracted = {}
        
        if not result.documents:
            return extracted
        
        # Tomar el primer documento (normalmente solo hay uno)
        document = result.documents[0]
        
        # Extraer campos según el tipo de documento
        if document.fields:
            for field_name, field_value in document.fields.items():
                extracted[field_name] = self._parse_field_value(field_value)
        
        return extracted
    
    def _parse_field_value(self, field_value: Any) -> Any:
        """
        Parsea un valor de campo de Azure
        
        Args:
            field_value: Valor del campo de Azure
            
        Returns:
            Valor parseado
        """
        if field_value is None:
            return None
        
        # Si es un campo simple
        if hasattr(field_value, 'value'):
            return field_value.value
        
        # Si es una lista/array
        if hasattr(field_value, 'value_array'):
            return [self._parse_field_value(item) for item in field_value.value_array]
        
        # Si es un objeto
        if hasattr(field_value, 'value_object'):
            return {
                k: self._parse_field_value(v)
                for k, v in field_value.value_object.items()
            }
        
        # Valor directo
        return str(field_value) if field_value is not None else None
    
    def _calculate_confidence(self, result: Any) -> float:
        """
        Calcula el puntaje de confianza promedio
        
        Args:
            result: Resultado de Azure
            
        Returns:
            Puntaje de confianza (0-1)
        """
        confidences = []
        
        if result.documents:
            for doc in result.documents:
                if hasattr(doc, 'confidence') and doc.confidence:
                    confidences.append(doc.confidence)
                
                if doc.fields:
                    for field in doc.fields.values():
                        if hasattr(field, 'confidence') and field.confidence:
                            confidences.append(field.confidence)
        
        if not confidences:
            return 0.0
        
        return round(sum(confidences) / len(confidences), 3)
    
    def _result_to_dict(self, result: Any) -> Dict[str, Any]:
        """
        Convierte el resultado de Azure a diccionario
        
        Args:
            result: Resultado de Azure
            
        Returns:
            Diccionario con el resultado
        """
        return {
            "model_id": result.model_id if hasattr(result, 'model_id') else None,
            "pages_count": len(result.pages) if result.pages else 0,
            "documents_count": len(result.documents) if result.documents else 0,
            "correlation_id": get_correlation_id()
        }
    
    def analyze_document(
        self,
        document_type: DocumentType,
        file_content: bytes
    ) -> AzureProcessingResult:
        """
        Analiza un documento usando Azure Form Recognizer
        
        Args:
            document_type: Tipo de documento
            file_content: Contenido binario del archivo
            
        Returns:
            AzureProcessingResult con el resultado del análisis
        """
        start_time = time.time()
        
        # Validar configuración
        if not self.is_configured:
            error_msg = "Azure Form Recognizer not configured"
            self.log_error(error_msg)
            
            log_azure_request(
                document_type=document_type.value,
                model_used="none",
                success=False,
                duration_ms=(time.time() - start_time) * 1000,
                error=error_msg
            )
            
            return AzureProcessingResult(
                success=False,
                error_message=error_msg
            )
        
        # Obtener modelo
        model_id = self._get_model_id(document_type)
        
        self.log_info(
            "Starting document analysis",
            document_type=document_type.value,
            model_id=model_id,
            file_size_bytes=len(file_content)
        )
        
        # Procesar con retry
        result = self._process_with_retry(document_type, file_content, model_id)
        
        # Calcular tiempo total
        duration_ms = (time.time() - start_time) * 1000
        result.processing_time_ms = int(duration_ms)
        
        # Log del resultado
        log_azure_request(
            document_type=document_type.value,
            model_used=model_id,
            success=result.success,
            duration_ms=duration_ms,
            error=result.error_message if not result.success else None
        )
        
        return result
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un modelo
        
        Args:
            model_id: ID del modelo
            
        Returns:
            Información del modelo
        """
        if not self.is_configured:
            return {"error": "Azure not configured"}
        
        try:
            # Para modelos prebuilt, retornar info básica
            if self._is_prebuilt_model(model_id):
                return {
                    "model_id": model_id,
                    "type": "prebuilt",
                    "description": f"Azure prebuilt model: {model_id}"
                }
            
            # Para modelos custom, intentar obtener info
            model = self._client.get_model(model_id)
            return {
                "model_id": model.model_id,
                "type": "custom",
                "description": model.description if hasattr(model, 'description') else None,
                "created_on": model.created_on.isoformat() if hasattr(model, 'created_on') else None
            }
            
        except Exception as e:
            self.log_error(f"Error getting model info: {str(e)}", model_id=model_id)
            return {
                "model_id": model_id,
                "error": str(e)
            }
    
    def list_available_models(self) -> Dict[str, Any]:
        """
        Lista los modelos disponibles
        
        Returns:
            Diccionario con modelos prebuilt y custom
        """
        return {
            "prebuilt_models": [
                {"id": v, "document_type": k.value}
                for k, v in self.PREBUILT_MODELS.items()
            ],
            "custom_models": [
                {"id": v, "document_type": k.value}
                for k, v in self.CUSTOM_MODELS.items()
            ],
            "azure_configured": self.is_configured
        }


# Instancia singleton del cliente
_azure_client: Optional[AzureFormRecognizerClient] = None


def get_azure_client() -> AzureFormRecognizerClient:
    """Obtiene la instancia singleton del cliente Azure"""
    global _azure_client
    if _azure_client is None:
        _azure_client = AzureFormRecognizerClient()
    return _azure_client


def reset_azure_client() -> None:
    """Resetea la instancia del cliente (útil para testing)"""
    global _azure_client
    _azure_client = None
