"""
Tests para los validadores
"""

import pytest
from unittest.mock import Mock

from app.utils.validators import (
    FileValidator,
    DocumentTypeValidator,
    validate_token_request,
    ValidationResult
)
from app.config import settings


class TestFileValidator:
    """Tests para FileValidator"""
    
    def test_validate_file_size_under_limit(self):
        """Test validación de archivo bajo el límite"""
        small_content = b"x" * 1024  # 1 KB
        
        result = FileValidator.validate_file_size(len(small_content))
        
        assert result.is_valid is True
        assert result.file_size == 1024
    
    def test_validate_file_size_over_limit(self, monkeypatch):
        """Test validación de archivo sobre el límite"""
        monkeypatch.setattr(settings, "max_file_size_mb", 1)
        
        large_content = b"x" * (2 * 1024 * 1024)  # 2 MB
        
        result = FileValidator.validate_file_size(len(large_content))
        
        assert result.is_valid is False
        assert "tamaño máximo" in result.error_message.lower() or "maximum" in result.error_message.lower()
    
    def test_validate_extension_valid(self):
        """Test validación de extensión válida"""
        result = FileValidator.validate_extension("document.pdf")
        
        assert result.is_valid is True
    
    def test_validate_extension_invalid(self):
        """Test validación de extensión inválida"""
        result = FileValidator.validate_extension("document.exe")
        
        assert result.is_valid is False
        assert ".exe" in result.error_message
    
    def test_validate_extension_case_insensitive(self):
        """Test validación de extensión case-insensitive"""
        result = FileValidator.validate_extension("document.PDF")
        
        assert result.is_valid is True
    
    def test_get_extension_from_mime(self):
        """Test obtención de extensión desde MIME type"""
        assert FileValidator.get_extension_from_mime("application/pdf") == ".pdf"
        assert FileValidator.get_extension_from_mime("image/png") == ".png"
        assert FileValidator.get_extension_from_mime("image/jpeg") == ".jpg"
    
    def test_get_mime_from_extension(self):
        """Test obtención de MIME type desde extensión"""
        assert FileValidator.get_mime_from_extension(".pdf") == "application/pdf"
        assert FileValidator.get_mime_from_extension("pdf") == "application/pdf"
        assert FileValidator.get_mime_from_extension(".png") == "image/png"


class TestDocumentTypeValidator:
    """Tests para DocumentTypeValidator"""
    
    def test_is_valid_type_true(self):
        """Test tipo de documento válido"""
        assert DocumentTypeValidator.is_valid_type("curriculum_vitae") is True
        assert DocumentTypeValidator.is_valid_type("titulo_universitario") is True
        assert DocumentTypeValidator.is_valid_type("cedula_identidad") is True
    
    def test_is_valid_type_false(self):
        """Test tipo de documento inválido"""
        assert DocumentTypeValidator.is_valid_type("invalid_type") is False
        assert DocumentTypeValidator.is_valid_type("") is False
    
    def test_get_supported_types(self):
        """Test obtención de tipos soportados"""
        types = DocumentTypeValidator.get_supported_types()
        
        assert isinstance(types, list)
        assert len(types) == 5
        assert "curriculum_vitae" in types
        assert "titulo_universitario" in types
    
    def test_get_azure_model_prebuilt(self):
        """Test obtención de modelo prebuilt"""
        model = DocumentTypeValidator.get_azure_model("curriculum_vitae")
        
        assert model == "prebuilt-resume"
    
    def test_get_azure_model_custom(self):
        """Test obtención de modelo custom"""
        model = DocumentTypeValidator.get_azure_model("titulo_universitario")
        
        assert model == "custom"
    
    def test_is_prebuilt_model_true(self):
        """Test verificación de modelo prebuilt"""
        assert DocumentTypeValidator.is_prebuilt_model("curriculum_vitae") is True
        assert DocumentTypeValidator.is_prebuilt_model("cedula_identidad") is True
    
    def test_is_prebuilt_model_false(self):
        """Test verificación de modelo no prebuilt"""
        assert DocumentTypeValidator.is_prebuilt_model("titulo_universitario") is False
    
    def test_is_custom_model_true(self):
        """Test verificación de modelo custom"""
        assert DocumentTypeValidator.is_custom_model("titulo_universitario") is True
        assert DocumentTypeValidator.is_custom_model("concentracion_notas") is True
    
    def test_is_custom_model_false(self):
        """Test verificación de modelo no custom"""
        assert DocumentTypeValidator.is_custom_model("curriculum_vitae") is False
    
    def test_validate_valid_type(self):
        """Test validación de tipo válido"""
        result = DocumentTypeValidator.validate("curriculum_vitae")
        
        assert result.is_valid is True
        assert result.error_message == ""
    
    def test_validate_invalid_type(self):
        """Test validación de tipo inválido"""
        result = DocumentTypeValidator.validate("invalid_type")
        
        assert result.is_valid is False
        assert "no soportado" in result.error_message.lower() or "not supported" in result.error_message.lower()
    
    def test_validate_empty_type(self):
        """Test validación de tipo vacío"""
        result = DocumentTypeValidator.validate("")
        
        assert result.is_valid is False


class TestValidateTokenRequest:
    """Tests para validate_token_request"""
    
    def test_valid_request(self):
        """Test request válido"""
        is_valid, error = validate_token_request("client1", "action1", "key123")
        
        assert is_valid is True
        assert error == ""
    
    def test_empty_client_name(self):
        """Test client_name vacío"""
        is_valid, error = validate_token_request("", "action1", "key123")
        
        assert is_valid is False
        assert "client_name" in error.lower()
    
    def test_empty_action_name(self):
        """Test action_name vacío"""
        is_valid, error = validate_token_request("client1", "", "key123")
        
        assert is_valid is False
        assert "action_name" in error.lower()
    
    def test_empty_shared_key(self):
        """Test shared_key vacío"""
        is_valid, error = validate_token_request("client1", "action1", "")
        
        assert is_valid is False
        assert "shared_key" in error.lower()
    
    def test_whitespace_only_values(self):
        """Test valores con solo espacios"""
        is_valid, error = validate_token_request("   ", "action1", "key123")
        
        assert is_valid is False


class TestValidationResult:
    """Tests para ValidationResult"""
    
    def test_creation(self):
        """Test creación de ValidationResult"""
        result = ValidationResult(is_valid=True, mime_type="application/pdf", file_size=1024)
        
        assert result.is_valid is True
        assert result.mime_type == "application/pdf"
        assert result.file_size == 1024
        assert result.error_message == ""
    
    def test_creation_with_error(self):
        """Test creación con error"""
        result = ValidationResult(
            is_valid=False,
            error_message="Error de prueba",
            mime_type="",
            file_size=0
        )
        
        assert result.is_valid is False
        assert result.error_message == "Error de prueba"
