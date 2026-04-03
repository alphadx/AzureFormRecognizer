"""
Mapeo de respuesta Azure Form Recognizer a JSON limpio y estructurado
"""

import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from app.models.document_types import DocumentType, get_expected_fields, FieldDefinition
from app.utils.logger import LoggerMixin, get_correlation_id


class FieldMapper(LoggerMixin):
    """Mapea campos individuales de Azure"""
    
    @staticmethod
    def extract_value(field_data: Any) -> Any:
        """Extrae el valor de un campo de Azure"""
        if field_data is None:
            return None
        
        # Si es un objeto de campo de Azure
        if hasattr(field_data, 'value'):
            return field_data.value
        
        # Si es un diccionario
        if isinstance(field_data, dict):
            return field_data.get('value') or field_data.get('content')
        
        # Valor directo
        return field_data
    
    @staticmethod
    def extract_confidence(field_data: Any) -> float:
        """Extrae el confidence score de un campo"""
        if field_data is None:
            return 0.0
        
        if hasattr(field_data, 'confidence'):
            return field_data.confidence or 0.0
        
        if isinstance(field_data, dict):
            return field_data.get('confidence', 0.0)
        
        return 0.0
    
    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """Limpia y normaliza texto"""
        if text is None:
            return None
        
        # Convertir a string si no lo es
        text = str(text)
        
        # Eliminar espacios extras
        text = ' '.join(text.split())
        
        # Eliminar caracteres de control
        text = ''.join(char for char in text if char.isprintable() or char.isspace())
        
        return text.strip() if text.strip() else None
    
    @staticmethod
    def parse_phone(phone: Optional[str]) -> Optional[str]:
        """Normaliza número de teléfono"""
        if not phone:
            return None
        
        # Eliminar espacios y caracteres no numéricos excepto + y -
        cleaned = re.sub(r'[^\d\+\-]', '', str(phone))
        
        # Asegurar formato chileno básico
        if cleaned.startswith('9') and len(cleaned) == 9:
            return f"+56{cleaned}"
        
        if cleaned.startswith('569') and len(cleaned) == 11:
            return f"+{cleaned}"
        
        if cleaned.startswith('+569') and len(cleaned) == 12:
            return cleaned
        
        return cleaned if cleaned else None
    
    @staticmethod
    def parse_email(email: Optional[str]) -> Optional[str]:
        """Valida y normaliza email"""
        if not email:
            return None
        
        email = str(email).strip().lower()
        
        # Validación básica de email
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return email
        
        return None
    
    @staticmethod
    def parse_rut(rut: Optional[str]) -> Optional[str]:
        """Normaliza RUT chileno"""
        if not rut:
            return None
        
        # Eliminar puntos y espacios, mantener guión
        cleaned = str(rut).upper().replace('.', '').replace(' ', '')
        
        # Validar formato básico
        if re.match(r'^\d{7,8}-[\dK]$', cleaned):
            return cleaned
        
        # Intentar formatear
        digits = re.sub(r'[^\d]', '', cleaned)
        verifier = re.sub(r'[^\dK]', '', cleaned[-1:]) if cleaned else ''
        
        if len(digits) >= 7 and verifier:
            return f"{digits}-{verifier}"
        
        return cleaned if cleaned else None
    
    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[str]:
        """Normaliza fecha a formato ISO (YYYY-MM-DD)"""
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Formatos comunes
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%m/%d/%Y',
            '%Y/%m/%d',
            '%d/%m/%y',
            '%B %Y',
            '%b %Y',
            '%Y'
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Si no se pudo parsear, retornar el string original
        return date_str if date_str else None
    
    @staticmethod
    def parse_number(value: Any) -> Optional[float]:
        """Parsea un valor numérico"""
        if value is None:
            return None
        
        try:
            # Eliminar separadores de miles y convertir
            if isinstance(value, str):
                # Manejar formatos: 1.234,56 (Chile) o 1,234.56 (USA)
                value = value.replace('$', '').replace('%', '').strip()
                
                if ',' in value and '.' in value:
                    # Determinar cuál es el separador decimal
                    last_comma = value.rfind(',')
                    last_dot = value.rfind('.')
                    
                    if last_comma > last_dot:
                        # Formato europeo: 1.234,56
                        value = value.replace('.', '').replace(',', '.')
                    else:
                        # Formato USA: 1,234.56
                        value = value.replace(',', '')
                elif ',' in value:
                    # Podría ser decimal europeo o separador de miles
                    if len(value.split(',')[-1]) <= 2:
                        value = value.replace(',', '.')
                    else:
                        value = value.replace(',', '')
            
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def parse_list(value: Any, separator: str = ',') -> List[str]:
        """Parsea una lista de valores"""
        if value is None:
            return []
        
        if isinstance(value, list):
            return [str(v).strip() for v in value if v]
        
        if isinstance(value, str):
            items = value.split(separator)
            return [item.strip() for item in items if item.strip()]
        
        return [str(value)] if value else []


