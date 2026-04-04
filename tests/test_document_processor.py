"""
Tests para el servicio de procesamiento de documentos
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.services.document_processor import (
    DocumentProcessor,
    DocumentProcessingError,
    get_document_processor
)
from app.models.document_types import DocumentType
from app.models.schemas import ProcessingStatus, AzureProcessingResult
from app.azure_client import AzureFormRecognizerClient


class TestDocumentProcessor:
    """Tests para DocumentProcessor"""
    
    def test_singleton_pattern(self):
        """Test que el procesador es singleton"""
        processor1 = get_document_processor()
        processor2 = get_document_processor()
        assert processor1 is processor2
    
    @pytest.mark.asyncio
    async def test_process_document_success(self, sample_pdf_bytes, mock_azure_response):
        """Test procesamiento exitoso de documento"""
        processor = DocumentProcessor()
        
        # Mock del cliente Azure
        mock_azure_result = AzureProcessingResult(
            success=True,
            extracted_data={
                "Name": Mock(value="Juan Pérez"),
                "Email": Mock(value="juan@email.com")
            },
            confidence_score=0.95,
            model_used="prebuilt-resume",
            pages_processed=1,
            processing_time_ms=1000
        )
        
        with patch.object(processor.azure_client, 'analyze_document', return_value=mock_azure_result):
            result = await processor.process_document(
                document_type=DocumentType.CURRICULUM_VITAE,
                file_content=sample_pdf_bytes,
                filename="test_cv.pdf",
                client_name="test_client"
            )
        
        assert result.success is True
        assert result.status in [ProcessingStatus.SUCCESS, ProcessingStatus.PARTIAL]
        assert result.document_type == "curriculum_vitae"
        assert result.confidence_score == 0.95
        assert result.processing_time_ms > 0
        assert result.correlation_id is not None
    
    @pytest.mark.asyncio
    async def test_process_document_invalid_type(self, sample_pdf_bytes):
        """Test procesamiento con tipo de documento inválido"""
        processor = DocumentProcessor()
        
        # Crear tipo inválido
        with pytest.raises(ValueError):
            invalid_type = DocumentType("invalid_type")
    
    @pytest.mark.asyncio
    async def test_process_document_azure_not_configured(self, sample_pdf_bytes, monkeypatch):
        """Test procesamiento cuando Azure no está configurado"""
        processor = DocumentProcessor()
        
        # Desconfigurar Azure
        monkeypatch.setattr(processor.azure_client.config, 'endpoint', '')
        monkeypatch.setattr(processor.azure_client.config, 'api_key', '')
        processor.azure_client._client = None
        
        result = await processor.process_document(
            document_type=DocumentType.CURRICULUM_VITAE,
            file_content=sample_pdf_bytes,
            filename="test_cv.pdf"
        )
        
        assert result.success is False
        assert result.status == ProcessingStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_process_document_azure_error(self, sample_pdf_bytes):
        """Test procesamiento cuando Azure retorna error"""
        processor = DocumentProcessor()
        
        mock_azure_result = AzureProcessingResult(
            success=False,
            error_message="Azure service error",
            model_used="prebuilt-resume"
        )
        
        with patch.object(processor.azure_client, 'analyze_document', return_value=mock_azure_result):
            result = await processor.process_document(
                document_type=DocumentType.CURRICULUM_VITAE,
                file_content=sample_pdf_bytes,
                filename="test_cv.pdf"
            )
        
        assert result.success is False
        assert result.status == ProcessingStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_process_document_file_too_large(self, monkeypatch):
        """Test procesamiento con archivo demasiado grande"""
        processor = DocumentProcessor()
        
        # Crear archivo grande
        large_content = b"x" * (20 * 1024 * 1024)  # 20 MB
        
        result = await processor.process_document(
            document_type=DocumentType.CURRICULUM_VITAE,
            file_content=large_content,
            filename="large.pdf"
        )
        
        assert result.success is False
        assert "demasiado grande" in result.warnings[0].lower() or "too large" in result.warnings[0].lower()
    
    @pytest.mark.asyncio
    async def test_process_document_low_confidence(self, sample_pdf_bytes):
        """Test procesamiento con baja confianza"""
        processor = DocumentProcessor()
        
        mock_azure_result = AzureProcessingResult(
            success=True,
            extracted_data={},
            confidence_score=0.4,
            model_used="prebuilt-resume",
            pages_processed=1,
            processing_time_ms=1000
        )
        
        with patch.object(processor.azure_client, 'analyze_document', return_value=mock_azure_result):
            result = await processor.process_document(
                document_type=DocumentType.CURRICULUM_VITAE,
                file_content=sample_pdf_bytes,
                filename="test_cv.pdf"
            )
        
        assert result.success is True
        assert result.status == ProcessingStatus.PARTIAL
        assert any("confianza" in w.lower() or "confidence" in w.lower() for w in (result.warnings or []))

    @pytest.mark.asyncio
    async def test_process_document_includes_azure_fallback_warning(self, sample_pdf_bytes):
        """Test que incluye advertencia de fallback de Azure en la respuesta"""
        processor = DocumentProcessor()
        
        mock_azure_result = AzureProcessingResult(
            success=True,
            extracted_data={"Name": "Juan Pérez"},
            confidence_score=0.95,
            model_used="prebuilt-document",
            pages_processed=1,
            processing_time_ms=1000,
            warnings=["Modelo no encontrado: prebuilt-idDocument. Se usó prebuilt-document como fallback."]
        )
        
        with patch.object(processor.azure_client, 'analyze_document', return_value=mock_azure_result):
            result = await processor.process_document(
                document_type=DocumentType.CEDULA_IDENTIDAD,
                file_content=sample_pdf_bytes,
                filename="frente.png"
            )
        
        assert result.success is True
        assert result.warnings is not None
        assert any("fallback" in w.lower() or "modelo no encontrado" in w.lower() for w in result.warnings)
    
    def test_get_document_info(self):
        """Test obtención de información de tipo de documento"""
        processor = DocumentProcessor()
        
        info = processor.get_document_info(DocumentType.CURRICULUM_VITAE)
        
        assert "type" in info
        assert "name" in info
        assert "azure_model" in info
        assert info["type"] == "curriculum_vitae"
    
    def test_get_document_info_not_found(self):
        """Test obtención de info de tipo no existente"""
        processor = DocumentProcessor()
        
        # Crear un tipo que no existe en las definiciones
        mock_type = Mock()
        mock_type.value = "non_existent"
        
        info = processor.get_document_info(mock_type)
        
        assert "error" in info
    
    def test_get_supported_types(self):
        """Test obtención de tipos soportados"""
        processor = DocumentProcessor()
        
        types = processor.get_supported_types()
        
        assert isinstance(types, list)
        assert len(types) > 0
        assert all("type" in t for t in types)


class TestDocumentProcessingError:
    """Tests para la excepción de procesamiento"""
    
    def test_error_creation(self):
        """Test creación de error de procesamiento"""
        error = DocumentProcessingError("Test error", "TEST_ERROR")
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
    
    def test_error_default_code(self):
        """Test código de error por defecto"""
        error = DocumentProcessingError("Test error")
        
        assert error.error_code == "PROCESSING_ERROR"


class TestAzureClient:
    """Tests para el cliente de Azure"""
    
    def test_azure_client_initialization(self):
        """Test inicialización del cliente Azure"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test-key",
            timeout_seconds=30,
            max_retries=2
        )
        
        client = AzureFormRecognizerClient(config)
        
        assert client.config.endpoint == "https://test.cognitiveservices.azure.com/"
        assert client.config.timeout_seconds == 30
        assert client.config.max_retries == 2
    
    def test_is_configured_true(self):
        """Test verificación de configuración exitosa"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(
            endpoint="https://test.cognitiveservices.azure.com/",
            api_key="test-key"
        )
        
        client = AzureFormRecognizerClient(config)
        client._client = Mock()  # Simular cliente inicializado
        
        assert client.is_configured is True
    
    def test_is_configured_false_no_endpoint(self):
        """Test configuración falsa sin endpoint"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(endpoint="", api_key="test-key")
        client = AzureFormRecognizerClient(config)
        
        assert client.is_configured is False
    
    def test_is_configured_false_no_key(self):
        """Test configuración falsa sin API key"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(endpoint="https://test.com", api_key="")
        client = AzureFormRecognizerClient(config)
        
        assert client.is_configured is False
    
    def test_get_model_id_prebuilt(self):
        """Test obtención de ID de modelo prebuilt"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(endpoint="https://test.com", api_key="key")
        client = AzureFormRecognizerClient(config)
        
        model_id = client._get_model_id(DocumentType.CURRICULUM_VITAE)
        
        assert model_id == "prebuilt-resume"
    
    def test_get_model_id_custom(self):
        """Test obtención de ID de modelo custom"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(endpoint="https://test.com", api_key="key")
        client = AzureFormRecognizerClient(config)
        
        model_id = client._get_model_id(DocumentType.TITULO_UNIVERSITARIO)
        
        assert model_id == "model-titulo-universitario"
    
    def test_list_available_models(self):
        """Test listado de modelos disponibles"""
        from app.azure_client import AzureFormRecognizerClient, AzureConfig
        
        config = AzureConfig(endpoint="https://test.com", api_key="key")
        client = AzureFormRecognizerClient(config)
        client._client = Mock()
        
        models = client.list_available_models()
        
        assert "prebuilt_models" in models
        assert "custom_models" in models
        assert "azure_configured" in models
        assert len(models["prebuilt_models"]) > 0


class TestModelMapper:
    """Tests para los mappers de modelos"""
    
    def test_cv_mapper(self, sample_cv_data):
        """Test mapper de CV"""
        from app.services.model_mapper import CurriculumVitaeMapper
        
        mapper = CurriculumVitaeMapper()
        
        # Simular datos de Azure
        azure_data = {
            "Name": Mock(value="Juan Pérez González"),
            "Email": Mock(value="juan.perez@email.com"),
            "Phone": Mock(value="+56912345678"),
            "WorkExperience": [],
            "Education": [],
            "Skills": [Mock(value="Python"), Mock(value="FastAPI")]
        }
        
        result = mapper.map(azure_data)
        
        assert "nombre" in result
        assert "email" in result
        assert "experiencia_laboral" in result
    
    def test_field_mapper_clean_text(self):
        """Test limpieza de texto"""
        from app.services.model_mapper import FieldMapper
        
        fm = FieldMapper()
        
        assert fm.clean_text("  Texto con espacios  ") == "Texto con espacios"
        assert fm.clean_text("Texto\tcon\ttabs") == "Texto con tabs"
        assert fm.clean_text("") is None
        assert fm.clean_text(None) is None
    
    def test_field_mapper_parse_phone(self):
        """Test parseo de teléfonos"""
        from app.services.model_mapper import FieldMapper
        
        fm = FieldMapper()
        
        assert fm.parse_phone("912345678") == "+56912345678"
        assert fm.parse_phone("56912345678") == "+56912345678"
        assert fm.parse_phone("+56912345678") == "+56912345678"
        assert fm.parse_phone("") is None
    
    def test_field_mapper_parse_email(self):
        """Test parseo de emails"""
        from app.services.model_mapper import FieldMapper
        
        fm = FieldMapper()
        
        assert fm.parse_email("Test@Email.COM") == "test@email.com"
        assert fm.parse_email("invalid-email") is None
        assert fm.parse_email("") is None
    
    def test_field_mapper_parse_rut(self):
        """Test parseo de RUT"""
        from app.services.model_mapper import FieldMapper
        
        fm = FieldMapper()
        
        assert fm.parse_rut("12.345.678-9") == "12345678-9"
        assert fm.parse_rut("12345678-9") == "12345678-9"
        assert fm.parse_rut("") is None
    
    def test_field_mapper_parse_number(self):
        """Test parseo de números"""
        from app.services.model_mapper import FieldMapper
        
        fm = FieldMapper()
        
        assert fm.parse_number("1.234,56") == 1234.56
        assert fm.parse_number("1,234.56") == 1234.56
        assert fm.parse_number("1234.56") == 1234.56
        assert fm.parse_number("$1,250.50") == 1250.50
        assert fm.parse_number("invalid") is None
    
    def test_model_mapper_factory(self):
        """Test factory de mappers"""
        from app.services.model_mapper import ModelMapperFactory, CurriculumVitaeMapper
        
        mapper = ModelMapperFactory.get_mapper(DocumentType.CURRICULUM_VITAE)
        
        assert isinstance(mapper, CurriculumVitaeMapper)
    
    def test_model_mapper_factory_invalid(self):
        """Test factory con tipo inválido"""
        from app.services.model_mapper import ModelMapperFactory
        
        with pytest.raises(ValueError):
            ModelMapperFactory.get_mapper(Mock(value="invalid"))
