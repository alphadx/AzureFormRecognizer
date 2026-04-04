# Document Processor API

API RESTful para procesamiento de documentos con Azure Form Recognizer. Soporta extracción de datos de:
- Curriculum Vitae (`curriculum_vitae`)
- Título universitario (`titulo_universitario`)
- Concentración de notas (`concentracion_notas`)
- Cédula de identidad (`cedula_identidad`)
- Cotización AFP (`cotizacion_afp`)

## 🎯 Qué puedes hacer
- Autenticar clientes con JWT
- Listar y detallar tipos de documento
- Procesar archivos PDF/PNG/JPG/JPEG
- Consultar modelos Azure configurados
- Mantener rate limiting y seguridad con headers
- Probar con una demo web simple

## ⭐ Por qué usarlo
Este proyecto no es solo una API de ejemplo: está pensado para integrarse rápido en flujos reales de captura y validación documental.

- Reduce trabajo manual al extraer datos estructurados desde documentos comunes.
- Centraliza autenticación, validación y procesamiento en un solo servicio.
- Incluye una demo funcional para validar la integración sin construir UI propia.
- Expone una API limpia y predecible para automatizar procesos desde cualquier backend.
- Ya viene con seguridad, límites de uso y documentación lista para equipos técnicos.

## 🚀 Demo disponible
El proyecto tiene una demo liviana que carga una página web estática y consume la API local.

### Iniciar demo
```bash
make demo-up
```

Esto equivale a:
```bash
make docker-up DEMO=1
```

La demo queda disponible en:
- `http://localhost:8081`

La página demo usa:
- `client_name=DEMO`
- `action_name=process_documents`
- `cliente_id=DEMO`

> Para que la demo funcione, agrega un cliente demo en `ALLOWED_CLIENTS`, por ejemplo:
> `ALLOWED_CLIENTS=DEMO:demo_key_123,cliente1:clave1`

## 📦 Inicio rápido

### 1. Clonar el repositorio
```bash
git clone <repo-url>
cd AzureFormRecognizer
```

### 2. Copiar el archivo de ejemplo
```bash
cp .env.example .env
```

### 3. Configurar variables de entorno
Edita `.env` con tus credenciales de Azure y JWT.

### 4. Instalar dependencias (opcional para desarrollo local)
```bash
make install
```

### 5. Iniciar con Docker
```bash
make docker-up-build
```

Con demo:
```bash
make docker-up-build DEMO=1
```

### 6. Ver la API
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

### Ejecutar sin Docker
Si prefieres correrlo de forma local durante el desarrollo:

```bash
cp .env.example .env
make install
make dev
```

La API quedará disponible en `http://localhost:8000`.

## 🔧 Variables de entorno
El servicio carga `.env` mediante Pydantic Settings. Estas son las variables principales:

| Variable | Descripción | Default / Nota |
|----------|-------------|----------------|
| `AZURE_FORM_RECOGNIZER_ENDPOINT` | Endpoint de Azure Form Recognizer | obligatorio |
| `AZURE_FORM_RECOGNIZER_API_KEY` | API Key de Azure | obligatorio |
| `AZURE_FORM_RECOGNIZER_API_VERSION` | Versión de la API de Azure | `2023-07-31` |
| `JWT_SECRET_KEY` | Clave secreta JWT para firmar tokens | obligatorio |
| `JWT_ALGORITHM` | Algoritmo JWT | `HS256` |
| `JWT_EXPIRATION_MINUTES` | Expiración del token en minutos | `30` |
| `ALLOWED_CLIENTS` | Clientes autorizados `name:key,name2:key2` | obligatorio |
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `MAX_FILE_SIZE_MB` | Tamaño máximo de archivo | `10` |
| `ALLOWED_FILE_TYPES` | Tipos MIME permitidos | `application/pdf,image/png,image/jpeg` |
| `REDIS_URL` | Redis para rate limiting | `redis://localhost:6379/0` |
| `RATE_LIMIT_REQUESTS` | Requests por ventana | `100` |
| `RATE_LIMIT_WINDOW` | Ventana en segundos | `3600` |
| `CUSTOM_MODEL_TITULO` | Modelo custom para títulos universitarios | `model-titulo-universitario` |
| `CUSTOM_MODEL_NOTAS` | Modelo custom para concentración de notas | `model-concentracion-notas` |
| `CUSTOM_MODEL_AFP` | Modelo custom para cotizaciones AFP | `model-cotizacion-afp` |
| `HOST` | Host para desarrollo local | `0.0.0.0` |
| `PORT` | Puerto para desarrollo local | `8000` |
| `RELOAD` | Recarga automática en dev | `false` |