class BaseModelMapper(LoggerMixin):
    """Mapper base para todos los tipos de documento"""
    
    def __init__(self, document_type: DocumentType):
        super().__init__()
        self.document_type = document_type
        self.field_mapper = FieldMapper()
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapea los datos de Azure a formato limpio
        
        Args:
            azure_data: Datos extraídos por Azure
            
        Returns:
            Diccionario con datos mapeados
        """
        raise NotImplementedError("Subclasses must implement map()")
    
    def _extract_field(self, data: Dict[str, Any], field_name: str, 
                       cleaner: Optional[Callable] = None) -> Any:
        """Extrae y limpia un campo"""
        value = data.get(field_name)
        extracted = self.field_mapper.extract_value(value)
        
        if cleaner and extracted is not None:
            extracted = cleaner(extracted)
        
        return extracted


class CurriculumVitaeMapper(BaseModelMapper):
    """Mapper para Curriculum Vitae"""
    
    def __init__(self):
        super().__init__(DocumentType.CURRICULUM_VITAE)
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea datos de CV"""
        fm = self.field_mapper
        
        # Experiencia laboral
        experiencia_raw = azure_data.get('WorkExperience', []) or azure_data.get('experiencia_laboral', [])
        experiencia = self._map_experiencia(experiencia_raw)
        
        # Educación
        educacion_raw = azure_data.get('Education', []) or azure_data.get('educacion', [])
        educacion = self._map_educacion(educacion_raw)
        
        # Habilidades
        skills_raw = azure_data.get('Skills', []) or azure_data.get('habilidades', [])
        habilidades = []
        if isinstance(skills_raw, list):
            for skill in skills_raw:
                val = fm.extract_value(skill)
                if val:
                    habilidades.extend(fm.parse_list(val))
        elif isinstance(skills_raw, str):
            habilidades = fm.parse_list(skills_raw)
        
        return {
            'nombre': fm.clean_text(self._extract_field(azure_data, 'Name') or 
                                   self._extract_field(azure_data, 'nombre')),
            'email': fm.parse_email(self._extract_field(azure_data, 'Email') or 
                                   self._extract_field(azure_data, 'email')),
            'telefono': fm.parse_phone(self._extract_field(azure_data, 'Phone') or 
                                      self._extract_field(azure_data, 'telefono')),
            'direccion': fm.clean_text(self._extract_field(azure_data, 'Address') or 
                                      self._extract_field(azure_data, 'direccion')),
            'experiencia_laboral': experiencia,
            'educacion': educacion,
            'habilidades': list(set(habilidades))  # Eliminar duplicados
        }
    
    def _map_experiencia(self, experiencia_raw: List[Any]) -> List[Dict[str, Any]]:
        """Mapea experiencia laboral"""
        fm = self.field_mapper
        experiencias = []
        
        for exp in experiencia_raw:
            if not exp:
                continue
            
            # Si es un objeto de Azure
            if hasattr(exp, 'value_object'):
                exp_data = exp.value_object
            elif isinstance(exp, dict):
                exp_data = exp
            else:
                continue
            
            experiencias.append({
                'empresa': fm.clean_text(fm.extract_value(exp_data.get('Employer') or 
                                                          exp_data.get('empresa'))),
                'cargo': fm.clean_text(fm.extract_value(exp_data.get('JobTitle') or 
                                                        exp_data.get('cargo'))),
                'fecha_inicio': fm.parse_date(fm.extract_value(exp_data.get('StartDate') or 
                                                               exp_data.get('fecha_inicio'))),
                'fecha_fin': fm.parse_date(fm.extract_value(exp_data.get('EndDate') or 
                                                            exp_data.get('fecha_fin'))),
                'descripcion': fm.clean_text(fm.extract_value(exp_data.get('Description') or 
                                                             exp_data.get('descripcion')))
            })
        
        return experiencias
    
    def _map_educacion(self, educacion_raw: List[Any]) -> List[Dict[str, Any]]:
        """Mapea educación"""
        fm = self.field_mapper
        educaciones = []
        
        for edu in educacion_raw:
            if not edu:
                continue
            
            if hasattr(edu, 'value_object'):
                edu_data = edu.value_object
            elif isinstance(edu, dict):
                edu_data = edu
            else:
                continue
            
            educaciones.append({
                'institucion': fm.clean_text(fm.extract_value(edu_data.get('School') or 
                                                              edu_data.get('institucion'))),
                'carrera': fm.clean_text(fm.extract_value(edu_data.get('Degree') or 
                                                          edu_data.get('carrera'))),
                'grado': fm.clean_text(fm.extract_value(edu_data.get('Degree') or 
                                                        edu_data.get('grado'))),
                'fecha_inicio': fm.parse_date(fm.extract_value(edu_data.get('StartDate') or 
                                                               edu_data.get('fecha_inicio'))),
                'fecha_fin': fm.parse_date(fm.extract_value(edu_data.get('EndDate') or 
                                                            edu_data.get('fecha_fin')))
            })
        
        return educaciones


