#!/usr/bin/env python3
"""
Script de ejemplo en Python para probar la Document Processor API

Uso:
    python scripts/test_api.py

Variables de entorno:
    API_URL: URL de la API (default: http://localhost:8000)
    CLIENT_NAME: Nombre del cliente (default: test_client)
    SHARED_KEY: Clave compartida (default: test_key_123)
"""

import os
import sys
import json
import argparse
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("Error: requests no está instalado")
    print("Instalar: pip install requests")
    sys.exit(1)


class DocumentProcessorAPI:
    """Cliente para la Document Processor API"""
    
    def __init__(self, base_url: str, client_name: str, shared_key: str, action_name: str = "process_documents"):
        self.base_url = base_url.rstrip('/')
        self.client_name = client_name
        self.shared_key = shared_key
        self.action_name = action_name
        self.token: Optional[str] = None
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Realiza una request a la API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Imprimir headers de rate limit
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Remaining']
                limit = response.headers.get('X-RateLimit-Limit', '?')
                print(f"  Rate Limit: {remaining}/{limit} remaining")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            print(f"  Error HTTP {e.response.status_code}: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"  Error de conexión: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de la API"""
        print("\n1. Health Check")
        print("-" * 40)
        return self._make_request('GET', '/health')
    
    def authenticate(self) -> str:
        """Obtiene un token JWT"""
        print("\n2. Autenticación")
        print("-" * 40)
        
        response = self._make_request(
            'POST',
            '/api/v1/auth/token',
            json={
                "client_name": self.client_name,
                "action_name": self.action_name,
                "shared_key": self.shared_key
            }
        )
        
        self.token = response['access_token']
        print(f"  Token obtenido (expira en {response['expires_in']}s)")
        return self.token
    
    def verify_token(self) -> Dict[str, Any]:
        """Verifica el token actual"""
        print("\n3. Verificar Token")
        print("-" * 40)
        return self._make_request(
            'GET',
            '/api/v1/auth/verify',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def get_document_types(self) -> Dict[str, Any]:
        """Obtiene los tipos de documento soportados"""
        print("\n4. Tipos de Documento")
        print("-" * 40)
        return self._make_request(
            'GET',
            '/api/v1/document-types',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def get_document_type_detail(self, doc_type: str) -> Dict[str, Any]:
        """Obtiene el detalle de un tipo de documento"""
        print(f"\n5. Detalle de {doc_type}")
        print("-" * 40)
        return self._make_request(
            'GET',
            f'/api/v1/document-types/{doc_type}',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def get_azure_models(self) -> Dict[str, Any]:
        """Obtiene los modelos Azure configurados"""
        print("\n6. Modelos Azure")
        print("-" * 40)
        return self._make_request(
            'GET',
            '/api/v1/azure/models',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de la API"""
        print("\n7. Configuración")
        print("-" * 40)
        return self._make_request(
            'GET',
            '/api/v1/config',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def process_document(self, file_path: str, doc_type: str, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Procesa un documento"""
        print(f"\n8. Procesar Documento: {doc_type}")
        print("-" * 40)
        
        if not os.path.exists(file_path):
            print(f"  Archivo no encontrado: {file_path}")
            print("  Creando PDF de prueba...")
            file_path = self._create_test_pdf()
        
        with open(file_path, 'rb') as f:
            files = {'archivo': (os.path.basename(file_path), f, 'application/pdf')}
            data = {'tipo_documento': doc_type}
            if client_id:
                data['cliente_id'] = client_id
            
            return self._make_request(
                'POST',
                '/api/v1/documents/process',
                headers={"Authorization": f"Bearer {self.token}"},
                files=files,
                data=data
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        print("\n9. Estadísticas")
        print("-" * 40)
        return self._make_request(
            'GET',
            '/api/v1/stats',
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    def _create_test_pdf(self) -> str:
        """Crea un PDF de prueba mínimo"""
        pdf_path = '/tmp/test_document_api.pdf'
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
196
%%EOF"""
        
        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)
        
        return pdf_path


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Test Document Processor API')
    parser.add_argument('--url', default=os.getenv('API_URL', 'http://localhost:8000'),
                        help='URL de la API')
    parser.add_argument('--client', default=os.getenv('CLIENT_NAME', 'test_client'),
                        help='Nombre del cliente')
    parser.add_argument('--key', default=os.getenv('SHARED_KEY', 'test_key_123'),
                        help='Clave compartida')
    parser.add_argument('--file', default=None,
                        help='Archivo a procesar (opcional)')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("  Document Processor API - Test Client")
    print("=" * 50)
    print(f"\nAPI URL: {args.url}")
    print(f"Client: {args.client}")
    
    # Crear cliente API
    api = DocumentProcessorAPI(args.url, args.client, args.key)
    
    try:
        # 1. Health check
        health = api.health_check()
        print(f"  Status: {health.get('status', 'unknown')}")
        
        # 2. Autenticar
        api.authenticate()
        
        # 3. Verificar token
        verify = api.verify_token()
        print(f"  Client: {verify.get('client_name')}")
        print(f"  Expires: {verify.get('expires_at_iso')}")
        
        # 4. Tipos de documento
        doc_types = api.get_document_types()
        print(f"  Total: {doc_types.get('total', 0)} types")
        for dt in doc_types.get('document_types', [])[:3]:
            print(f"    - {dt['type']}: {dt['name']}")
        
        # 5. Detalle de CV
        cv_detail = api.get_document_type_detail('curriculum_vitae')
        print(f"  Model: {cv_detail.get('azure_model')}")
        print(f"  Fields: {len(cv_detail.get('fields', []))}")
        
        # 6. Modelos Azure
        azure = api.get_azure_models()
        print(f"  Configured: {azure.get('azure_configured')}")
        
        # 7. Configuración
        config = api.get_config()
        print(f"  Max file size: {config.get('max_file_size_mb')} MB")
        print(f"  Rate limit: {config.get('rate_limit_requests')}/hour")
        
        # 8. Procesar documento
        file_to_process = args.file or '/tmp/test_document_api.pdf'
        process_result = api.process_document(file_to_process, 'curriculum_vitae', 'test_001')
        print(f"  Success: {process_result.get('success')}")
        print(f"  Status: {process_result.get('status')}")
        print(f"  Confidence: {process_result.get('confidence_score')}")
        print(f"  Processing time: {process_result.get('processing_time_ms')}ms")
        
        # 9. Estadísticas
        stats = api.get_stats()
        print(f"  Document types: {stats.get('document_types', {}).get('total')}")
        
        print("\n" + "=" * 50)
        print("  All tests passed successfully!")
        print("=" * 50)
        
        # Guardar token para uso manual
        print(f"\nToken JWT (para uso manual):")
        print(f"  export TOKEN={api.token}")
        print(f"\nEjemplo:")
        print(f"  curl -H \"Authorization: Bearer {api.token}\" {args.url}/api/v1/document-types")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
