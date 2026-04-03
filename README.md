# Document Processor API

API RESTful para procesamiento de documentos con Azure Form Recognizer. Soporta extracción de datos de CVs, títulos universitarios, certificados de notas, cédulas de identidad y cotizaciones AFP.

## 🎯 Características

- **5 tipos de documento** soportados con modelos específicos
- **Autenticación JWT** con validación de cliente y acción
- **Rate limiting** (100 requests/hora por IP)
- **Compresión GZip** automática
- **Logging estructurado** en JSON
- **Docker** completamente containerizado
- **Tests unitarios** con pytest

## 📋 Requisitos

- Docker y Docker Compose
- Cuenta de Azure con Form Recognizer
- Python 3.10+ (para desarrollo local)

## 🚀 Inicio Rápido

### 1. Clonar y Configurar

```bash
git clone <repo-url>
cd document-processor
cp .env.example .env
```

### 2. Configurar Variables de Entorno

Edita `.env` con tus credenciales:

```bash
# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://tu-recurso.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_API_KEY=tu-api-key

# JWT
JWT_SECRET_KEY=tu-clave-secreta-muy-larga
ALLOWED_CLIENTS=cliente1:clave1,cliente2:clave2
```

### 3. Iniciar con Docker

```bash
make docker-up-build
```

Modo demo (levanta una web de pruebas en otro contenedor):

```bash
make docker-up-build DEMO=1
# o equivalente
make demo-up-build
```

La web demo queda disponible en `http://localhost:8081`.

### 4. Probar la API

```bash
# Health check
curl http://localhost:8000/health

# Documentación Swagger
open http://localhost:8000/docs
```

## 📖 Documentación de la API

### Autenticación

Todos los endpoints protegidos requieren un token JWT:

```bash
# Obtener token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "cliente1",
    "action_name": "process_documents",
    "shared_key": "clave1"
  }'

# Usar token
curl http://localhost:8000/api/v1/document-types \
  -H "Authorization: Bearer <token>"
```

### Endpoints Principales

| Endpoint | Método | Auth | Descripción |
|----------|--------|------|-------------|
| `/health` | GET | ❌ | Health check |
| `/api/v1/auth/token` | POST | ❌ | Obtener JWT |
| `/api/v1/document-types` | GET | ✅ | Tipos soportados |
| `/api/v1/documents/process` | POST | ✅ | Procesar documento |
| `/api/v1/azure/models` | GET | ✅ | Modelos Azure |

### Procesar un Documento

```bash
curl -X POST http://localhost:8000/api/v1/documents/process \
  -H "Authorization: Bearer <token>" \
  -F "archivo=@/ruta/al/documento.pdf" \
  -F "tipo_documento=curriculum_vitae" \
  -F "cliente_id=opcional"
```

### Tipos de Documento Soportados

| Tipo | Modelo Azure | Campos Principales |
|------|--------------|-------------------|
| `curriculum_vitae` | prebuilt-resume | nombre, email, experiencia, educación, habilidades |
| `titulo_universitario` | custom | institución, carrera, fecha_emisión, número_título |
| `concentracion_notas` | custom | asignaturas[{nombre, nota, créditos}], promedio |
| `cedula_identidad` | prebuilt-identityDocument | nombre, rut, fecha_nacimiento, nacionalidad |
| `cotizacion_afp` | custom | institución, monto, fecha, tipo_cotización |

## 🐳 Docker

### Desarrollo

```bash
# Construir y ejecutar
make docker-up-build

# Ejecutar en segundo plano
make docker-up

# Incluir demo web opcional
make docker-up DEMO=1

# Ver logs
make docker-logs

# Detener
make docker-down
```

### Demo Web de Pruebas

Cuando usas `DEMO=1`, se activa un contenedor `demo-web` (Nginx liviano) que sirve una página para probar el endpoint de procesamiento.

- URL demo: `http://localhost:8081`
- API esperada: `http://localhost:8000`
- Flujo: solicita token con `client_name=DEMO` y luego envía `archivo`, `tipo_documento` y `cliente_id=DEMO` al endpoint `/api/v1/documents/process`

### Producción

```bash
# Construir imagen
docker build -f docker/Dockerfile -t document-processor:latest .

# Ejecutar
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name document-processor \
  document-processor:latest
```

## 🧪 Tests

```bash
# Instalar dependencias de desarrollo
pip install -r requirements.txt

# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=app --cov-report=html

# Tests específicos
pytest tests/test_auth.py -v
pytest tests/test_api.py -v
```

## 📊 Monitoreo

### Health Checks

```bash
# Health básico
curl http://localhost:8000/health

# Health detallado
curl http://localhost:8000/health/detailed

# Estadísticas
curl http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer <token>"
```

### Logs

