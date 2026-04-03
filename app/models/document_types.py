"""
Definición de tipos de documento y campos esperados
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


class DocumentType(str, Enum):
    """Enum de tipos de documento soportados"""
    CURRICULUM_VITAE = "curriculum_vitae"
    TITULO_UNIVERSITARIO = "titulo_universitario"
    CONCENTRACION_NOTAS = "concentracion_notas"
    CEDULA_IDENTIDAD = "cedula_identidad"
    COTIZACION_AFP = "cotizacion_afp"


class AzureModelType(str, Enum):
    """Enum de tipos de modelo Azure"""
    PREBUILT_RESUME = "prebuilt-resume"
    PREBUILT_IDENTITY = "prebuilt-identityDocument"
    PREBUILT_DOCUMENT = "prebuilt-document"
    CUSTOM = "custom"


@dataclass
class FieldDefinition:
    """Definición de un campo a extraer"""
    name: str
    description: str
    data_type: str  # string, number, date, array, object
    required: bool = True
    example: Any = None
    nested_fields: List['FieldDefinition'] = field(default_factory=list)


@dataclass
class DocumentTypeDefinition:
    """Definición completa de un tipo de documento"""
    type: DocumentType
    name: str
    description: str
    azure_model: str
    is_custom_model: bool
    fields: List[FieldDefinition]
    supported_extensions: List[str]
    max_pages: int = 10


# ============================================
# DEFINICIONES DE CAMPOS POR TIPO DE DOCUMENTO
# ============================================

# Curriculum Vitae - Usa prebuilt-resume
CV_FIELDS = [
    FieldDefinition(
        name="nombre",
        description="Nombre completo del candidato",
        data_type="string",
        example="Juan Pérez González"
    ),
    FieldDefinition(
        name="email",
        description="Correo electrónico",
        data_type="string",
        example="juan.perez@email.com"
    ),
    FieldDefinition(
        name="telefono",
        description="Número de teléfono",
        data_type="string",
        example="+56912345678"
    ),
    FieldDefinition(
        name="direccion",
        description="Dirección física",
        data_type="string",
        required=False,
        example="Santiago, Chile"
    ),
    FieldDefinition(
        name="experiencia_laboral",
        description="Lista de experiencias laborales",
        data_type="array",
        nested_fields=[
            FieldDefinition(
                name="empresa",
                description="Nombre de la empresa",
                data_type="string",
                example="Empresa XYZ"
            ),
            FieldDefinition(
                name="cargo",
                description="Cargo o posición",
                data_type="string",
                example="Desarrollador Senior"
            ),
            FieldDefinition(
                name="fecha_inicio",
                description="Fecha de inicio",
                data_type="string",
                example="2020-01"
            ),
            FieldDefinition(
                name="fecha_fin",
                description="Fecha de término",
                data_type="string",
                required=False,
                example="2023-12"
            ),
            FieldDefinition(
                name="descripcion",
                description="Descripción de funciones",
                data_type="string",
                required=False,
                example="Desarrollo de aplicaciones web"
            )
        ]
    ),
    FieldDefinition(
        name="educacion",
        description="Lista de estudios",
        data_type="array",
        nested_fields=[
            FieldDefinition(
                name="institucion",
                description="Nombre de la institución",
                data_type="string",
                example="Universidad de Chile"
            ),
            FieldDefinition(
                name="carrera",
                description="Carrera o título obtenido",
                data_type="string",
                example="Ingeniería Civil Informática"
            ),
            FieldDefinition(
                name="grado",
                description="Grado académico",
                data_type="string",
                example="Licenciatura"
            ),
            FieldDefinition(
                name="fecha_inicio",
                description="Año de inicio",
                data_type="string",
                required=False,
                example="2014"
            ),
            FieldDefinition(
                name="fecha_fin",
                description="Año de graduación",
                data_type="string",
                example="2019"
            )
        ]
    ),
    FieldDefinition(
        name="habilidades",
        description="Lista de habilidades técnicas y blandas",
        data_type="array",
        example=["Python", "FastAPI", "Docker", "Trabajo en equipo"]
    ),
    FieldDefinition(
        name="idiomas",
        description="Idiomas que domina",
        data_type="array",
        required=False,
        example=[{"idioma": "Español", "nivel": "Nativo"}, {"idioma": "Inglés", "nivel": "Avanzado"}]
    )
]

# Título Universitario - Modelo Custom
TITULO_FIELDS = [
    FieldDefinition(
        name="institucion",
        description="Nombre de la universidad o institución",
        data_type="string",
        example="Universidad de Chile"
    ),
    FieldDefinition(
        name="carrera",
        description="Nombre de la carrera o programa",
        data_type="string",
        example="Ingeniería Civil Informática"
    ),
    FieldDefinition(
        name="nombre_titular",
        description="Nombre completo del titular del título",
        data_type="string",
        example="Juan Pérez González"
    ),
    FieldDefinition(
        name="rut_titular",
        description="RUT del titular",
        data_type="string",
        required=False,
        example="12.345.678-9"
    ),
    FieldDefinition(
        name="fecha_emision",
        description="Fecha de emisión del título",
        data_type="string",
        example="2019-12-15"
    ),
    FieldDefinition(
        name="numero_titulo",
        description="Número de registro del título",
        data_type="string",
        example="T-12345-2019"
    ),
    FieldDefinition(
        name="grado_academico",
        description="Grado académico otorgado",
        data_type="string",
        example="Licenciado"
    ),
    FieldDefinition(
        name="duracion_anios",
        description="Duración de la carrera en años",
        data_type="number",
        required=False,
        example=5
    )
]

# Concentración de Notas - Modelo Custom
NOTAS_FIELDS = [
    FieldDefinition(
        name="institucion",
        description="Nombre de la institución educativa",
        data_type="string",
        example="Universidad de Chile"
    ),
    FieldDefinition(
        name="carrera",
        description="Carrera o programa",
        data_type="string",
        example="Ingeniería Civil Informática"
    ),
    FieldDefinition(
        name="nombre_estudiante",
        description="Nombre del estudiante",
        data_type="string",
        example="Juan Pérez González"
    ),
    FieldDefinition(
        name="rut_estudiante",
        description="RUT del estudiante",
        data_type="string",
        required=False,
        example="12.345.678-9"
    ),
    FieldDefinition(
        name="fecha_emision",
        description="Fecha de emisión del certificado",
        data_type="string",
        example="2023-06-30"
    ),
    FieldDefinition(
        name="periodo_academico",
        description="Período académico cubierto",
        data_type="string",
        example="2023-1"
    ),
    FieldDefinition(
        name="asignaturas",
        description="Lista de asignaturas cursadas",
        data_type="array",
        nested_fields=[
            FieldDefinition(
                name="codigo",
                description="Código de la asignatura",
                data_type="string",
                required=False,
                example="INF-101"
            ),
            FieldDefinition(
                name="nombre",
                description="Nombre de la asignatura",
                data_type="string",
                example="Programación I"
            ),
            FieldDefinition(
                name="nota",
                description="Calificación obtenida",
                data_type="number",
                example=6.5
            ),
            FieldDefinition(
                name="creditos",
                description="Créditos de la asignatura",
                data_type="number",
                example=6
            ),
            FieldDefinition(
                name="estado",
                description="Estado (aprobado/reprobado)",
                data_type="string",
                example="Aprobado"
            )
        ]
    ),
    FieldDefinition(
        name="promedio_ponderado",
        description="Promedio ponderado del período",
        data_type="number",
        example=5.8
    ),
    FieldDefinition(
        name="promedio_semestral",
        description="Promedio semestral",
        data_type="number",
        required=False,
        example=5.8
    ),
    FieldDefinition(
        name="total_creditos",
        description="Total de créditos cursados",
        data_type="number",
        required=False,
        example=24
    ),
    FieldDefinition(
        name="total_asignaturas",
        description="Total de asignaturas",
        data_type="number",
        required=False,
        example=4
    )
]

# Cédula de Identidad - Usa prebuilt-identityDocument
CEDULA_FIELDS = [
    FieldDefinition(
        name="nombre",
        description="Nombre completo",
        data_type="string",
        example="Juan Pérez González"
    ),
    FieldDefinition(
        name="rut",
        description="Rol Único Tributario",
        data_type="string",
        example="12.345.678-9"
    ),
    FieldDefinition(
        name="fecha_nacimiento",
        description="Fecha de nacimiento",
        data_type="string",
        example="1990-05-15"
    ),
    FieldDefinition(
        name="nacionalidad",
        description="Nacionalidad",
        data_type="string",
        example="Chilena"
    ),
    FieldDefinition(
        name="sexo",
        description="Sexo registrado",
        data_type="string",
        required=False,
        example="M"
    ),
    FieldDefinition(
        name="fecha_emision",
        description="Fecha de emisión del documento",
        data_type="string",
        example="2020-01-10"
    ),
    FieldDefinition(
        name="fecha_vencimiento",
        description="Fecha de vencimiento",
        data_type="string",
        required=False,
        example="2030-01-10"
    ),
    FieldDefinition(
        name="numero_documento",
        description="Número de documento",
        data_type="string",
        required=False,
        example="12.345.678"
    ),
    FieldDefinition(
        name="lugar_nacimiento",
        description="Lugar de nacimiento",
        data_type="string",
        required=False,
        example="Santiago"
    )
]

# Cotización AFP - Modelo Custom
AFP_FIELDS = [
    FieldDefinition(
        name="institucion",
        description="Nombre de la AFP",
        data_type="string",
        example="AFP Habitat"
    ),
    FieldDefinition(
        name="rut_afiliado",
        description="RUT del afiliado",
        data_type="string",
        example="12.345.678-9"
    ),
    FieldDefinition(
        name="nombre_afiliado",
        description="Nombre del afiliado",
        data_type="string",
        example="Juan Pérez González"
    ),
    FieldDefinition(
        name="fecha_cotizacion",
        description="Fecha de la cotización",
        data_type="string",
        example="2024-01-15"
    ),
    FieldDefinition(
        name="periodo",
        description="Período de cotización (mes/año)",
        data_type="string",
        example="01/2024"
    ),
    FieldDefinition(
        name="tipo_cotizacion",
        description="Tipo de cotización",
        data_type="string",
        example="Dependiente"
    ),
    FieldDefinition(
        name="monto_cotizacion_obligatoria",
        description="Monto de cotización obligatoria",
        data_type="number",
        example=125000.50
    ),
    FieldDefinition(
        name="monto_cotizacion_voluntaria",
        description="Monto de cotización voluntaria",
        data_type="number",
        required=False,
        example=50000.00
    ),
    FieldDefinition(
        name="monto_total",
        description="Monto total cotizado",
        data_type="number",
        example=175000.50
    ),
    FieldDefinition(
        name="rentabilidad",
        description="Rentabilidad del período",
        data_type="number",
        required=False,
        example=2.5
    ),
    FieldDefinition(
        name="saldo_total",
        description="Saldo total acumulado",
        data_type="number",
        required=False,
        example=15000000.00
    ),
    FieldDefinition(
        name="numero_cuenta",
        description="Número de cuenta AFP",
        data_type="string",
        required=False,
        example="1234567890"
    )
]


# ============================================
# DEFINICIONES COMPLETAS DE DOCUMENTOS
# ============================================

DOCUMENT_TYPE_DEFINITIONS: Dict[DocumentType, DocumentTypeDefinition] = {
    DocumentType.CURRICULUM_VITAE: DocumentTypeDefinition(
        type=DocumentType.CURRICULUM_VITAE,
        name="Curriculum Vitae",
        description="Hoja de vida de candidato a empleo",
        azure_model="prebuilt-resume",
        is_custom_model=False,
        fields=CV_FIELDS,
        supported_extensions=[".pdf"],
        max_pages=5
    ),
    DocumentType.TITULO_UNIVERSITARIO: DocumentTypeDefinition(
        type=DocumentType.TITULO_UNIVERSITARIO,
        name="Título Universitario",
        description="Título universitario o certificado de grado",
        azure_model="custom",
        is_custom_model=True,
        fields=TITULO_FIELDS,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        max_pages=2
    ),
    DocumentType.CONCENTRACION_NOTAS: DocumentTypeDefinition(
        type=DocumentType.CONCENTRACION_NOTAS,
        name="Concentración de Notas",
        description="Certificado de notas o concentración académica",
        azure_model="custom",
        is_custom_model=True,
        fields=NOTAS_FIELDS,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        max_pages=5
    ),
    DocumentType.CEDULA_IDENTIDAD: DocumentTypeDefinition(
        type=DocumentType.CEDULA_IDENTIDAD,
        name="Cédula de Identidad",
        description="Cédula de identidad nacional",
        azure_model="prebuilt-identityDocument",
        is_custom_model=False,
        fields=CEDULA_FIELDS,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        max_pages=2
    ),
    DocumentType.COTIZACION_AFP: DocumentTypeDefinition(
        type=DocumentType.COTIZACION_AFP,
        name="Cotización AFP",
        description="Certificado de cotización previsional",
        azure_model="custom",
        is_custom_model=True,
        fields=AFP_FIELDS,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        max_pages=3
    )
}


def get_document_type_definition(doc_type: DocumentType) -> Optional[DocumentTypeDefinition]:
    """Obtiene la definición de un tipo de documento"""
    return DOCUMENT_TYPE_DEFINITIONS.get(doc_type)


def get_all_document_types() -> List[DocumentTypeDefinition]:
    """Retorna todas las definiciones de tipos de documento"""
    return list(DOCUMENT_TYPE_DEFINITIONS.values())


def get_document_type_from_string(type_str: str) -> Optional[DocumentType]:
    """Convierte un string a DocumentType enum"""
    try:
        return DocumentType(type_str)
    except ValueError:
        return None


def get_expected_fields(doc_type: DocumentType) -> List[FieldDefinition]:
    """Obtiene los campos esperados para un tipo de documento"""
    definition = get_document_type_definition(doc_type)
    return definition.fields if definition else []


def get_field_names(doc_type: DocumentType, include_optional: bool = True) -> List[str]:
    """Obtiene los nombres de campos para un tipo de documento"""
    fields = get_expected_fields(doc_type)
    if include_optional:
        return [f.name for f in fields]
    return [f.name for f in fields if f.required]
