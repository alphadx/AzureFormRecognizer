"""
Fixtures y configuración para tests
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock

# Configurar variables de entorno para tests
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-jwt-2024"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRATION_MINUTES"] = "30"
os.environ["ALLOWED_CLIENTS"] = "test_client:test_key_123,client2:key2_456"
os.environ["AZURE_FORM_RECOGNIZER_ENDPOINT"] = "https://test.cognitiveservices.azure.com/"
os.environ["AZURE_FORM_RECOGNIZER_API_KEY"] = "test-azure-key"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["MAX_FILE_SIZE_MB"] = "10"
os.environ["ALLOWED_FILE_TYPES"] = "application/pdf,image/png,image/jpeg"


@pytest.fixture
def sample_pdf_bytes():
    """Retorna bytes de un PDF de prueba mínimo"""
    # PDF mínimo válido (header PDF)
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF"


@pytest.fixture
def sample_png_bytes():
    """Retorna bytes de una imagen PNG de prueba mínima"""
    # PNG mínimo válido (header PNG)
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture
def sample_jpg_bytes():
    """Retorna bytes de una imagen JPG de prueba mínima"""
    # JPEG mínimo válido (header JPEG)
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


@pytest.fixture
def valid_client_credentials():
    """Credenciales de cliente válidas para tests"""
    return {
        "client_name": "test_client",
        "action_name": "process_documents",
        "shared_key": "test_key_123"
    }


@pytest.fixture
def invalid_client_credentials():
    """Credenciales de cliente inválidas para tests"""
    return {
        "client_name": "invalid_client",
        "action_name": "process_documents",
        "shared_key": "wrong_key"
    }


@pytest.fixture
def mock_azure_response():
    """Mock de respuesta de Azure Form Recognizer"""
    mock_result = Mock()
    mock_result.model_id = "prebuilt-resume"
    mock_result.pages = [Mock()]
    
    # Mock de documentos
    mock_doc = Mock()
    mock_doc.confidence = 0.95
    
    # Mock de campos
    mock_name_field = Mock()
    mock_name_field.value = "Juan Pérez"
    mock_name_field.confidence = 0.98
    
    mock_email_field = Mock()
    mock_email_field.value = "juan.perez@email.com"
    mock_email_field.confidence = 0.97
    
    mock_doc.fields = {
        "Name": mock_name_field,
        "Email": mock_email_field
    }
    
    mock_result.documents = [mock_doc]
    
    return mock_result


@pytest.fixture
def mock_azure_client(mock_azure_response):
    """Mock del cliente de Azure"""
    mock_client = Mock()
    
    # Mock del poller
    mock_poller = Mock()
    mock_poller.result.return_value = mock_azure_response
    
    mock_client.begin_analyze_document.return_value = mock_poller
    
    return mock_client


@pytest.fixture
def sample_cv_data():
    """Datos de CV de ejemplo"""
    return {
        "nombre": "Juan Pérez González",
        "email": "juan.perez@email.com",
        "telefono": "+56912345678",
        "experiencia_laboral": [
            {
                "empresa": "Empresa XYZ",
                "cargo": "Desarrollador Senior",
                "fecha_inicio": "2020-01",
                "fecha_fin": "2023-12"
            }
        ],
        "educacion": [
            {
                "institucion": "Universidad de Chile",
                "carrera": "Ingeniería Civil Informática",
                "fecha_fin": "2019"
            }
        ],
        "habilidades": ["Python", "FastAPI", "Docker"]
    }


@pytest.fixture
def sample_titulo_data():
    """Datos de título universitario de ejemplo"""
    return {
        "institucion": "Universidad de Chile",
        "carrera": "Ingeniería Civil Informática",
        "nombre_titular": "Juan Pérez González",
        "rut_titular": "12.345.678-9",
        "fecha_emision": "2019-12-15",
        "numero_titulo": "T-12345-2019",
        "grado_academico": "Licenciado"
    }


@pytest.fixture
def sample_cedula_data():
    """Datos de cédula de ejemplo"""
    return {
        "nombre": "Juan Pérez González",
        "rut": "12.345.678-9",
        "fecha_nacimiento": "1990-05-15",
        "nacionalidad": "Chilena",
        "fecha_emision": "2020-01-10",
        "fecha_vencimiento": "2030-01-10"
    }


@pytest.fixture
def sample_notas_data():
    """Datos de concentración de notas de ejemplo"""
    return {
        "institucion": "Universidad de Chile",
        "carrera": "Ingeniería Civil Informática",
        "nombre_estudiante": "Juan Pérez González",
        "periodo_academico": "2023-1",
        "asignaturas": [
            {"nombre": "Programación I", "nota": 6.5, "creditos": 6, "estado": "Aprobado"},
            {"nombre": "Bases de Datos", "nota": 5.8, "creditos": 6, "estado": "Aprobado"},
            {"nombre": "Algoritmos", "nota": 4.2, "creditos": 6, "estado": "Aprobado"}
        ],
        "promedio_ponderado": 5.5,
        "total_creditos": 18,
        "total_asignaturas": 3
    }


@pytest.fixture
def sample_afp_data():
    """Datos de cotización AFP de ejemplo"""
    return {
        "institucion": "AFP Habitat",
        "rut_afiliado": "12.345.678-9",
        "nombre_afiliado": "Juan Pérez González",
        "fecha_cotizacion": "2024-01-15",
        "periodo": "01/2024",
        "tipo_cotizacion": "Dependiente",
        "monto_cotizacion_obligatoria": 125000.50,
        "monto_cotizacion_voluntaria": 50000.00,
        "monto_total": 175000.50,
        "saldo_total": 15000000.00
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Resetea singletons antes de cada test"""
    from app.auth import reset_auth_provider
    from app.azure_client import reset_azure_client
    from app.services.document_processor import reset_document_processor
    
    reset_auth_provider()
    reset_azure_client()
    reset_document_processor()
    
    yield
    
    # Limpiar después del test
    reset_auth_provider()
    reset_azure_client()
    reset_document_processor()
