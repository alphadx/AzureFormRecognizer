# Changelog

Todos los cambios notables de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added
- API RESTful completa con FastAPI
- Soporte para 5 tipos de documento:
  - Curriculum Vitae (prebuilt-resume)
  - Título Universitario (custom model)
  - Concentración de Notas (custom model)
  - Cédula de Identidad (prebuilt-identityDocument)
  - Cotización AFP (custom model)
- Autenticación JWT con validación de cliente y acción
- Rate limiting (100 requests/hora por IP)
- Compresión GZip automática
- Logging estructurado en JSON con correlation_id
- Docker y Docker Compose completamente configurados
- Tests unitarios con pytest (cobertura > 70%)
- Middlewares de seguridad (CSP, HSTS, X-Frame-Options)
- Documentación completa (README, Swagger, ReDoc)
- Scripts de prueba (Bash y Python)
- Guía para entrenar modelos custom en Azure

### Security
- Headers de seguridad implementados
- Validación de archivos (tipo MIME, extensión, tamaño)
- Protección contra timing attacks en comparación de claves
- Rate limiting por IP

## [Unreleased]

### Planned
- Soporte para procesamiento por lotes (batch)
- Caché de documentos procesados (Redis)
- Webhooks para notificaciones
- Dashboard de monitoreo
- Soporte para más tipos de documento
- Internacionalización (i18n)
