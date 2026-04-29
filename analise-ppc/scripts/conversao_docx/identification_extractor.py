"""
IdentificationExtractor - Extração de tabelas campo|valor

Responsável por processar tabelas de identificação com duas colunas
(campo | valor) e extrair dados estruturados.
"""

import re
import unicodedata
from typing import Dict

from .table_extractor import NormalizedTable


class IdentificationExtractor:
    """
    Extrator de tabelas de identificação (2 colunas: campo|valor).

    Processa tabelas com estrutura de par chave-valor e normaliza
    os nomes dos campos para uso como chaves de dicionário.

    Uso:
        extractor = IdentificationExtractor()
        data = extractor.extract_identification_data(normalized_table)
    """

    def __init__(self):
        """Inicializa o extrator de identificação."""
        pass

    # Padrões para extração de dados em formato "Campo: Valor"
    INLINE_PATTERNS = {
        'nome_curso': [
            r'nome\s+do\s+curso[:\s]+(.+)',
            r'denomina[çc][ãa]o[:\s]+(.+)',
        ],
        'forma_oferta': [
            r'forma\s+de\s+oferta[:\s]+(.+)',
        ],
        'modalidade_ensino': [
            r'modalidade[:\s]+(.+)',
        ],
        'eixo_tecnologico': [
            r'eixo\s+tecnol[óo]gico[:\s]+(.+)',
        ],
        'campus': [
            r'campus[:\s]+(.+)',
            r'unidade[:\s]+(.+)',
        ],
        'carga_horaria_total': [
            r'carga[\s-]hor[áa]ria\s+total[^:]*[:\s]+(.+)',
            r'ch\s+total[:\s]+(.+)',
        ],
        'duracao': [
            r'tempo\s+de\s+dura[çc][ãa]o[^:]*[:\s]+(.+)',
            r'tempo\s+de\s+integraliza[çc][ãa]o[:\s]+(.+)',
            r'dura[çc][ãa]o\s+do\s+curso[:\s]+(.+)',
        ],
        'turno': [
            r'turno[^:]*[:\s]+(.+)',
        ],
        'vagas': [
            r'total\s+de\s+vagas[^:]*[:\s]+(.+)',
            r'vagas[:\s]+(\d+)',
            r'n[úu]mero\s+de\s+vagas[:\s]+(\d+)',
        ],
        'horario_oferta': [
            r'hor[áa]rio\s+de\s+oferta[^:]*[:\s]+(.+)',
        ],
        'tipo_matricula': [
            r'tipo\s+de\s+matr[íi]cula[:\s]+(.+)',
        ],
        'periodicidade': [
            r'periodicidade[:\s]+(.+)',
        ],
        'etapas_regime_avaliacao': [
            r'etapas/regime\s+de\s+avalia[çc][ãa]o[:\s]+(.+)',
        ],
        'regime_oferta': [
            r'regime\s+de\s+oferta[:\s]+(.+)',
        ],
        'carga_horaria_estagio': [
            r'carga\s+hor[áa]ria\s+de\s+est[áa]gio[^:]*[:\s]+(.+)',
        ],
        'ano_vigencia': [
            r'in[íi]cio\s+(?:da\s+)?(?:nova\s+)?matriz[^:]*[:\s]+(\d{4})',
            r'ano\s+de\s+vig[êe]ncia[:\s]+(\d{4})',
            r'vig[êe]ncia[:\s]+(\d{4})',
        ],
    }

    def extract_identification_data(self, table: NormalizedTable) -> Dict[str, str]:
        """
        Extrai dados de uma tabela de identificação.

        Suporta dois formatos:
        - 2 colunas: campo | valor
        - 1 coluna: "Campo: Valor" inline

        Args:
            table: Tabela normalizada

        Returns:
            Dict com pares campo-valor
        """
        data = {}

        # Processar cada linha
        all_rows = [table.headers] + table.rows if table.headers else table.rows

        for row in all_rows:
            if len(row) >= 2:
                # Formato 2+ colunas: Campo | Valor
                field = row[0].strip()
                value = row[1].strip()

                if field and value:
                    self._extract_inline_values(field, data)
                    self._extract_inline_values(value, data)

                    # Normalizar nome do campo
                    field_normalized = self._normalize_field_name(field)
                    data[field_normalized] = value

            elif len(row) == 1:
                # Formato 1 coluna com "Campo: Valor" inline
                cell_text = row[0].strip()
                self._extract_inline_values(cell_text, data)

        return data

    def _extract_inline_values(self, text: str, data: Dict[str, str]) -> None:
        """Extrai pares canônicos quando a célula contém texto "Campo: Valor"."""
        for field, patterns in self.INLINE_PATTERNS.items():
            if field in data:
                continue
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data[field] = match.group(1).strip()
                    break

    def _normalize_field_name(self, field: str) -> str:
        """
        Normaliza nome de campo para chave de dicionário.

        Args:
            field: Nome original do campo

        Returns:
            Nome normalizado em snake_case, sem acentos
        """
        # Remover acentos
        field = unicodedata.normalize('NFD', field)
        field = ''.join(c for c in field if unicodedata.category(c) != 'Mn')

        # Converter para snake_case
        field = field.lower()
        field = re.sub(r'[^\w\s]', '', field)
        field = re.sub(r'\s+', '_', field)

        return field
