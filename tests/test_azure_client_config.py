from pathlib import Path
from unittest.mock import Mock

from app.azure_client import AzureConfig, AzureFormRecognizerClient
from app.config import Settings
from app.models.document_types import DocumentType


def _parse_env_value(env_path: Path, key: str) -> str:
    for line in env_path.read_text().splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def test_azure_credentials_load_from_dotenv(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"

    assert env_path.exists(), ".env file must exist in the repository root"

    expected_endpoint = _parse_env_value(env_path, "AZURE_FORM_RECOGNIZER_ENDPOINT")
    expected_api_key = _parse_env_value(env_path, "AZURE_FORM_RECOGNIZER_API_KEY")

    assert expected_endpoint, "AZURE_FORM_RECOGNIZER_ENDPOINT must be set in .env"
    assert expected_api_key, "AZURE_FORM_RECOGNIZER_API_KEY must be set in .env"

    monkeypatch.delenv("AZURE_FORM_RECOGNIZER_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FORM_RECOGNIZER_API_KEY", raising=False)

    settings = Settings()
    assert settings.azure_form_recognizer_endpoint == expected_endpoint
    assert settings.azure_form_recognizer_api_key == expected_api_key

    azure_config = AzureConfig(
        endpoint=settings.azure_form_recognizer_endpoint,
        api_key=settings.azure_form_recognizer_api_key,
        api_version=settings.azure_form_recognizer_api_version
    )
    azure_client = AzureFormRecognizerClient(config=azure_config)

    assert azure_client.config.endpoint == expected_endpoint
    assert azure_client.config.api_key == expected_api_key
    assert azure_client.config.api_version == settings.azure_form_recognizer_api_version


def test_cedula_identidad_uses_prebuilt_identity_document():
    assert AzureFormRecognizerClient.PREBUILT_MODELS[DocumentType.CEDULA_IDENTIDAD] == "prebuilt-idDocument"


def test_analyze_document_logs_actual_model_used_after_fallback(monkeypatch):
    azure_config = AzureConfig(
        endpoint="https://test.cognitiveservices.azure.com/",
        api_key="test-azure-key",
        api_version="2023-07-31"
    )
    client = AzureFormRecognizerClient(config=azure_config)

    mock_result = Mock()
    mock_result.success = True
    mock_result.model_used = "prebuilt-document"
    mock_result.processing_time_ms = 0
    mock_result.error_message = None

    monkeypatch.setattr(client, "_process_with_retry", lambda document_type, file_content, model_id: mock_result)
    mock_log_azure_request = Mock()
    monkeypatch.setattr("app.azure_client.log_azure_request", mock_log_azure_request)

    client.analyze_document(DocumentType.CEDULA_IDENTIDAD, b"test")

    assert mock_log_azure_request.call_count == 1
    _, kwargs = mock_log_azure_request.call_args
    assert kwargs["model_used"] == "prebuilt-document"
