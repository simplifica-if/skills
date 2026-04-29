"""
SectionDetector - Módulo de detecção de seções

Responsável por identificar e classificar seções de documentos PPC,
extraindo estrutura hierárquica e dados relevantes.
"""

import re
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field

from .docx_reader import DocumentElement, ElementType, HeadingElement, ParagraphElement, TableElement


@dataclass
class Section:
    """Representa uma seção do documento."""
    number: Optional[str]  # Ex: "1", "1.1", "5.6"
    title: str
    level: int
    elements: List[DocumentElement] = field(default_factory=list)
    subsections: List['Section'] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        """Retorna título completo com numeração."""
        if self.number:
            return f"{self.number} {self.title}"
        return self.title


# Padrões conhecidos de seções de PPC
PPC_SECTION_PATTERNS = {
    'apresentacao': [
        r'apresenta[çc][ãa]o',
        r'identifica[çc][ãa]o',
        r'dados\s+gerais',
    ],
    'justificativa': [
        r'justificativa',
        r'motiva[çc][ãa]o',
    ],
    'objetivos': [
        r'objetivos?',
        r'objetivo\s+geral',
        r'objetivos?\s+espec[íi]ficos?',
    ],
    'perfil_profissional': [
        r'perfil\s+(profissional|do\s+egresso)',
        r'compet[êe]ncias',
        r'habilidades',
    ],
    'organizacao_curricular': [
        r'organiza[çc][ãa]o\s+curricular',
        r'matriz\s+curricular',
        r'estrutura\s+curricular',
        r'componentes?\s+curriculares?',
        r'ementas?',
    ],
    'metodologia': [
        r'metodologia',
        r'pr[áa]ticas\s+pedag[óo]gicas',
    ],
    'estagio': [
        r'est[áa]gio',
        r'pr[áa]tica\s+profissional',
    ],
    'avaliacao': [
        r'avalia[çc][ãa]o',
        r'crit[ée]rios\s+de\s+avalia[çc][ãa]o',
    ],
    'infraestrutura': [
        r'infraestrutura',
        r'instala[çc][õo]es',
        r'laborat[óo]rios?',
        r'biblioteca',
    ],
    'corpo_docente': [
        r'corpo\s+docente',
        r'professores',
        r'equipe\s+pedag[óo]gica',
    ],
    'referencias': [
        r'refer[êe]ncias',
        r'bibliografia',
    ],
}