> Si usas la demo, asegúrate de tener un cliente `DEMO` en `ALLOWED_CLIENTS`.

## 🧠 API RESTful

### Autenticación
Todos los endpoints protegidos requieren el header:
```http
Authorization: Bearer <token>
```

### Endpoints principales

| Endpoint | Método | Protegido | Descripción |
|---|---|---|---|
| `/` | GET | No | Información básica del servicio |
| `/health` | GET | No | Health check general |
| `/api/v1/ping` | GET | No | Ping rápido |
| `/api/v1/auth/token` | POST | No | Generar token JWT |
| `/api/v1/auth/verify` | GET | Sí | Verificar token válido |
| `/api/v1/document-types` | GET | Sí | Listar tipos de documento |
| `/api/v1/document-types/{doc_type}` | GET | Sí | Detalle de un tipo de documento |
| `/api/v1/documents/process` | POST | Sí | Procesar documento con Azure |
| `/api/v1/azure/models` | GET | Sí | Listar modelos Azure configurados |
| `/api/v1/azure/status` | GET | Sí | Estado de conexión con Azure |
| `/api/v1/config` | GET | Sí | Configuración activa de la API |
| `/api/v1/stats` | GET | Sí | Estadísticas y métricas simples |

### Solicitud de token
```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "client_name": "cliente1",
  "action_name": "process_documents",
  "shared_key": "clave1"
}
```

Respuesta esperada:
```json
{
  "access_token": "eyJhb...",
  "token_type": "bearer",
  "expires_in": 1800,
  "client_name": "cliente1",
  "action_name": "process_documents"
}
```

### Procesar documento
```http
POST /api/v1/documents/process
Authorization: Bearer <token>
Content-Type: multipart/form-data

archivo=@/ruta/al/documento.pdf
tipo_documento=curriculum_vitae
cliente_id=cliente_123
```

Campos:
- `archivo`: archivo PDF/PNG/JPG/JPEG
- `tipo_documento`: tipo de documento soportado
- `cliente_id`: opcional para tracking

### Ejemplos de respuesta
```json
{
  "success": true,
  "document_type": "curriculum_vitae",
  "data": {
    "nombre": "Juan Pérez",
    "email": "juan@example.com",
    "experiencia": [ ... ]
  },
  "correlation_id": "abc123",
  "message": "Documento procesado"
}
```

### Otros endpoints útiles
```bash
# Verificar token
curl http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer <token>"

# Ver configuración activa
curl http://localhost:8000/api/v1/config \
  -H "Authorization: Bearer <token>"

# Ver modelos Azure
curl http://localhost:8000/api/v1/azure/models \
  -H "Authorization: Bearer <token>"
```

## 🔐 Seguridad
Esta API incluye controles de seguridad clave para proteger el acceso,
la integridad de los datos y la plataforma:

- Autenticación JWT para todos los endpoints de negocio.
- Validación de `ALLOWED_CLIENTS` con `client_name` y `shared_key`.
- Tokens firmados con `JWT_SECRET_KEY` y expiración configurable.
- Rate limiting por IP (`RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`).
- Validación de archivos por tamaño y tipo MIME antes de procesar.
- Headers de seguridad aplicados a las respuestas HTTP.
- CORS abierto pero con `Authorization` permitido y headers expuestos.
- Logs estructurados con `correlation_id` para trazabilidad.

### ¿Qué cubre esta protección?
- Prevención de uso no autorizado de la API.
- Protección contra envío de archivos demasiado grandes.
- Restricción de clientes sólo a los permitidos en `ALLOWED_CLIENTS`.
- Detección y auditoría con correlation ID en cada request.

> Nota: para entornos de producción, asegúrate de usar un `JWT_SECRET_KEY` seguro,
> definir los clientes reales en `ALLOWED_CLIENTS` y usar Redis o un sistema de cache
> adecuado para el rate limiting.

