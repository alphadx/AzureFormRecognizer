# Documentos de Ejemplo para Tests

Esta carpeta contiene documentos de ejemplo para pruebas.

## Archivos

### PDFs
- `sample_cv.pdf` - CV de ejemplo
- `sample_titulo.pdf` - Título universitario de ejemplo
- `sample_cedula.pdf` - Cédula de identidad de ejemplo
- `sample_notas.pdf` - Concentración de notas de ejemplo
- `sample_afp.pdf` - Cotización AFP de ejemplo

### Imágenes
- `sample_cedula.png` - Cédula como imagen PNG
- `sample_titulo.jpg` - Título como imagen JPG

## Generación

Para generar archivos de prueba válidos, puedes usar:

```python
# PDF mínimo válido
pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF"

# PNG mínimo válido
png_bytes = b"\x89PNG\r\n\x1a\n..."

# JPG mínimo válido
jpg_bytes = b"\xff\xd8\xff\xe0..."
```

## Notas

- Los archivos en esta carpeta son para testing únicamente
- No contienen información real
- Se usan mocks para simular respuestas de Azure en tests unitarios