class TituloUniversitarioMapper(BaseModelMapper):
    """Mapper para Título Universitario"""
    
    def __init__(self):
        super().__init__(DocumentType.TITULO_UNIVERSITARIO)
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea datos de título universitario"""
        fm = self.field_mapper
        
        return {
            'institucion': fm.clean_text(self._extract_field(azure_data, 'institucion') or 
                                        self._extract_field(azure_data, 'Institucion')),
            'carrera': fm.clean_text(self._extract_field(azure_data, 'carrera') or 
                                    self._extract_field(azure_data, 'Carrera')),
            'nombre_titular': fm.clean_text(self._extract_field(azure_data, 'nombre_titular') or 
                                           self._extract_field(azure_data, 'Nombre')),
            'rut_titular': fm.parse_rut(self._extract_field(azure_data, 'rut_titular') or 
                                       self._extract_field(azure_data, 'RUT')),
            'fecha_emision': fm.parse_date(self._extract_field(azure_data, 'fecha_emision') or 
                                          self._extract_field(azure_data, 'FechaEmision')),
            'numero_titulo': fm.clean_text(self._extract_field(azure_data, 'numero_titulo') or 
                                          self._extract_field(azure_data, 'NumeroTitulo')),
            'grado_academico': fm.clean_text(self._extract_field(azure_data, 'grado_academico')),
            'duracion_anios': int(fm.parse_number(self._extract_field(azure_data, 'duracion_anios')) or 0) or None
        }


class ConcentracionNotasMapper(BaseModelMapper):
    """Mapper para Concentración de Notas"""
    
    def __init__(self):
        super().__init__(DocumentType.CONCENTRACION_NOTAS)
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea datos de concentración de notas"""
        fm = self.field_mapper
        
        # Asignaturas
        asignaturas_raw = azure_data.get('asignaturas', []) or azure_data.get('Asignaturas', [])
        asignaturas = self._map_asignaturas(asignaturas_raw)
        
        return {
            'institucion': fm.clean_text(self._extract_field(azure_data, 'institucion')),
            'carrera': fm.clean_text(self._extract_field(azure_data, 'carrera')),
            'nombre_estudiante': fm.clean_text(self._extract_field(azure_data, 'nombre_estudiante') or 
                                              self._extract_field(azure_data, 'Nombre')),
            'rut_estudiante': fm.parse_rut(self._extract_field(azure_data, 'rut_estudiante') or 
                                          self._extract_field(azure_data, 'RUT')),
            'fecha_emision': fm.parse_date(self._extract_field(azure_data, 'fecha_emision')),
            'periodo_academico': fm.clean_text(self._extract_field(azure_data, 'periodo_academico')),
            'asignaturas': asignaturas,
            'promedio_ponderado': fm.parse_number(self._extract_field(azure_data, 'promedio_ponderado')),
            'promedio_semestral': fm.parse_number(self._extract_field(azure_data, 'promedio_semestral')),
            'total_creditos': int(fm.parse_number(self._extract_field(azure_data, 'total_creditos')) or 0) or None,
            'total_asignaturas': len(asignaturas) if asignaturas else None
        }
    
    def _map_asignaturas(self, asignaturas_raw: List[Any]) -> List[Dict[str, Any]]:
        """Mapea lista de asignaturas"""
        fm = self.field_mapper
        asignaturas = []
        
        for asig in asignaturas_raw:
            if not asig:
                continue
            
            if hasattr(asig, 'value_object'):
                asig_data = asig.value_object
            elif isinstance(asig, dict):
                asig_data = asig
            else:
                continue
            
            nota = fm.parse_number(fm.extract_value(asig_data.get('nota') or asig_data.get('Nota')))
            
            asignaturas.append({
                'codigo': fm.clean_text(fm.extract_value(asig_data.get('codigo') or asig_data.get('Codigo'))),
                'nombre': fm.clean_text(fm.extract_value(asig_data.get('nombre') or asig_data.get('Nombre'))),
                'nota': nota,
                'creditos': int(fm.parse_number(fm.extract_value(asig_data.get('creditos') or asig_data.get('Creditos'))) or 0) or None,
                'estado': 'Aprobado' if nota and nota >= 4.0 else 'Reprobado' if nota else None
            })
        
        return asignaturas