Los logs están en formato JSON estructurado:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Document processed",
  "correlation_id": "abc12345",
  "document_type": "curriculum_vitae",
  "confidence_score": 0.94
}
```

Ver logs del contenedor:
```bash
docker logs document-processor-api -f
```

## 🔧 Configuración

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `AZURE_FORM_RECOGNIZER_ENDPOINT` | Endpoint de Azure | - |
| `AZURE_FORM_RECOGNIZER_API_KEY` | API Key de Azure | - |
| `JWT_SECRET_KEY` | Clave secreta JWT | - |
| `JWT_EXPIRATION_MINUTES` | Expiración del token | 30 |
| `ALLOWED_CLIENTS` | Clientes permitidos (formato: name:key,name2:key2) | - |
| `MAX_FILE_SIZE_MB` | Tamaño máximo de archivo | 10 |
| `RATE_LIMIT_REQUESTS` | Requests por ventana | 100 |
| `RATE_LIMIT_WINDOW` | Ventana en segundos | 3600 |
| `LOG_LEVEL` | Nivel de logging | INFO |

### Rate Limiting

- **Límite**: 100 requests por hora por IP
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Respuesta 429**: Cuando se excede el límite

## 🎓 Entrenar Modelos Custom en Azure

Para los tipos de documento que usan modelos custom (`titulo_universitario`, `concentracion_notas`, `cotizacion_afp`), debes entrenar modelos en Azure Form Recognizer.

### Pasos:

1. **Crear proyecto en Azure AI Document Intelligence**
   ```bash
   # Ir a Azure Portal > Create Resource > AI Document Intelligence
   ```

2. **Etiquetar documentos de entrenamiento**
   - Subir al menos 5 documentos de ejemplo
   - Etiquetar cada campo que quieres extraer
   - Guardar el proyecto

3. **Entrenar el modelo**
   ```bash
   # En el portal de Azure AI Document Intelligence
   # Train > Create new model > Seleccionar documentos etiquetados
   ```

4. **Obtener el Model ID**
   - Ir a Models > Seleccionar modelo
   - Copiar el Model ID (ej: `model-titulo-universitario`)

5. **Configurar en .env**
   ```bash
   CUSTOM_MODEL_TITULO=model-titulo-universitario
   CUSTOM_MODEL_NOTAS=model-concentracion-notas
   CUSTOM_MODEL_AFP=model-cotizacion-afp
   ```

### Campos Recomendados por Tipo

#### Título Universitario
- `institucion` (string)
- `carrera` (string)
- `nombre_titular` (string)
- `rut_titular` (string)
- `fecha_emision` (date)
- `numero_titulo` (string)
- `grado_academico` (string)

#### Concentración de Notas
- `institucion` (string)
- `carrera` (string)
- `nombre_estudiante` (string)
- `periodo_academico` (string)
- `asignaturas` (array)
  - `nombre` (string)
  - `nota` (number)
  - `creditos` (number)
- `promedio_ponderado` (number)

#### Cotización AFP
- `institucion` (string)
- `rut_afiliado` (string)
- `nombre_afiliado` (string)
- `fecha_cotizacion` (date)
- `periodo` (string)
- `monto_cotizacion_obligatoria` (number)
- `monto_cotizacion_voluntaria` (number)
- `monto_total` (number)

## 📁 Estructura del Proyecto

```
document-processor/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuración
│   ├── auth.py                 # Autenticación JWT
│   ├── azure_client.py         # Cliente Azure
│   ├── middleware.py           # Middlewares
│   ├── models/
│   │   ├── document_types.py   # Definiciones de documentos
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── document_processor.py
│   │   └── model_mapper.py
│   └── utils/
│       ├── logger.py
│       └── validators.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_document_processor.py
│   ├── test_validators.py
│   └── test_api.py
├── .env.example
├── pytest.ini
├── requirements.txt
└── README.md
```

## 🔒 Seguridad

- **JWT**: Tokens con expiración configurable (default 30 min)
- **Rate Limiting**: Protección contra abuso
- **Headers de seguridad**: CSP, HSTS, X-Frame-Options, etc.
- **Validación de archivos**: Tipo MIME, extensión, tamaño
- **Comparación segura**: Protección contra timing attacks

## 🐛 Troubleshooting

### Azure no configurado
```
Error: Azure Form Recognizer not configured
```
**Solución**: Configurar `AZURE_FORM_RECOGNIZER_ENDPOINT` y `AZURE_FORM_RECOGNIZER_API_KEY`

### Token inválido
```
Error: Invalid token
```
**Solución**: Obtener nuevo token en `/api/v1/auth/token`

### Rate limit excedido
```
Error: Rate limit exceeded
```
**Solución**: Esperar 1 hora o aumentar `RATE_LIMIT_REQUESTS`

### Archivo demasiado grande
```
Error: File too large
```
**Solución**: Reducir tamaño del archivo o aumentar `MAX_FILE_SIZE_MB`

## 📄 Licencia

MIT License - ver LICENSE para detalles.

## 🤝 Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📞 Soporte

- Email: support@example.com
- Issues: GitHub Issues
- Documentación: `/docs` (Swagger UI)

---

**Versión**: 1.0.0  
**Última actualización**: 2024
