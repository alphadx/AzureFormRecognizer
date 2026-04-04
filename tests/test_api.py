"""
Tests de integración para los endpoints de la API
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.main import app
from app.auth import get_auth_provider
from app.models.schemas import DocumentProcessResponse


# Crear cliente de test
client = TestClient(app)


class TestPublicEndpoints:
    """Tests para endpoints públicos"""
    
    def test_root_endpoint(self):
        """Test endpoint raíz"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Document Processor API"
        assert "version" in data
        assert "correlation_id" in data
    
    def test_health_endpoint(self):
        """Test endpoint de health check"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["service"] == "document-processor-api"
    
    def test_health_detailed_endpoint(self):
        """Test endpoint de health check detallado"""
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "dependencies" in data
        assert "configuration" in data
    
    def test_ping_endpoint(self):
        """Test endpoint ping"""
        response = client.get("/api/v1/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pong"
    
    def test_robots_txt_endpoint(self):
        """Test endpoint robots.txt"""
        response = client.get("/robots.txt")
        
        assert response.status_code == 200
        assert "Disallow" in response.text


class TestAuthEndpoints:
    """Tests para endpoints de autenticación"""
    
    def test_create_token_success(self):
        """Test creación exitosa de token"""
        response = client.post(
            "/api/v1/auth/token",
            json={
                "client_name": "test_client",
                "action_name": "process_documents",
                "shared_key": "test_key_123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["client_name"] == "test_client"
        assert "expires_in" in data
    
    def test_create_token_invalid_credentials(self):
        """Test creación de token con credenciales inválidas"""
        response = client.post(
            "/api/v1/auth/token",
            json={
                "client_name": "invalid_client",
                "action_name": "process_documents",
                "shared_key": "wrong_key"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "AUTHENTICATION_ERROR"
    
    def test_create_token_missing_fields(self):
        """Test creación de token con campos faltantes"""
        response = client.post(
            "/api/v1/auth/token",
            json={
                "client_name": "test_client"
                # Falta action_name y shared_key
            }
        )
        
        assert response.status_code == 422  # Validation error de Pydantic
    
    def test_verify_token_success(self):
        """Test verificación exitosa de token"""
        # Primero obtener un token
        token_response = client.post(
            "/api/v1/auth/token",
            json={
                "client_name": "test_client",
                "action_name": "process_documents",
                "shared_key": "test_key_123"
            }
        )
        token = token_response.json()["access_token"]
        
        # Verificar token
        response = client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["client_name"] == "test_client"
    
    def test_verify_token_missing(self):
        """Test verificación sin token"""
        response = client.get("/api/v1/auth/verify")
        
        assert response.status_code == 403  # FastAPI HTTPBearer auto_error=False
    
    def test_verify_token_invalid(self):
        """Test verificación con token inválido"""
        response = client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Tests para endpoints protegidos"""
    
    @pytest.fixture
    def auth_token(self):
        """Fixture para obtener token de autenticación"""
        response = client.post(
            "/api/v1/auth/token",
            json={
                "client_name": "test_client",
                "action_name": "process_documents",
                "shared_key": "test_key_123"
            }
        )
        return response.json()["access_token"]
    
    def test_get_config_protected(self, auth_token):
        """Test obtención de configuración con auth"""
        response = client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "azure_configured" in data
        assert "jwt_configured" in data
    
    def test_get_config_without_auth(self):
        """Test obtención de configuración sin auth"""
        response = client.get("/api/v1/config")
        
        assert response.status_code == 403
    
    def test_get_document_types(self, auth_token):
        """Test obtención de tipos de documento"""
        response = client.get(
            "/api/v1/document-types",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "document_types" in data
        assert data["total"] == 5
    
    def test_get_document_type_detail(self, auth_token):
        """Test obtención de detalle de tipo de documento"""
        response = client.get(
            "/api/v1/document-types/curriculum_vitae",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "curriculum_vitae"
        assert "fields" in data
        assert len(data["fields"]) > 0
    
    def test_get_document_type_detail_invalid(self, auth_token):
        """Test obtención de detalle con tipo inválido"""
        response = client.get(
            "/api/v1/document-types/invalid_type",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 400
    
    def test_get_azure_models(self, auth_token):
        """Test obtención de modelos Azure"""
        response = client.get(
            "/api/v1/azure/models",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "prebuilt_models" in data["models"]
        assert "custom_models" in data["models"]

    def test_process_azure_model_invalid_model(self, auth_token, sample_pdf_bytes):
        """Test procesar modelo Azure inválido"""
        response = client.post(
            "/api/v1/documents/process/azure-model",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"archivo": ("test.pdf", sample_pdf_bytes, "application/pdf")},
            data={"azure_model_id": "prebuilt-invalid"}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INVALID_DOCUMENT_TYPE"

    def test_process_azure_model_success(self, auth_token, sample_pdf_bytes, monkeypatch):
        """Test procesar modelo Azure directo exitosamente"""
        response_payload = DocumentProcessResponse(
            success=True,
            status="success",
            document_type="prebuilt-document",
            processed_at="2025-01-01T00:00:00Z",
            data={"text": "ejemplo"},
            confidence_score=0.98,
            processing_time_ms=300,
            correlation_id="test-correlation-id"
        )

        async def fake_process_azure_model(*args, **kwargs):
            return response_payload

        monkeypatch.setattr("app.main.get_document_processor", lambda: Mock(process_azure_model=fake_process_azure_model))

        response = client.post(
            "/api/v1/documents/process/azure-model",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"archivo": ("test.pdf", sample_pdf_bytes, "application/pdf")},
            data={"azure_model_id": "prebuilt-document"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_type"] == "prebuilt-document"
        assert data["data"]["text"] == "ejemplo"
    
    def test_get_azure_status(self, auth_token):
        """Test obtención de estado de Azure"""
        response = client.get(
            "/api/v1/azure/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
    
    def test_get_stats(self, auth_token):
        """Test obtención de estadísticas"""
        response = client.get(
            "/api/v1/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "configuration" in data
        assert "document_types" in data
    
    def test_test_validation(self, auth_token):
        """Test endpoint de validación"""
        response = client.get(
            "/api/v1/test-validation",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "authenticated_client" in data
        assert "document_type_tests" in data


class TestRateLimiting:
    """Tests para rate limiting"""
    
    def test_rate_limit_headers_present(self):
        """Test que los headers de rate limit están presentes"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
    
    def test_correlation_id_header(self):
        """Test que el header de correlation_id está presente"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
    
    def test_custom_correlation_id(self):
        """Test correlation_id personalizado"""
        custom_id = "my-custom-id-123"
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": custom_id}
        )
        
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_id


class TestSecurityHeaders:
    """Tests para headers de seguridad"""
    
    def test_security_headers_present(self):
        """Test que los headers de seguridad están presentes"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
