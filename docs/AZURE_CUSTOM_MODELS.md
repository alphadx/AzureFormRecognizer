# Guía: Entrenar Modelos Custom en Azure Form Recognizer

Esta guía explica paso a paso cómo entrenar modelos custom para los tipos de documento que no tienen modelos prebuilt en Azure.

## 📋 Tipos que Requieren Modelos Custom

| Tipo de Documento | Modelo Prebuilt | Necesita Custom |
|-------------------|-----------------|-----------------|
| Curriculum Vitae | ✅ `prebuilt-resume` | ❌ |
| Cédula de Identidad | ✅ `prebuilt-idDocument` | ❌ |
| **Título Universitario** | ❌ | ✅ |
| **Concentración de Notas** | ❌ | ✅ |
| **Cotización AFP** | ❌ | ✅ |

## 🚀 Paso a Paso

### Paso 1: Crear Recurso de Azure AI Document Intelligence

1. Ve al [Azure Portal](https://portal.azure.com)
2. Click en **"Create a resource"**
3. Busca **"Azure AI Document Intelligence"** (anteriormente Form Recognizer)
4. Click **"Create"**
5. Completa la información:
   - **Subscription**: Tu suscripción de Azure
   - **Resource group**: Crear nuevo o seleccionar existente
   - **Region**: Selecciona la más cercana (ej: East US)
   - **Name**: `document-processor-ai`
   - **Pricing tier**: Free (F0) para pruebas, Standard (S0) para producción
6. Click **"Review + create"** y luego **"Create"**

### Paso 2: Obtener Credenciales

1. Una vez creado el recurso, ve a **"Keys and Endpoint"**
2. Copia:
   - **Endpoint**: `https://<nombre>.cognitiveservices.azure.com/`
   - **KEY 1**: Tu API key
3. Guarda estos valores para configurar en `.env`:
   ```bash
   AZURE_FORM_RECOGNIZER_ENDPOINT=https://<nombre>.cognitiveservices.azure.com/
   AZURE_FORM_RECOGNIZER_API_KEY=<tu-api-key>
   ```

### Paso 3: Acceder al Studio de Document Intelligence

1. En el recurso de Azure, click en **"Document Intelligence Studio"**
2. O ve directamente a: https://documentintelligence.ai.azure.com
3. Inicia sesión con tu cuenta de Azure
4. Selecciona tu subscription y resource

### Paso 4: Crear Proyecto

1. En el Document Intelligence Studio, click en **"Custom models"**
2. Click en **"Create a project"**
3. Completa:
   - **Project name**: `titulos-universitarios` (o el nombre que prefieras)
   - **Description**: "Modelo para extraer datos de títulos universitarios"
   - **Service resource**: Selecciona el recurso creado
   - **Storage account**: Crea nuevo o selecciona existente
4. Click **"Create project"**

### Paso 5: Subir Documentos de Entrenamiento

Necesitas **mínimo 5 documentos** de ejemplo (recomendado: 10-15).

1. En el proyecto, click en **"+ Add documents"**
2. Selecciona los archivos PDF/imágenes de títulos universitarios
3. Click **"Upload"**

**Requisitos de los documentos:**
- Formatos: PDF, PNG, JPG, TIFF
- Tamaño máximo: 50 MB por archivo
- Resolución mínima: 200 DPI para imágenes
- Documentos variados (diferentes universidades, formatos, años)

### Paso 6: Etiquetar Campos

Este es el paso más importante. Debes etiquetar cada campo que quieres extraer.

#### Para Título Universitario:

1. Abre el primer documento
2. Click en **"+ Add field"** para cada campo:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `institucion` | String | Nombre de la universidad |
| `carrera` | String | Nombre de la carrera |
| `nombre_titular` | String | Nombre completo del graduado |
| `rut_titular` | String | RUT del titular |
| `fecha_emision` | Date | Fecha de emisión del título |
| `numero_titulo` | String | Número de registro del título |
| `grado_academico` | String | Grado otorgado (Licenciado, etc.) |

3. Para cada campo:
   - Selecciona el tipo de dato
   - Dibuja un rectángulo alrededor del valor en el documento
   - Verifica que el valor detectado sea correcto

4. Repite para todos los documentos

**Tip**: Etiqueta al menos 5 documentos completamente antes de entrenar.

### Paso 7: Entrenar el Modelo

1. Click en **"Train"** (barra superior)
2. Selecciona **"Template"** (para documentos con formato fijo) o **"Neural"** (para mayor flexibilidad)
3. Click **"Train"**
4. Espera 5-30 minutos (depende de la cantidad de documentos)

### Paso 8: Obtener el Model ID

1. Una vez entrenado, ve a **"Models"** en el menú lateral
2. Encuentra tu modelo en la lista
3. Copia el **Model ID** (ej: `titulos-universitarios-model-v1`)

### Paso 9: Configurar en la API

Edita tu archivo `.env`:

```bash
# Modelos Custom de Azure
CUSTOM_MODEL_TITULO=titulos-universitarios-model-v1
CUSTOM_MODEL_NOTAS=concentracion-notas-model-v1
CUSTOM_MODEL_AFP=cotizaciones-afp-model-v1
```

Reinicia la aplicación:
```bash
docker-compose -f docker/docker-compose.yml restart
```

### Paso 10: Probar el Modelo

```bash
# Obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_name":"cliente1","action_name":"process_documents","shared_key":"clave1"}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# Procesar documento
curl -X POST http://localhost:8000/api/v1/documents/process \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@/ruta/al/titulo.pdf" \
  -F "tipo_documento=titulo_universitario"
```

## 📊 Mejores Prácticas

### Documentos de Entrenamiento

| Recomendación | Por qué |
|---------------|---------|
| **Mínimo 5 documentos** | Azure requiere al menos 5 para entrenar |
| **Máxima variedad** | Diferentes formatos, fuentes, calidades |
| **Buena calidad** | Evita documentos borrosos o cortados |
| **Datos reales** | Usa documentos reales (anónimizados) |

### Etiquetado

| Recomendación | Por qué |
|---------------|---------|
| **Sé consistente** | Mismo campo = mismo nombre en todos los docs |
| **Etiqueta todo** | No dejes campos sin etiquetar |
| **Verifica OCR** | Asegúrate que Azure leyó correctamente |
| **Usa tipos correctos** | Date para fechas, Number para números |

### Tipos de Modelo

| Tipo | Cuándo usar | Ventajas |
|------|-------------|----------|
| **Template** | Formularios estructurados | Más rápido, menor costo |
| **Neural** | Documentos variados | Más flexible, mejor precisión |
| **Composed** | Múltiples modelos | Combina varios modelos |

## 🔧 Solución de Problemas

### "No se detectan campos"

**Causa**: El OCR no puede leer el texto

**Solución**:
- Verifica que la imagen tenga buena resolución (200+ DPI)
- Aumenta el contraste del documento
- Recorta bordes en blanco excesivos

### "Campos detectados incorrectamente"

**Causa**: Etiquetado inconsistente

**Solución**:
- Revisa que el mismo campo tenga el mismo nombre en todos los docs
- Verifica que los rectángulos de selección sean precisos
- Añade más documentos de entrenamiento

### "Baja precisión en extracción"

**Causa**: Pocos documentos de entrenamiento o poca variedad

**Solución**:
- Aumenta a 10-15 documentos
- Incluye documentos de diferentes fuentes
- Entrena con modelo Neural en lugar de Template

### "Modelo no aparece en la lista"

**Causa**: El entrenamiento falló o está en progreso

**Solución**:
- Ve a **"Training jobs"** para ver el estado
- Si falló, revisa el error y reentrena
- Espera a que termine (puede tomar 30+ minutos)

## 💰 Costos

Azure cobra por:
- **Entrenamiento**: ~$0.05 por página de entrenamiento
- **Análisis**: ~$0.05 por página analizada

Ejemplo mensual:
- 100 documentos procesados/día × 30 días = $150/mes
- 1,000 documentos/día = $1,500/mes

**Tips para reducir costos:**
- Usa modelos prebuilt cuando existan
- Comprime documentos antes de enviar
- Implementa caché para documentos repetidos
- Usa Azure Reserved Capacity para descuentos

## 📚 Recursos Adicionales

- [Documentación oficial de Azure Form Recognizer](https://docs.microsoft.com/azure/applied-ai-services/form-recognizer/)
- [Document Intelligence Studio](https://documentintelligence.ai.azure.com)
- [Precios de Azure AI Document Intelligence](https://azure.microsoft.com/pricing/details/form-recognizer/)
- [Límites y cuotas](https://docs.microsoft.com/azure/applied-ai-services/form-recognizer/service-limits)

## ✅ Checklist

Antes de usar un modelo custom en producción:

- [ ] Mínimo 5 documentos etiquetados
- [ ] Entrenamiento completado exitosamente
- [ ] Pruebas con documentos nuevos (no de entrenamiento)
- [ ] Precisión > 80% en campos críticos
- [ ] Model ID configurado en `.env`
- [ ] API reiniciada con nueva configuración
- [ ] Documentación actualizada
