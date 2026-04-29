"""
TableExtractor - Módulo de extração e formatação de tabelas

Responsável por processar tabelas do DOCX, normalizar células mescladas
e converter para formato adequado para Markdown.
"""

import re
from typing import List, Optional
from dataclasses import dataclass

from .docx_reader import TableCell, TableElement


@dataclass
class NormalizedTable:
    """Tabela normalizada (sem células mescladas)."""
    headers: List[str]
    rows: List[List[str]]
    original_row_count: int
    original_col_count: int
    has_merged_cells: bool = False

    @property
    def num_cols(self) -> int:
        return len(self.headers) if self.headers else (len(self.rows[0]) if self.rows else 0)

    @property
    def num_rows(self) -> int:
        return len(self.rows)


class TableExtractor:
    """
    Extrator e normalizador de tabelas.

    Processa tabelas com células mescladas e as normaliza para
    um formato regular adequado para conversão em Markdown.

    Uso:
        extractor = TableExtractor()
        normalized = extractor.normalize(table_element)
        markdown = extractor.to_markdown(normalized)
    """

    def __init__(self):
        """Inicializa o extrator."""
        pass

    def normalize(self, table: TableElement) -> NormalizedTable:
        """
        Normaliza uma tabela, expandindo células mescladas.

        Args:
            table: Tabela do DocxReader

        Returns:
            Tabela normalizada
        """
        if not table.rows:
            return NormalizedTable(
                headers=[],
                rows=[],
                original_row_count=0,
                original_col_count=0
            )

        # Determinar dimensões reais da tabela
        max_cols = max(
            sum(cell.col_span for cell in row)
            for row in table.rows
        )

        # Expandir tabela para grade regular
        expanded = self._expand_merged_cells(table.rows, max_cols)

        # Separar cabeçalho e dados
        headers = []
        data_rows = []
        has_merged = False

        for row_idx, row in enumerate(expanded):
            # Verificar se há células mescladas
            for cell in table.rows[row_idx] if row_idx < len(table.rows) else []:
                if cell.col_span > 1 or cell.is_merged_continuation:
                    has_merged = True

            if row_idx == 0:
                # Primeira linha é cabeçalho
                headers = [cell for cell in row]
            else:
                data_rows.append(row)

        return NormalizedTable(
            headers=headers,
            rows=data_rows,
            original_row_count=len(table.rows),
            original_col_count=max_cols,
            has_merged_cells=has_merged
        )

    def _expand_merged_cells(
        self,
        rows: List[List[TableCell]],
        num_cols: int
    ) -> List[List[str]]:
        """
        Expande células mescladas (colspan e rowspan) para células individuais.

        Args:
            rows: Linhas originais com células
            num_cols: Número total de colunas

        Returns:
            Matriz de strings normalizada
        """
        # Primeiro passo: criar grade expandindo colspan e rastreando merges verticais
        grid = []

        for row in rows:
            expanded_row = []
            col_idx = 0

            for cell in row:
                # Limpar e normalizar texto
                text = self._clean_cell_text(cell.text)

                # Expandir colspan
                for i in range(cell.col_span):
                    expanded_row.append({
                        'text': text if i == 0 else '',
                        'is_merged_continuation': cell.is_merged_continuation
                    })
                    col_idx += 1

            # Preencher colunas faltantes
            while len(expanded_row) < num_cols:
                expanded_row.append({'text': '', 'is_merged_continuation': False})

            grid.append(expanded_row)

        # Segundo passo: fill-down para rowspan (células com is_merged_continuation)
        for row_idx in range(1, len(grid)):
            for col_idx in range(len(grid[row_idx])):
                cell = grid[row_idx][col_idx]
                # Se é continuação de merge vertical e está vazia, propagar valor de cima
                if cell['is_merged_continuation'] and not cell['text']:
                    grid[row_idx][col_idx]['text'] = grid[row_idx - 1][col_idx]['text']

        # Converter para formato final (lista de strings)
        return [[cell['text'] for cell in row] for row in grid]

    def _clean_cell_text(self, text: str) -> str:
        """
        Limpa e normaliza texto de célula.

        Args:
            text: Texto original

        Returns:
            Texto limpo
        """
        if not text:
            return ''

        # Remover quebras de linha internas (substituir por espaço)
        text = re.sub(r'[\r\n]+', ' ', text)

        # Normalizar espaços múltiplos
        text = re.sub(r'\s+', ' ', text)

        # Escapar caracteres especiais do Markdown
        text = text.replace('|', '\\|')

        return text.strip()

    def to_markdown(
        self,
        table: NormalizedTable,
        alignment: Optional[List[str]] = None
    ) -> str:
        """
        Converte tabela normalizada para Markdown.

        Args:
            table: Tabela normalizada
            alignment: Lista de alinhamentos ('left', 'center', 'right')
                      para cada coluna

        Returns:
            String Markdown da tabela
        """
        if not table.headers and not table.rows:
            return ''

        lines = []
        num_cols = table.num_cols

        # Linha de cabeçalho
        if table.headers:
            lines.append(self._format_markdown_row(table.headers, num_cols))
        else:
            # Se não há cabeçalho, criar um vazio
            lines.append(self._format_markdown_row([''] * num_cols, num_cols))

        # Linha separadora
        if alignment:
            separators = []
            for align in alignment[:num_cols]:
                if align == 'center':
                    separators.append(':---:')
                elif align == 'right':
                    separators.append('---:')
                else:  # left ou default
                    separators.append('---')
            while len(separators) < num_cols:
                separators.append('---')
        else:
            # Detectar alinhamento automático
            separators = []
            for i in range(num_cols):
                align = self._detect_column_alignment(table, i)
                if align == 'center':
                    separators.append(':---:')
                elif align == 'right':
                    separators.append('---:')
                else:
                    separators.append('---')

        lines.append('|' + '|'.join(separators) + '|')

        # Linhas de dados
        for row in table.rows:
            lines.append(self._format_markdown_row(row, num_cols))

        return '\n'.join(lines)

    def _format_markdown_row(self, cells: List[str], num_cols: int) -> str:
        """Formata linha de tabela Markdown sem padding visual excessivo."""
        valores = [
            cells[i].strip() if i < len(cells) else ''
            for i in range(num_cols)
        ]
        return '| ' + ' | '.join(valores) + ' |'

    def _detect_column_alignment(self, table: NormalizedTable, col_idx: int) -> str:
        """
        Detecta alinhamento de uma coluna baseado no conteúdo.

        Números são alinhados à direita, texto à esquerda.
        """
        numeric_count = 0
        total_count = 0

        for row in table.rows:
            if col_idx < len(row) and row[col_idx]:
                total_count += 1
                # Verificar se é numérico
                text = row[col_idx].strip()
                if re.match(r'^[\d.,\s\-+]+%?$', text):
                    numeric_count += 1

        # Se mais de 50% são numéricos, alinhar à direita
        if total_count > 0 and numeric_count / total_count > 0.5:
            return 'right'

        return 'left'
