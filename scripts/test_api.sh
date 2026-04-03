#!/bin/bash
#
# Script de ejemplo para probar la Document Processor API
#
# Uso:
#   chmod +x scripts/test_api.sh
#   ./scripts/test_api.sh
#

set -e

# Configuración
API_URL="${API_URL:-http://localhost:8000}"
CLIENT_NAME="${CLIENT_NAME:-test_client}"
SHARED_KEY="${SHARED_KEY:-test_key_123}"
ACTION_NAME="${ACTION_NAME:-process_documents}"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Document Processor API - Test Script${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "API URL: ${API_URL}"
echo -e "Client: ${CLIENT_NAME}"
echo ""

# ============================================
# 1. Health Check
# ============================================
echo -e "${YELLOW}1. Health Check${NC}"
echo "----------------------------------------"
HEALTH_RESPONSE=$(curl -s "${API_URL}/health")
echo "Response: ${HEALTH_RESPONSE}"
echo ""

# ============================================
# 2. Obtener Token JWT
# ============================================
echo -e "${YELLOW}2. Obtener Token JWT${NC}"
echo "----------------------------------------"

TOKEN_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d "{
    \"client_name\": \"${CLIENT_NAME}\",
    \"action_name\": \"${ACTION_NAME}\",
    \"shared_key\": \"${SHARED_KEY}\"
  }")

echo "Response: ${TOKEN_RESPONSE}"

# Extraer token
TOKEN=$(echo "${TOKEN_RESPONSE}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "${TOKEN}" ]; then
    echo -e "${RED}Error: No se pudo obtener token${NC}"
    exit 1
fi

echo -e "${GREEN}Token obtenido exitosamente${NC}"
echo ""

# ============================================
# 3. Verificar Token
# ============================================
echo -e "${YELLOW}3. Verificar Token${NC}"
echo "----------------------------------------"
VERIFY_RESPONSE=$(curl -s "${API_URL}/api/v1/auth/verify" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${VERIFY_RESPONSE}"
echo ""

# ============================================
# 4. Obtener Tipos de Documento
# ============================================
echo -e "${YELLOW}4. Tipos de Documento Soportados${NC}"
echo "----------------------------------------"
DOC_TYPES=$(curl -s "${API_URL}/api/v1/document-types" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${DOC_TYPES}"
echo ""

# ============================================
# 5. Obtener Detalle de CV
# ============================================
echo -e "${YELLOW}5. Detalle de Curriculum Vitae${NC}"
echo "----------------------------------------"
CV_DETAIL=$(curl -s "${API_URL}/api/v1/document-types/curriculum_vitae" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${CV_DETAIL}"
echo ""

# ============================================
# 6. Obtener Modelos Azure
# ============================================
echo -e "${YELLOW}6. Modelos Azure Configurados${NC}"
echo "----------------------------------------"
AZURE_MODELS=$(curl -s "${API_URL}/api/v1/azure/models" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${AZURE_MODELS}"
echo ""

# ============================================
# 7. Obtener Configuración
# ============================================
echo -e "${YELLOW}7. Configuración de la API${NC}"
echo "----------------------------------------"
CONFIG=$(curl -s "${API_URL}/api/v1/config" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${CONFIG}"
echo ""

# ============================================
# 8. Procesar Documento (si existe archivo)
# ============================================
echo -e "${YELLOW}8. Procesar Documento${NC}"
echo "----------------------------------------"

# Crear un PDF de prueba mínimo
TEST_PDF="/tmp/test_document.pdf"
echo "%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
%%EOF" > "${TEST_PDF}"

if [ -f "${TEST_PDF}" ]; then
    echo "Enviando documento de prueba..."
    
    PROCESS_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/documents/process" \
      -H "Authorization: Bearer ${TOKEN}" \
      -F "archivo=@${TEST_PDF};type=application/pdf" \
      -F "tipo_documento=curriculum_vitae" \
      -F "cliente_id=test_001")
    
    echo "Response: ${PROCESS_RESPONSE}"
    
    # Limpiar
    rm -f "${TEST_PDF}"
else
    echo "No se pudo crear archivo de prueba"
fi

echo ""

# ============================================
# 9. Estadísticas
# ============================================
echo -e "${YELLOW}9. Estadísticas del Sistema${NC}"
echo "----------------------------------------"
STATS=$(curl -s "${API_URL}/api/v1/stats" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${STATS}"
echo ""

# ============================================
# 10. Test de Validación
# ============================================
echo -e "${YELLOW}10. Test de Validación${NC}"
echo "----------------------------------------"
TEST_RESPONSE=$(curl -s "${API_URL}/api/v1/test-validation" \
  -H "Authorization: Bearer ${TOKEN}")
echo "Response: ${TEST_RESPONSE}"
echo ""

# ============================================
# Resumen
# ============================================
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Tests completados exitosamente${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Token JWT (para uso manual):"
echo "${TOKEN}"
echo ""
echo "Uso manual:"
echo "  curl -H \"Authorization: Bearer ${TOKEN}\" ${API_URL}/api/v1/document-types"
