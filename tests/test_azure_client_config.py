from pathlib import Path

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
        api_key=settings.azure_form_recognizer_api_key
    )
    azure_client = AzureFormRecognizerClient(config=azure_config)

    assert azure_client.config.endpoint == expected_endpoint
    assert azure_client.config.api_key == expected_api_key


def test_cedula_identidad_uses_prebuilt_identity_document():
    assert AzureFormRecognizerClient.PREBUILT_MODELS[DocumentType.CEDULA_IDENTIDAD] == "prebuilt-identityDocument"
