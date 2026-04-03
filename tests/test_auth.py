"""
Tests para el módulo de autenticación
"""

import pytest
import jwt
from datetime import datetime, timezone, timedelta

from app.auth import (
    JWTAuthProvider,
    get_auth_provider,
    AuthContext,
    AuthenticationError,
    AuthorizationError,
    TokenExpiredError
)
from app.config import settings


class TestJWTAuthProvider:
    """Tests para JWTAuthProvider"""
    
    def test_singleton_pattern(self):
        """Test que el provider es singleton"""
        provider1 = get_auth_provider()
        provider2 = get_auth_provider()
        assert provider1 is provider2
    
    def test_is_configured(self):
        """Test de verificación de configuración"""
        provider = JWTAuthProvider()
        assert provider._is_configured() is True
    
    def test_authenticate_client_valid(self, valid_client_credentials):
        """Test autenticación con credenciales válidas"""
        provider = JWTAuthProvider()
        
        result = provider.authenticate_client(
            valid_client_credentials["client_name"],
            valid_client_credentials["shared_key"]
        )
        
        assert result is True
    
    def test_authenticate_client_invalid_name(self, invalid_client_credentials):
        """Test autenticación con nombre de cliente inválido"""
        provider = JWTAuthProvider()
        
        result = provider.authenticate_client(
            invalid_client_credentials["client_name"],
            "any_key"
        )
        
        assert result is False
    
    def test_authenticate_client_invalid_key(self, valid_client_credentials):
        """Test autenticación con clave inválida"""
        provider = JWTAuthProvider()
        
        result = provider.authenticate_client(
            valid_client_credentials["client_name"],
            "wrong_key"
        )
        
        assert result is False
    
    def test_authenticate_client_empty_clients(self, monkeypatch):
        """Test autenticación cuando no hay clientes configurados"""
        monkeypatch.setattr(settings, "allowed_clients", "")
        
        provider = JWTAuthProvider()
        
        result = provider.authenticate_client("any", "any")
        
        assert result is False
    
    def test_generate_token_success(self, valid_client_credentials):
        """Test generación exitosa de token"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_generate_token_contains_correct_claims(self, valid_client_credentials):
        """Test que el token contiene los claims correctos"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        # Decodificar sin verificar expiración
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        
        assert payload["client_name"] == valid_client_credentials["client_name"]
        assert payload["action_name"] == valid_client_credentials["action_name"]
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload
    
    def test_generate_token_expiration(self, valid_client_credentials):
        """Test que el token tiene fecha de expiración correcta"""
        provider = JWTAuthProvider()
        
        before = datetime.now(timezone.utc)
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        after = datetime.now(timezone.utc)
        
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = before + timedelta(minutes=settings.jwt_expiration_minutes)
        
        # Permitir margen de 5 segundos
        assert abs((exp - expected_exp).total_seconds()) < 5
    
    def test_decode_token_success(self, valid_client_credentials):
        """Test decodificación exitosa de token"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        payload = provider.decode_token(token)
        
        assert payload.client_name == valid_client_credentials["client_name"]
        assert payload.action_name == valid_client_credentials["action_name"]
        assert payload.exp > 0
    
    def test_decode_token_invalid(self):
        """Test decodificación de token inválido"""
        provider = JWTAuthProvider()
        
        with pytest.raises(AuthenticationError):
            provider.decode_token("invalid.token.here")
    
    def test_decode_token_expired(self, valid_client_credentials, monkeypatch):
        """Test decodificación de token expirado"""
        provider = JWTAuthProvider()
        
        # Generar token con expiración inmediata
        monkeypatch.setattr(settings, "jwt_expiration_minutes", -1)
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        with pytest.raises(TokenExpiredError):
            provider.decode_token(token)
    
    def test_validate_token_for_action_success(self, valid_client_credentials):
        """Test validación exitosa de token para acción"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        auth_context = provider.validate_token_for_action(token)
        
        assert isinstance(auth_context, AuthContext)
        assert auth_context.client_name == valid_client_credentials["client_name"]
        assert auth_context.action_name == valid_client_credentials["action_name"]
    
    def test_validate_token_for_action_with_required_action(self, valid_client_credentials):
        """Test validación de token con acción requerida específica"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        auth_context = provider.validate_token_for_action(
            token,
            required_action=valid_client_credentials["action_name"]
        )
        
        assert auth_context.action_name == valid_client_credentials["action_name"]
    
    def test_validate_token_for_action_wrong_action(self, valid_client_credentials):
        """Test validación con acción incorrecta"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        with pytest.raises(AuthorizationError):
            provider.validate_token_for_action(token, required_action="wrong_action")
    
    def test_validate_token_client_no_longer_valid(self, valid_client_credentials, monkeypatch):
        """Test validación cuando el cliente ya no es válido"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        # Remover cliente de la configuración
        monkeypatch.setattr(settings, "allowed_clients", "other_client:other_key")
        
        with pytest.raises(AuthenticationError) as exc_info:
            provider.validate_token_for_action(token)
        
        assert "Client is no longer valid" in str(exc_info.value)
    
    def test_get_token_expiration(self, valid_client_credentials):
        """Test obtención de fecha de expiración"""
        provider = JWTAuthProvider()
        
        token = provider.generate_token(
            valid_client_credentials["client_name"],
            valid_client_credentials["action_name"]
        )
        
        exp = provider.get_token_expiration(token)
        
        assert isinstance(exp, datetime)
        assert exp > datetime.now(timezone.utc)
    
    def test_secure_compare_equal(self):
        """Test comparación segura de strings iguales"""
        provider = JWTAuthProvider()
        
        result = provider._secure_compare("test_string", "test_string")
        
        assert result is True
    
    def test_secure_compare_different(self):
        """Test comparación segura de strings diferentes"""
        provider = JWTAuthProvider()
        
        result = provider._secure_compare("test_string", "different_string")
        
        assert result is False
    
    def test_secure_compare_different_length(self):
        """Test comparación segura de strings con diferente longitud"""
        provider = JWTAuthProvider()
        
        result = provider._secure_compare("short", "much_longer_string")
        
        assert result is False


class TestAuthErrors:
    """Tests para excepciones de autenticación"""
    
    def test_authentication_error(self):
        """Test excepción de autenticación"""
        error = AuthenticationError("Custom auth error")
        
        assert str(error) == "Custom auth error"
        assert error.error_code.value == "AUTHENTICATION_ERROR"
    
    def test_authorization_error(self):
        """Test excepción de autorización"""
        error = AuthorizationError("Custom authz error")
        
        assert str(error) == "Custom authz error"
        assert error.error_code.value == "AUTHORIZATION_ERROR"
    
    def test_token_expired_error(self):
        """Test excepción de token expirado"""
        error = TokenExpiredError("Token expired")
        
        assert str(error) == "Token expired"
        assert error.error_code.value == "AUTHENTICATION_ERROR"