class CedulaIdentidadMapper(BaseModelMapper):
    """Mapper para Cédula de Identidad"""
    
    def __init__(self):
        super().__init__(DocumentType.CEDULA_IDENTIDAD)
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea datos de cédula de identidad"""
        fm = self.field_mapper
        
        return {
            'nombre': fm.clean_text(self._extract_field(azure_data, 'FirstName') or 
                                   self._extract_field(azure_data, 'nombre')),
            'apellidos': fm.clean_text(self._extract_field(azure_data, 'LastName') or 
                                      self._extract_field(azure_data, 'apellidos')),
            'rut': fm.parse_rut(self._extract_field(azure_data, 'DocumentNumber') or 
                               self._extract_field(azure_data, 'rut')),
            'fecha_nacimiento': fm.parse_date(self._extract_field(azure_data, 'DateOfBirth') or 
                                             self._extract_field(azure_data, 'fecha_nacimiento')),
            'nacionalidad': fm.clean_text(self._extract_field(azure_data, 'Nationality') or 
                                         self._extract_field(azure_data, 'nacionalidad')),
            'sexo': fm.clean_text(self._extract_field(azure_data, 'Sex') or 
                                 self._extract_field(azure_data, 'sexo')),
            'fecha_emision': fm.parse_date(self._extract_field(azure_data, 'DateOfIssue') or 
                                          self._extract_field(azure_data, 'fecha_emision')),
            'fecha_vencimiento': fm.parse_date(self._extract_field(azure_data, 'DateOfExpiration') or 
                                              self._extract_field(azure_data, 'fecha_vencimiento')),
            'numero_documento': fm.clean_text(self._extract_field(azure_data, 'DocumentNumber')),
            'lugar_nacimiento': fm.clean_text(self._extract_field(azure_data, 'PlaceOfBirth') or 
                                             self._extract_field(azure_data, 'lugar_nacimiento'))
        }


class CotizacionAFPMapper(BaseModelMapper):
    """Mapper para Cotización AFP"""
    
    def __init__(self):
        super().__init__(DocumentType.COTIZACION_AFP)
    
    def map(self, azure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapea datos de cotización AFP"""
        fm = self.field_mapper
        
        monto_obligatoria = fm.parse_number(self._extract_field(azure_data, 'monto_cotizacion_obligatoria'))
        monto_voluntaria = fm.parse_number(self._extract_field(azure_data, 'monto_cotizacion_voluntaria'))
        monto_total = fm.parse_number(self._extract_field(azure_data, 'monto_total'))
        
        # Calcular monto total si no está explícito
        if monto_total is None and (monto_obligatoria or monto_voluntaria):
            monto_total = (monto_obligatoria or 0) + (monto_voluntaria or 0)
        
        return {
            'institucion': fm.clean_text(self._extract_field(azure_data, 'institucion') or 
                                        self._extract_field(azure_data, 'AFP')),
            'rut_afiliado': fm.parse_rut(self._extract_field(azure_data, 'rut_afiliado') or 
                                        self._extract_field(azure_data, 'RUT')),
            'nombre_afiliado': fm.clean_text(self._extract_field(azure_data, 'nombre_afiliado') or 
                                            self._extract_field(azure_data, 'Nombre')),
            'fecha_cotizacion': fm.parse_date(self._extract_field(azure_data, 'fecha_cotizacion') or 
                                             self._extract_field(azure_data, 'Fecha')),
            'periodo': fm.clean_text(self._extract_field(azure_data, 'periodo') or 
                                    self._extract_field(azure_data, 'Periodo')),
            'tipo_cotizacion': fm.clean_text(self._extract_field(azure_data, 'tipo_cotizacion')),
            'monto_cotizacion_obligatoria': monto_obligatoria,
            'monto_cotizacion_voluntaria': monto_voluntaria,
            'monto_total': monto_total,
            'rentabilidad': fm.parse_number(self._extract_field(azure_data, 'rentabilidad')),
            'saldo_total': fm.parse_number(self._extract_field(azure_data, 'saldo_total')),
            'numero_cuenta': fm.clean_text(self._extract_field(azure_data, 'numero_cuenta'))
        }


