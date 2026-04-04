"""
Servicio principal de procesamiento de documentos
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.config import settings
from app.models.document_types import DocumentType, get_document_type_definition, get_expected_fields
from app.models.schemas import (
    DocumentProcessResponse,
    ProcessingStatus,
    AzureProcessingResult
)
from app.azure_client import get_azure_client
from app.services.model_mapper import map_azure_response, ModelMapperFactory
from app.utils.logger import LoggerMixin, log_document_processed, get_correlation_id
from app.utils.validators import FileValidator, DocumentTypeValidator


class DocumentProcessingError(Exception):
    """Error durante el procesamiento de documento"""
    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DocumentProcessor(LoggerMixin):
    """
    Servicio principal para procesamiento de documentos
    
    Flujo:
    1. Validar tipo de documento
    2. Validar archivo
    3. Enviar a Azure Form Recognizer
    4. Mapear respuesta a JSON limpio
    5. Calcular métricas y retornar respuesta
    """
    
    def __init__(self):
        super().__init__()
        self.azure_client = get_azure_client()
    
    async def process_document(
        self,
        document_type: DocumentType,
        file_content: bytes,
        filename: str,
        client_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentProcessResponse:
        """
        Procesa un documento completo
        
        Args:
            document_type: Tipo de documento
            file_content: Contenido binario del archivo
            filename: Nombre del archivo
            client_name: Nombre del cliente (para logging)
            metadata: Metadata adicional
            
        Returns:
            DocumentProcessResponse con el resultado
        """
        start_time = time.time()
        
        self.log_info(
            "Starting document processing",
            document_type=document_type.value,
            filename=filename,
            file_size_bytes=len(file_content),
            client_name=client_name
        )
        
        try:
            # Paso 1: Validar tipo de documento
            self._validate_document_type(document_type)
            
            # Paso 2: Validar archivo
            validation_result = self._validate_file(file_content, filename)
            if not validation_result.is_valid:
                raise DocumentProcessingError(
                    validation_result.error_message,
                    "VALIDATION_ERROR"
                )
            
            # Paso 3: Procesar con Azure
            azure_result = self._process_with_azure(document_type, file_content)
            
            if not azure_result.success:
                raise DocumentProcessingError(
                    azure_result.error_message or "Azure processing failed",
                    "AZURE_ERROR"
                )
            
            # Paso 4: Mapear respuesta
            mapped_data = self._map_response(document_type, azure_result.extracted_data)
            
            # Paso 5: Calcular métricas
            extracted_count, missing_fields = self._calculate_metrics(
                document_type, mapped_data
            )
            
            # Calcular tiempo total
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Determinar estado
            status = self._determine_status(
                azure_result.confidence_score,
                missing_fields
            )
            
            # Log de documento procesado
            log_document_processed(
                document_type=document_type.value,
                confidence_score=azure_result.confidence_score,
                processing_time_ms=processing_time_ms,
                file_size_bytes=len(file_content),
                client_name=client_name
            )
            
            self.log_info(
                "Document processing completed",
                document_type=document_type.value,
                confidence=azure_result.confidence_score,
                processing_time_ms=processing_time_ms,
                extracted_fields=extracted_count
            )
            
            response_warnings = []
            if azure_result.warnings:
                response_warnings.extend(azure_result.warnings)
            generated_warnings = self._generate_warnings(missing_fields, azure_result.confidence_score)
            if generated_warnings:
                response_warnings.extend(generated_warnings)

            return DocumentProcessResponse(
                success=True,
                status=status,
                document_type=document_type.value,
                processed_at=datetime.utcnow().isoformat() + "Z",
                data=mapped_data,
                confidence_score=azure_result.confidence_score,
                processing_time_ms=processing_time_ms,
                correlation_id=get_correlation_id(),
                warnings=response_warnings if response_warnings else None,
                extracted_fields_count=extracted_count,
                missing_fields=missing_fields if missing_fields else None
            )
            
        except DocumentProcessingError as e:
            self.log_error(
                f"Document processing failed: {e.message}",
                document_type=document_type.value,
                error_code=e.error_code
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return DocumentProcessResponse(
                success=False,
                status=ProcessingStatus.ERROR,
                document_type=document_type.value,
                processed_at=datetime.utcnow().isoformat() + "Z",
                data={},
                confidence_score=0.0,
                processing_time_ms=processing_time_ms,
                correlation_id=get_correlation_id(),
                warnings=[f"{e.error_code}: {e.message}"]
            )
        
        except Exception as e:
            self.log_error(
                f"Unexpected error during processing: {str(e)}",
                document_type=document_type.value,
                exc_info=True
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return DocumentProcessResponse(
                success=False,
                status=ProcessingStatus.ERROR,
                document_type=document_type.value,
                processed_at=datetime.utcnow().isoformat() + "Z",
                data={},
                confidence_score=0.0,
                processing_time_ms=processing_time_ms,
                correlation_id=get_correlation_id(),
                warnings=[f"INTERNAL_ERROR: {str(e)}"]
            )
    
    def _validate_document_type(self, document_type: DocumentType) -> None:
        """Valida que el tipo de documento sea soportado"""
        validation = DocumentTypeValidator.validate(document_type.value)
        
        if not validation.is_valid:
            raise DocumentProcessingError(
                validation.error_message,
                "INVALID_DOCUMENT_TYPE"
            )
        
        # Verificar que Azure esté configurado
        if not self.azure_client.is_configured:
            raise DocumentProcessingError(
                "Azure Form Recognizer not configured",
                "CONFIGURATION_ERROR"
            )
    
    def _validate_file(self, file_content: bytes, filename: str):
        """Valida el archivo"""
        return FileValidator.validate_file(file_content, filename)
    
    def _process_with_azure(
        self,
        document_type: DocumentType,
        file_content: bytes
    ) -> AzureProcessingResult:
        """Procesa el documento con Azure"""
        return self.azure_client.analyze_document(document_type, file_content)
    
    def _map_response(
        self,
        document_type: DocumentType,
        azure_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mapea la respuesta de Azure a formato limpio"""
        try:
            return map_azure_response(document_type, azure_data)
        except Exception as e:
            self.log_error(
                f"Error mapping response: {str(e)}",
                document_type=document_type.value,
                exc_info=True
            )
            # Retornar datos sin mapear si falla
            return azure_data
    
    def _calculate_metrics(
        self,
        document_type: DocumentType,
        mapped_data: Dict[str, Any]
    ) -> Tuple[int, List[str]]:
        """
        Calcula métricas de extracción
        
        Returns:
            Tuple (campos_extraidos, campos_faltantes)
        """
        expected_fields = get_expected_fields(document_type)
        
        extracted_count = 0
        missing_fields = []
        
        for field in expected_fields:
            if not field.required:
                continue
            
            value = mapped_data.get(field.name)
            
            # Considerar extraído si tiene valor no vacío
            if value is not None and value != [] and value != {} and value != "":
                extracted_count += 1
            else:
                missing_fields.append(field.name)
        
        return extracted_count, missing_fields
    
    def _determine_status(
        self,
        confidence_score: float,
        missing_fields: List[str]
    ) -> ProcessingStatus:
        """Determina el estado del procesamiento"""
        # Si hay campos faltantes requeridos, es parcial
        if missing_fields:
            return ProcessingStatus.PARTIAL
        
        # Si el confidence es bajo, es parcial
        if confidence_score < 0.7:
            return ProcessingStatus.PARTIAL
        
        return ProcessingStatus.SUCCESS
    
    def _generate_warnings(
        self,
        missing_fields: List[str],
        confidence_score: float
    ) -> List[str]:
        """Genera advertencias basadas en el resultado"""
        warnings = []
        
        if missing_fields:
            warnings.append(
                f"Campos no detectados: {', '.join(missing_fields[:5])}"
                + (f" y {len(missing_fields) - 5} más" if len(missing_fields) > 5 else "")
            )
        
        if confidence_score < 0.5:
            warnings.append("Baja confianza en la extracción (< 50%)")
        elif confidence_score < 0.7:
            warnings.append("Confianza moderada en la extracción (< 70%)")
        
        return warnings if warnings else None
    
    def get_document_info(self, document_type: DocumentType) -> Dict[str, Any]:
        """Obtiene información sobre un tipo de documento"""
        definition = get_document_type_definition(document_type)
        
        if not definition:
            return {"error": "Document type not found"}
        
        return {
            "type": definition.type.value,
            "name": definition.name,
            "description": definition.description,
            "azure_model": definition.azure_model,
            "is_custom_model": definition.is_custom_model,
            "supported_extensions": definition.supported_extensions,
            "max_pages": definition.max_pages,
            "expected_fields_count": len(definition.fields),
            "required_fields_count": len([f for f in definition.fields if f.required])
        }
    
    def get_supported_types(self) -> List[Dict[str, Any]]:
        """Obtiene lista de tipos soportados con información"""
        types = []
        for doc_type in DocumentType:
            info = self.get_document_info(doc_type)
            if "error" not in info:
                types.append(info)
        return types


# Instancia singleton del procesador
_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Obtiene la instancia singleton del procesador"""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor


def reset_document_processor() -> None:
    """Resetea la instancia del procesador (útil para testing)"""
    global _processor
    _processor = None