## 🧩 Casos de uso reales
Este servicio encaja bien cuando necesitas automatizar validaciones documentales sin construir una solución desde cero:

- Onboarding de clientes con lectura automática de documentos.
- Carga masiva de CVs para portales de empleo o RR. HH.
- Validación de títulos, notas o identificaciones en procesos administrativos.
- Integración con backends existentes que ya consumen APIs REST.
- Pruebas rápidas con la demo antes de conectar una interfaz propia.

## ⚠️ Errores comunes
Si algo falla, normalmente se debe a uno de estos puntos:

- `401 Unauthorized`: el token expiró o el `shared_key` no coincide con `ALLOWED_CLIENTS`.
- `403 Forbidden`: el token es válido, pero no tiene acceso para esa acción.
- `413 Payload Too Large`: el archivo supera `MAX_FILE_SIZE_MB`.
- `429 Too Many Requests`: se alcanzó el límite de `RATE_LIMIT_REQUESTS`.
- `500 Internal Server Error`: revisa `AZURE_FORM_RECOGNIZER_ENDPOINT`, `AZURE_FORM_RECOGNIZER_API_KEY` y los modelos custom.

Si usas la demo, confirma además que exista `DEMO` dentro de `ALLOWED_CLIENTS`.

## 🧪 Ejemplos de uso

### 1) Curl - obtener token y procesar documento
```bash
token=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_name":"cliente1","action_name":"process_documents","shared_key":"clave1"}' \
  | jq -r '.access_token')

curl -X POST http://localhost:8000/api/v1/documents/process \
  -H "Authorization: Bearer $token" \
  -F "archivo=@documento.pdf" \
  -F "tipo_documento=curriculum_vitae" \
  -F "cliente_id=cliente1"
```

### 2) Python (requests)
```python
import requests

base_url = 'http://localhost:8000'

resp = requests.post(
    f'{base_url}/api/v1/auth/token',
    json={
        'client_name': 'cliente1',
        'action_name': 'process_documents',
        'shared_key': 'clave1'
    }
)
resp.raise_for_status()
token = resp.json()['access_token']

with open('documento.pdf', 'rb') as f:
    files = {'archivo': ('documento.pdf', f, 'application/pdf')}
    data = {'tipo_documento': 'curriculum_vitae', 'cliente_id': 'cliente1'}
    result = requests.post(
        f'{base_url}/api/v1/documents/process',
        headers={'Authorization': f'Bearer {token}'},
        files=files,
        data=data
    )
    print(result.json())
```

### 3) Node.js (axios + form-data)
```js
import axios from 'axios';
import FormData from 'form-data';
import fs from 'fs';

const baseUrl = 'http://localhost:8000';
const tokenResp = await axios.post(`${baseUrl}/api/v1/auth/token`, {
  client_name: 'cliente1',
  action_name: 'process_documents',
  shared_key: 'clave1'
});
const token = tokenResp.data.access_token;

const form = new FormData();
form.append('archivo', fs.createReadStream('documento.pdf'));
form.append('tipo_documento', 'curriculum_vitae');
form.append('cliente_id', 'cliente1');

const response = await axios.post(
  `${baseUrl}/api/v1/documents/process`,
  form,
  {
    headers: {
      Authorization: `Bearer ${token}`,
      ...form.getHeaders()
    }
  }
);
console.log(response.data);
```

### 4) Java (OkHttp)
```java
import okhttp3.*;
import java.io.File;

OkHttpClient client = new OkHttpClient();
String baseUrl = "http://localhost:8000";

RequestBody tokenBody = RequestBody.create(
    MediaType.get("application/json; charset=utf-8"),
    "{\"client_name\":\"cliente1\",\"action_name\":\"process_documents\",\"shared_key\":\"clave1\"}"
);
Request tokenRequest = new Request.Builder()
    .url(baseUrl + "/api/v1/auth/token")
    .post(tokenBody)
    .build();
String token = client.newCall(tokenRequest).execute().body().string();

// Procesamiento multipart
File file = new File("documento.pdf");
RequestBody multipartBody = new MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart("archivo", file.getName(), RequestBody.create(file, MediaType.parse("application/pdf")))
    .addFormDataPart("tipo_documento", "curriculum_vitae")
    .addFormDataPart("cliente_id", "cliente1")
    .build();

Request processRequest = new Request.Builder()
    .url(baseUrl + "/api/v1/documents/process")
    .header("Authorization", "Bearer " + token)
    .post(multipartBody)
    .build();
String processResult = client.newCall(processRequest).execute().body().string();
System.out.println(processResult);
```