class SectionDetector:
    """
    Detector de seções de documentos PPC.

    Analisa elementos do documento e identifica a estrutura de seções,
    classificando-as conforme padrões típicos de PPCs.

    Uso:
        detector = SectionDetector()
        sections = detector.detect(elements)
        for section in sections:
            print(f"{section.number}. {section.title}")
    """

    # Padrão para detectar numeração de seção
    SECTION_NUM_PATTERN = re.compile(
        r'^(\d+(?:\.\d+)*\.?)\s*[-–—.]?\s*(.+)$'
    )

    def __init__(self):
        """Inicializa o detector."""
        self._sections: List[Section] = []
        self._current_path: List[Section] = []

    def detect(self, elements: List[DocumentElement]) -> List[Section]:
        """
        Detecta seções a partir de uma lista de elementos.

        Args:
            elements: Lista de elementos do documento

        Returns:
            Lista de seções de nível 1 (com subsections aninhadas)
        """
        self._sections = []
        self._current_path = []

        for element in elements:
            if element.type == ElementType.HEADING:
                self._process_heading(element)
            else:
                # Adiciona elemento à seção atual
                self._add_to_current_section(element)

        return self._sections

    def _process_heading(self, heading: HeadingElement) -> None:
        """Processa um heading e cria/atualiza seção."""
        # Extrair número e título
        number, title = self._parse_heading_text(heading.text)

        # Determinar nível
        level = heading.level
        if number:
            # Usar contagem de pontos para determinar nível
            level = number.rstrip('.').count('.') + 1

        section = Section(
            number=number,
            title=title,
            level=level
        )

        self._add_section(section)

    def _parse_heading_text(self, text: str) -> Tuple[Optional[str], str]:
        """
        Extrai número e título de um texto de heading.

        Args:
            text: Texto do heading

        Returns:
            Tuple (número, título)
        """
        text = text.strip()
        match = self.SECTION_NUM_PATTERN.match(text)

        if match:
            number = match.group(1).rstrip('.')
            title = match.group(2).strip()
            return number, title

        return None, text

    def _add_section(self, section: Section) -> None:
        """Adiciona uma seção na posição correta da hierarquia."""
        level = section.level

        if level == 1 or not self._current_path:
            # Seção de nível 1: adiciona à raiz
            self._sections.append(section)
            self._current_path = [section]

        else:
            # Subseção: encontra o pai correto
            # Remove seções do path até encontrar um nível menor
            while len(self._current_path) >= level:
                self._current_path.pop()

            if self._current_path:
                # Adiciona como subseção do pai
                parent = self._current_path[-1]
                parent.subsections.append(section)
            else:
                # Fallback: adiciona à raiz
                self._sections.append(section)

            self._current_path.append(section)

    def _add_to_current_section(self, element: DocumentElement) -> None:
        """Adiciona um elemento à seção atual."""
        if self._current_path:
            self._current_path[-1].elements.append(element)
        elif self._sections:
            # Se não há path mas há seções, adiciona à última
            self._sections[-1].elements.append(element)
        # Elementos antes da primeira seção são ignorados ou poderiam
        # ser tratados como preâmbulo

    def classify_section(self, section: Section) -> Optional[str]:
        """
        Classifica uma seção conforme padrões de PPC.

        Args:
            section: Seção a classificar

        Returns:
            Categoria da seção ou None se não identificada
        """
        title_lower = section.title.lower()
        full_title_lower = section.full_title.lower()

        for category, patterns in PPC_SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title_lower) or re.search(pattern, full_title_lower):
                    return category

        return None

    def get_section_list(self, sections: Optional[List[Section]] = None) -> List[str]:
        """
        Retorna lista flat de todas as seções detectadas.

        Args:
            sections: Lista de seções (usa self._sections se None)

        Returns:
            Lista de títulos completos das seções
        """
        if sections is None:
            sections = self._sections

        result = []
        for section in sections:
            result.append(section.full_title)
            if section.subsections:
                result.extend(self.get_section_list(section.subsections))

        return result

    def find_section(
        self,
        category: str,
        sections: Optional[List[Section]] = None
    ) -> Optional[Section]:
        """
        Encontra uma seção por categoria.

        Args:
            category: Categoria a buscar (ex: 'matriz_curricular')
            sections: Lista de seções para buscar

        Returns:
            Seção encontrada ou None
        """
        if sections is None:
            sections = self._sections

        for section in sections:
            if self.classify_section(section) == category:
                return section

            # Buscar em subsections
            found = self.find_section(category, section.subsections)
            if found:
                return found

        return None

    def extract_data_hints(self, sections: List[Section]) -> Dict[str, str]:
        """
        Extrai dicas de dados das seções (para ppc_dados.json).

        Analisa seções de identificação/apresentação para extrair
        informações como nome do curso, modalidade, etc.

        Args:
            sections: Lista de seções do documento

        Returns:
            Dict com dados extraídos
        """
        data = {}

        # Procurar seção de apresentação/identificação
        for section in sections:
            category = self.classify_section(section)

            if category == 'apresentacao':
                # Extrair dados de tabelas ou parágrafos
                data.update(self._extract_from_section(section))

            # Buscar em subsections
            for subsection in section.subsections:
                sub_category = self.classify_section(subsection)
                if sub_category == 'apresentacao':
                    data.update(self._extract_from_section(subsection))

        return data

    def _extract_from_section(self, section: Section) -> Dict[str, str]:
        """Extrai dados de uma seção específica."""
        data = {}

        # Padrões para extração
        patterns = {
            'nome_curso': [
                r'nome\s+do\s+curso[:\s]+(.+)',
                r'curso[:\s]+(.+)',
                r'denomina[çc][ãa]o[:\s]+(.+)',
            ],
            'modalidade': [
                r'modalidade[:\s]+(.+)',
                r'forma\s+de\s+oferta[:\s]+(.+)',
            ],
            'eixo_tecnologico': [
                r'eixo\s+tecnol[óo]gico[:\s]+(.+)',
            ],
            'campus': [
                r'campus[:\s]+(.+)',
                r'unidade[:\s]+(.+)',
            ],
            'carga_horaria_total': [
                r'carga\s+hor[áa]ria\s+total[:\s]+(.+)',
                r'ch\s+total[:\s]+(.+)',
            ],
            'duracao': [
                r'tempo\s+de\s+dura[çc][ãa]o[^:]*[:\s]+(.+)',
                r'tempo\s+de\s+integraliza[çc][ãa]o[:\s]+(.+)',
                r'dura[çc][ãa]o\s+do\s+curso[:\s]+(.+)',
            ],
            'turno': [
                r'turno[:\s]+(.+)',
                r'per[íi]odo[:\s]+(.+)',
            ],
            'vagas': [
                r'vagas[:\s]+(\d+)',
                r'n[úu]mero\s+de\s+vagas[:\s]+(\d+)',
            ],
            'ano_vigencia': [
                r'in[íi]cio\s+(?:da\s+)?(?:nova\s+)?matriz[^:]*[:\s]+(\d{4})',
                r'ano\s+de\s+vig[êe]ncia[:\s]+(\d{4})',
                r'vig[êe]ncia[:\s]+(\d{4})',
            ],
        }

        for element in section.elements:
            if element.type == ElementType.TABLE:
                # Extrair de tabela (campo | valor)
                data.update(self._extract_from_table(element, patterns))

            elif element.type == ElementType.PARAGRAPH:
                # Extrair de parágrafo
                text = element.text
                for field, field_patterns in patterns.items():
                    if field not in data:
                        for pattern in field_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                data[field] = match.group(1).strip()
                                break

        return data

    def _extract_from_table(
        self,
        table: TableElement,
        patterns: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Extrai dados de uma tabela de identificação."""
        data = {}

        for row in table.rows:
            if len(row) >= 2:
                # Formato 2+ colunas: Campo | Valor
                field_text = row[0].text.lower().strip()
                value_text = row[1].text.strip()

                if not value_text:
                    continue

                # Mapear campo para nossos padrões
                for field, field_patterns in patterns.items():
                    if field not in data:
                        for pattern in field_patterns:
                            # Simplificar padrão para match em campo de tabela
                            simple_pattern = pattern.replace(r'[:\s]+(.+)', '').replace(r'[:\s]+', '')
                            if re.search(simple_pattern, field_text, re.IGNORECASE):
                                data[field] = value_text
                                break

            elif len(row) == 1:
                # Formato 1 coluna com "Campo: Valor" inline
                cell_text = row[0].text.strip()
                for field, field_patterns in patterns.items():
                    if field not in data:
                        for pattern in field_patterns:
                            match = re.search(pattern, cell_text, re.IGNORECASE)
                            if match:
                                data[field] = match.group(1).strip()
                                break

        return data
