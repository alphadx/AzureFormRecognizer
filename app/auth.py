"""
Sistema de autenticación JWT con validación de cliente y acción
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass
from functools import wraps

import jwt
from jwt.exceptions import PyJWTError, ExpiredSignatureError, InvalidTokenError

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.models.schemas import TokenPayload, ErrorCode
from app.utils.logger import LoggerMixin, log_auth_event, get_correlation_id


# Security scheme para FastAPI
security = HTTPBearer(auto_error=False)


class AuthError(Exception):
    """Excepción base para errores de autenticación"""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.AUTHENTICATION_ERROR):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AuthenticationError(AuthError):
    """Error de autenticación (credenciales inválidas)"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, ErrorCode.AUTHENTICATION_ERROR)


class AuthorizationError(AuthError):
    """Error de autorización (sin permisos)"""
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, ErrorCode.AUTHORIZATION_ERROR)


class TokenExpiredError(AuthError):
    """Error de token expirado"""
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, ErrorCode.AUTHENTICATION_ERROR)


@dataclass
class AuthContext:
    """Contexto de autenticación"""
    client_name: str
    action_name: str
    token: str
    exp: int


class JWTAuthProvider(LoggerMixin):
    """
    Proveedor de autenticación JWT
    
    Implementa:
    - Generación de tokens JWT
    - Validación de tokens
    - Validación de clientes contra ALLOWED_CLIENTS
    - Verificación de claims (client_name, action_name, exp)
    """
    
    def __init__(self):
        super().__init__()
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.expiration_minutes = settings.jwt_expiration_minutes
    
    def _is_configured(self) -> bool:
        """Verifica si la configuración JWT está completa"""
        return bool(self.secret_key)
    
    def authenticate_client(self, client_name: str, shared_key: str) -> bool:
        """
        Autentica un cliente verificando su shared_key
        
        Args:
            client_name: Nombre del cliente
            shared_key: Clave compartida proporcionada
            
        Returns:
            True si la autenticación es exitosa
        """
        allowed_clients = settings.clients_dict
        
        if not allowed_clients:
            self.log_warning("No clients configured in ALLOWED_CLIENTS")
            return False
        
        if client_name not in allowed_clients:
            self.log_warning(
                "Client not found",
                client_name=client_name,
                available_clients=list(allowed_clients.keys())
            )
            return False
        
        expected_key = allowed_clients[client_name]
        
        # Comparación segura contra timing attacks
        if not self._secure_compare(shared_key, expected_key):
            self.log_warning(
                "Invalid shared key",
                client_name=client_name
            )
            return False
        
        return True
    
    def _secure_compare(self, a: str, b: str) -> bool:
        """
        Comparación segura de strings contra timing attacks
        
        Args:
            a: Primer string
            b: Segundo string
            
        Returns:
            True si son iguales
        """
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        
        return result == 0
    
    def generate_token(self, client_name: str, action_name: str) -> str:
        """
        Genera un token JWT
        
        Args:
            client_name: Nombre del cliente
            action_name: Nombre de la acción permitida
            
        Returns:
            Token JWT firmado
            
        Raises:
            AuthenticationError: Si no está configurado JWT
        """
        if not self._is_configured():
            raise AuthenticationError("JWT not configured")
        
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(minutes=settings.jwt_expiration_minutes)
        
        payload = {
            "client_name": client_name,
            "action_name": action_name,
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp()),
            "jti": f"{client_name}:{int(now.timestamp())}"  # JWT ID único
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        self.log_info(
            "Token generated",
            client_name=client_name,
            action_name=action_name,
            expires_at=expiration.isoformat()
        )
        
        return token
    
    def decode_token(self, token: str) -> TokenPayload:
        """
        Decodifica y valida un token JWT
        
        Args:
            token: Token JWT
            
        Returns:
            TokenPayload con los claims
            
        Raises:
            TokenExpiredError: Si el token expiró
            AuthenticationError: Si el token es inválido
        """
        if not self._is_configured():
            raise AuthenticationError("JWT not configured")
        
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            return TokenPayload(
                client_name=payload.get("client_name", ""),
                action_name=payload.get("action_name", ""),
                exp=payload.get("exp", 0),
                iat=payload.get("iat")
            )
            
        except ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except PyJWTError as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")
    
    def validate_token_for_action(
        self,
        token: str,
        required_action: Optional[str] = None
    ) -> AuthContext:
        """
        Valida un token y opcionalmente verifica la acción
        
        Args:
            token: Token JWT
            required_action: Acción requerida (opcional)
            
        Returns:
            AuthContext con la información del token
            
        Raises:
            AuthenticationError: Si el token es inválido
            AuthorizationError: Si la acción no está permitida
        """
        # Decodificar token
        payload = self.decode_token(token)
        
        # Validar que el cliente exista
        if payload.client_name not in settings.clients_dict:
            log_auth_event(
                event_type="token_validation",
                client_name=payload.client_name,
                success=False,
                error="Client no longer valid"
            )
            raise AuthenticationError("Client is no longer valid")
        
        # Validar acción si se especificó
        if required_action and payload.action_name != required_action:
            log_auth_event(
                event_type="action_validation",
                client_name=payload.client_name,
                action_name=payload.action_name,
                success=False,
                error=f"Action '{payload.action_name}' not allowed for '{required_action}'"
            )
            raise AuthorizationError(
                f"Action '{payload.action_name}' is not authorized for this endpoint"
            )
        
        log_auth_event(
            event_type="token_validation",
            client_name=payload.client_name,
            action_name=payload.action_name,
            success=True
        )
        
        return AuthContext(
            client_name=payload.client_name,
            action_name=payload.action_name,
            token=token,
            exp=payload.exp
        )
    
    def get_token_expiration(self, token: str) -> datetime:
        """
        Obtiene la fecha de expiración de un token
        
        Args:
            token: Token JWT
            
        Returns:
            Fecha de expiración
        """
        payload = self.decode_token(token)
        return datetime.fromtimestamp(payload.exp, tz=timezone.utc)