### 5) PHP (cURL)
```php
<?php
$baseUrl = 'http://localhost:8000';
$tokenPayload = json_encode([
    'client_name' => 'cliente1',
    'action_name' => 'process_documents',
    'shared_key' => 'clave1'
]);

$ch = curl_init("$baseUrl/api/v1/auth/token");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
curl_setopt($ch, CURLOPT_POSTFIELDS, $tokenPayload);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$tokenResp = curl_exec($ch);
curl_close($ch);
$tokenData = json_decode($tokenResp, true);
$token = $tokenData['access_token'];

$ch = curl_init("$baseUrl/api/v1/documents/process");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ["Authorization: Bearer $token"]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, [
    'archivo' => new CURLFile('documento.pdf', 'application/pdf'),
    'tipo_documento' => 'curriculum_vitae',
    'cliente_id' => 'cliente1'
]);
$response = curl_exec($ch);
curl_close($ch);
echo $response;
```

## 🐳 Docker

### Construir y ejecutar
```bash
make docker-build
make docker-up
```

### Con demo web
```bash
make docker-up DEMO=1
```

### Detener
```bash
make docker-down
```

### Logs de la API
```bash
make docker-logs-api
```

## 📚 Documentación y recursos
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Guía de modelos custom: `docs/AZURE_CUSTOM_MODELS.md`

## 🧪 Tests
```bash
pytest
pytest --cov=app --cov-report=html
```

## 📌 Nota sobre el DEMO
El demo es una forma rápida de verificar la integración sin escribir código. Solo necesitas:
1. Iniciar la API y el demo web con `make demo-up`.
2. Abrir `http://localhost:8081`.
3. Ingresar la URL de la API local y la shared key del cliente `DEMO`.

Esto envía automáticamente el token y el archivo a `/api/v1/documents/process`.

Si estás evaluando el proyecto, la demo es la forma más directa de comprobar el valor real del sistema: subes un documento, obtienes el token, procesas el archivo y ves la respuesta estructurada sin escribir una sola línea de integración.

## 🧾 Tipos de documento soportados
| Tipo | Modelo Azure | Descripción |
|---|---|---|
| `curriculum_vitae` | `prebuilt-resume` | Hoja de vida / CV |
| `titulo_universitario` | `CUSTOM_MODEL_TITULO` | Título universitario |
| `concentracion_notas` | `CUSTOM_MODEL_NOTAS` | Certificado de notas |
| `cedula_identidad` | `prebuilt-idDocument` | Cédula de identidad |
| `cotizacion_afp` | `CUSTOM_MODEL_AFP` | Cotización AFP |

## 🔧 Configuración de la demo
La demo web está en `demo/index.html` y se sirve desde el contenedor `demo-web`.

- URL de demo: `http://localhost:8081`
- API base: `http://localhost:8000`
- Token demo: se pide a `/api/v1/auth/token` con `client_name=DEMO`
- Procesamiento: `/api/v1/documents/process`

## 📁 Estructura de archivos
Esta sección complementa el README con el diagrama de los archivos principales.

```text
.
├── app/                    # Código de la API en FastAPI
│   ├── __init__.py
│   ├── auth.py
│   ├── azure_client.py
│   ├── config.py
│   ├── main.py
│   ├── middleware.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document_types.py
│   │   ├── schemas.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── document_processor.py
│   │       └── model_mapper.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       └── validators.py
├── demo/                   # Página web de demo estática
│   └── index.html
├── docker/                 # Dockerfile y docker-compose
│   ├── docker-compose.yml
│   └── Dockerfile
├── docs/                   # Documentación adicional
│   └── AZURE_CUSTOM_MODELS.md
├── scripts/                # Scripts de prueba
│   └── test_api.py
├── tests/                  # Pruebas unitarias
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_azure_client_config.py
│   ├── test_document_processor.py
│   ├── test_validators.py
│   └── fixtures/
│       └── sample_documents/
├── .env.example            # Ejemplo de variables de entorno
├── Makefile                # Comandos útiles
└── README.md               # Documentación principal
```