class ModelMapperFactory:
    """Factory para obtener el mapper correcto según tipo de documento"""
    
    _mappers = {
        DocumentType.CURRICULUM_VITAE: CurriculumVitaeMapper,
        DocumentType.TITULO_UNIVERSITARIO: TituloUniversitarioMapper,
        DocumentType.CONCENTRACION_NOTAS: ConcentracionNotasMapper,
        DocumentType.CEDULA_IDENTIDAD: CedulaIdentidadMapper,
        DocumentType.COTIZACION_AFP: CotizacionAFPMapper
    }
    
    @classmethod
    def get_mapper(cls, document_type: DocumentType) -> BaseModelMapper:
        """
        Obtiene el mapper para un tipo de documento
        
        Args:
            document_type: Tipo de documento
            
        Returns:
            Instancia del mapper correspondiente
        """
        mapper_class = cls._mappers.get(document_type)
        
        if not mapper_class:
            raise ValueError(f"No mapper found for document type: {document_type}")
        
        return mapper_class()
    
    @classmethod
    def register_mapper(cls, document_type: DocumentType, mapper_class: type):
        """Registra un nuevo mapper (para extensibilidad)"""
        cls._mappers[document_type] = mapper_class
    
    @classmethod
    def list_mappers(cls) -> Dict[str, str]:
        """Lista los mappers registrados"""
        return {
            doc_type.value: mapper_class.__name__
            for doc_type, mapper_class in cls._mappers.items()
        }


def map_azure_response(
    document_type: DocumentType,
    azure_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Función helper para mapear respuesta de Azure
    
    Args:
        document_type: Tipo de documento
        azure_data: Datos extraídos por Azure
        
    Returns:
        Datos mapeados y limpios
    """
    mapper = ModelMapperFactory.get_mapper(document_type)
    return mapper.map(azure_data)