# Instancia singleton del proveedor de auth
_auth_provider: Optional[JWTAuthProvider] = None


def get_auth_provider() -> JWTAuthProvider:
    """Obtiene la instancia singleton del proveedor de auth"""
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = JWTAuthProvider()
    return _auth_provider


def reset_auth_provider() -> None:
    """Resetea la instancia del proveedor (útil para testing)"""
    global _auth_provider
    _auth_provider = None


# ============================================
# DEPENDENCIAS DE FASTAPI
# ============================================

async def get_current_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthContext:
    """
    Dependencia de FastAPI para obtener el contexto de autenticación
    
    Args:
        credentials: Credenciales del header Authorization
        
    Returns:
        AuthContext del usuario autenticado
        
    Raises:
        HTTPException: 401 si no hay token o es inválido
    """
    if not credentials:
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error_code": ErrorCode.AUTHENTICATION_ERROR,
                "message": "Authorization header required",
                "correlation_id": get_correlation_id()
            }
        )
    
    token = credentials.credentials
    auth_provider = get_auth_provider()
    
    try:
        return auth_provider.validate_token_for_action(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error_code": ErrorCode.AUTHENTICATION_ERROR,
                "message": str(e),
                "correlation_id": get_correlation_id()
            }
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error_code": ErrorCode.AUTHENTICATION_ERROR,
                "message": str(e),
                "correlation_id": get_correlation_id()
            }
        )


async def require_action(action_name: str):
    """
    Dependencia factory para requerir una acción específica
    
    Args:
        action_name: Nombre de la acción requerida
        
    Returns:
        Dependencia que valida la acción
    """
    async def _check_action(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> AuthContext:
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail={
                    "success": False,
                    "error_code": ErrorCode.AUTHENTICATION_ERROR,
                    "message": "Authorization header required",
                    "correlation_id": get_correlation_id()
                }
            )
        
        token = credentials.credentials
        auth_provider = get_auth_provider()
        
        try:
            return auth_provider.validate_token_for_action(token, action_name)
        except TokenExpiredError as e:
            raise HTTPException(
                status_code=401,
                detail={
                    "success": False,
                    "error_code": ErrorCode.AUTHENTICATION_ERROR,
                    "message": str(e),
                    "correlation_id": get_correlation_id()
                }
            )
        except AuthenticationError as e:
            raise HTTPException(
                status_code=401,
                detail={
                    "success": False,
                    "error_code": ErrorCode.AUTHENTICATION_ERROR,
                    "message": str(e),
                    "correlation_id": get_correlation_id()
                }
            )
        except AuthorizationError as e:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error_code": ErrorCode.AUTHORIZATION_ERROR,
                    "message": str(e),
                    "correlation_id": get_correlation_id()
                }
            )
    
    return _check_action


# ============================================
# DECORADORES (para uso en funciones no-FastAPI)
# ============================================

def require_auth(action_name: Optional[str] = None):
    """
    Decorador para requerir autenticación en funciones
    
    Args:
        action_name: Nombre de la acción requerida (opcional)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener token del contexto o kwargs
            token = kwargs.get('token') or kwargs.get('auth_token')
            
            if not token:
                raise AuthenticationError("Token required")
            
            auth_provider = get_auth_provider()
            auth_context = auth_provider.validate_token_for_action(token, action_name)
            
            # Agregar contexto a los kwargs
            kwargs['auth_context'] = auth_context
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
