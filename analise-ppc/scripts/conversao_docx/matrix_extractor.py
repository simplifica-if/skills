"""
MatrixExtractor - Extração de matrizes curriculares

Responsável por processar e extrair dados estruturados de tabelas
que representam matrizes curriculares em PPCs.
"""

import re
from typing import Dict, Optional, List

from .table_extractor import NormalizedTable


class MatrixExtractor:
    """
    Extrator de matrizes curriculares de PPCs.

    Processa tabelas de matriz curricular e extrai dados estruturados
    como componentes, cargas horárias e distribuição por ano/período.

    Uso:
        extractor = MatrixExtractor()
        matrix_data = extractor.extract_matrix_data(normalized_table)
        ppc_matrix = extractor.extract_ppc_matrix_data(normalized_table)
    """

    def __init__(self):
        """Inicializa o extrator de matrizes."""
        pass

    def extract_matrix_data(self, table: NormalizedTable) -> Optional[Dict]:
        """
        Extrai dados estruturados de uma matriz curricular.

        Identifica padrões típicos de matrizes curriculares de PPCs.

        Args:
            table: Tabela normalizada

        Returns:
            Dict com dados estruturados ou None se não for matriz
        """
        if not table.headers or not table.rows:
            return None

        # Detectar se é matriz curricular
        # Procurar por padrões típicos nos cabeçalhos
        headers_lower = [h.lower() for h in table.headers]

        is_matrix = any(
            pattern in ' '.join(headers_lower)
            for pattern in ['componente', 'disciplina', 'ano', 'semestre', 'período', 'carga']
        )

        if not is_matrix:
            return None

        # Identificar colunas
        componente_col = None
        ch_cols = []
        total_col = None

        for i, header in enumerate(headers_lower):
            if any(p in header for p in ['componente', 'disciplina', 'unidade']):
                componente_col = i
            elif any(p in header for p in ['ano', 'semestre', 'período', 'série']):
                ch_cols.append(i)
            elif 'total' in header or 'ch total' in header:
                total_col = i
            elif any(p in header for p in ['carga', 'ch', 'h/']):
                ch_cols.append(i)

        if componente_col is None:
            return None

        # Extrair dados
        componentes = []
        for row in table.rows:
            if componente_col < len(row) and row[componente_col].strip():
                componente = {
                    'nome': row[componente_col].strip(),
                    'cargas': {}
                }

                for ch_col in ch_cols:
                    if ch_col < len(row) and row[ch_col].strip():
                        header = table.headers[ch_col]
                        value = row[ch_col].strip()
                        # Tentar converter para número
                        try:
                            value = int(re.sub(r'[^\d]', '', value))
                        except ValueError:
                            pass
                        componente['cargas'][header] = value

                if total_col and total_col < len(row) and row[total_col].strip():
                    try:
                        componente['total'] = int(re.sub(r'[^\d]', '', row[total_col]))
                    except ValueError:
                        componente['total'] = row[total_col].strip()

                componentes.append(componente)

        return {
            'tipo': 'matriz_curricular',
            'headers': table.headers,
            'componentes': componentes,
            'total_rows': len(componentes)
        }

    def extract_ppc_matrix_data(self, table: NormalizedTable) -> Optional[Dict]:
        """
        Extrai dados de matriz curricular de PPC do IFPR.

        Estrutura esperada:
        - Linha com "CH em Hora-aula (min)" e valor (ex: 50)
        - Linha com "Semanas do ano letivo" e valor (ex: 40)
        - Colunas: Ano/Período | Componente | N° aulas | CH total | CH teórica | CH prática | Total CNCT
        - Linhas: componentes agrupados por ano (1º Ano, 2º Ano, 3º Ano)

        Args:
            table: Tabela normalizada

        Returns:
            Dict com dados estruturados ou None se não for matriz PPC
        """
        if not table.rows or len(table.rows) < 3:
            return None

        # Juntar headers e rows para análise completa
        all_rows = [table.headers] + table.rows if table.headers else table.rows

        # Detectar se é matriz curricular de carga horária
        # DEVE ter colunas de carga horária numérica (não é ementário)
        all_text = ' '.join(
            ' '.join(str(cell).lower() for cell in row)
            for row in all_rows[:10]  # Primeiras 10 linhas
        )

        # Critérios OBRIGATÓRIOS para ser matriz de CH (não ementário):
        # 1. Deve ter padrões de carga horária (inclui versões com e sem acento)
        has_ch_columns = any(pattern in all_text for pattern in [
            'ch total',
            'hora-aula',
            'hora aula',
            'aulas semanais',
            'número de aulas',
            'numero de aulas',
            'hora-relógio',
            'hora-relogio',
            'hora relogio'
        ])

        # 2. Deve ter padrão numérico de carga horária (40, 50, 60, 80, 100, 120, etc)
        has_numeric_ch = bool(re.search(r'\b(40|50|60|80|100|120|160)\b', all_text))

        # 3. NÃO deve ser tabela de ementário (que tem ementa, bibliografia)
        is_ementario = any(pattern in all_text for pattern in [
            'ementa:',
            'bibliografia',
            'básica:',
            'basica:',
            'complementar:'
        ])

        # 4. Verificar se há anos na primeira coluna
        has_year_pattern = any(
            re.search(r'[1234]º?\s*ano', str(row[0]).lower())
            for row in all_rows if row
        )

        # Para ser matriz de CH: deve ter colunas de CH + numéricos + anos + NÃO ser ementário
        if is_ementario:
            return None

        if not (has_ch_columns and has_numeric_ch and has_year_pattern):
            return None

        # Extrair metadados (minutos por hora-aula, semanas)
        minutos_hora_aula = 50  # Valor padrão
        semanas_ano_letivo = 40  # Valor padrão

        # Procurar nas primeiras 10 linhas (metadados podem estar após cabeçalho institucional)
        for row in all_rows[:10]:
            row_text = ' '.join(str(cell).lower() for cell in row)
            # Buscar linha com "CH em Hora-aula (min)" - padrão específico do IFPR
            # DEVE conter indicador de minutos: "(min)" ou "minutos" ou "min"
            # para não confundir com colunas "CH total em hora aula"
            is_minutos_row = (
                ('hora-aula' in row_text or 'hora aula' in row_text) and
                ('(min)' in row_text or 'minutos' in row_text or
                 ('min' in row_text and 'período' not in row_text and 'total' not in row_text))
            )
            if is_minutos_row:
                for cell in row:
                    try:
                        val = int(re.sub(r'[^\d]', '', str(cell)))
                        if 40 <= val <= 60:  # Valores típicos de minutos
                            minutos_hora_aula = val
                            break
                    except (ValueError, TypeError):
                        continue
            if 'semanas' in row_text and 'ano letivo' in row_text:
                for cell in row:
                    try:
                        val = int(re.sub(r'[^\d]', '', str(cell)))
                        if 30 <= val <= 50:  # Valores típicos de semanas
                            semanas_ano_letivo = val
                            break
                    except (ValueError, TypeError):
                        continue

        # Encontrar linha de cabeçalho das colunas (com padrões de CH)
        header_row_idx = None
        col_mapping = {}

        for idx, row in enumerate(all_rows):
            row_lower = [str(cell).lower() for cell in row]
            row_text = ' '.join(row_lower)

            # Procurar linha que contenha padrões de cabeçalho de matriz
            # Include both accented and non-accented versions for encoding safety
            has_ch_header = any(kw in row_text for kw in [
                'número de aulas',
                'numero de aulas',
                'aulas semanais',
                'ch total',
                'hora-relógio',
                'hora-relogio',
                'hora relogio'
            ])

            if has_ch_header:
                header_row_idx = idx
                # Mapear colunas
                for col_idx, cell in enumerate(row_lower):
                    if any(kw in cell for kw in ['componente', 'disciplina', 'unidade curricular']):
                        col_mapping['componente'] = col_idx
                    elif 'número de aulas' in cell or 'numero de aulas' in cell or 'aulas semanais' in cell or 'n°' in cell or 'nº' in cell:
                        col_mapping['aulas_semanais'] = col_idx
                    elif ('teórica' in cell or 'teorica' in cell) and ('ch' in cell or 'hora' in cell):
                        col_mapping['ch_teorica'] = col_idx
                    elif ('prática' in cell or 'pratica' in cell) and ('ch' in cell or 'hora' in cell):
                        col_mapping['ch_pratica'] = col_idx
                    elif 'cnct' in cell:
                        col_mapping['ch_cnct'] = col_idx
                    elif ('ch' in cell or 'carga' in cell) and 'total' in cell:
                        # Check this BEFORE the generic "período" check
                        col_mapping['ch_total'] = col_idx
                    elif ('hora-aula' in cell or 'hora aula' in cell) and ('período' in cell or 'periodo' in cell):
                        col_mapping['ch_total'] = col_idx
                    elif ('hora-relógio' in cell or 'hora-relogio' in cell or 'hora relogio' in cell) and ('período' in cell or 'periodo' in cell):
                        col_mapping['ch_cnct'] = col_idx
                    elif 'semanas' in cell and 'ano' in cell:
                        # Esta é a coluna de metadados (Semanas do ano letivo), não de período/ano
                        pass
                    elif 'ano' in cell and 'período' not in cell and 'periodo' not in cell:
                        # "ano" standalone (like "1º Ano"), not "período letivo" context
                        col_mapping['ano'] = col_idx
                    elif ('período' in cell or 'periodo' in cell or 'série' in cell or 'serie' in cell) and 'letivo' not in cell and 'hora' not in cell:
                        # "período" or "série" as column header, but not "período letivo" context
                        col_mapping['ano'] = col_idx
                break

        # Se não encontrou cabeçalho por padrões de CH, tentar por estrutura
        if header_row_idx is None:
            # Para matrizes sem cabeçalho explícito, usar posição padrão
            # baseada na estrutura típica: Ano | Componente | Aulas | CH total | Teórica | Prática | CNCT
            if table.num_cols >= 4:
                header_row_idx = 0
                col_mapping = {
                    'ano': 0,
                    'componente': 1,
                    'aulas_semanais': 2,
                    'ch_total': 3
                }
                if table.num_cols >= 5:
                    col_mapping['ch_teorica'] = 4
                if table.num_cols >= 6:
                    col_mapping['ch_pratica'] = 5
                if table.num_cols >= 7:
                    col_mapping['ch_cnct'] = 6

        if header_row_idx is None:
            return None

        # Se não mapeou ano/componente, tentar posições padrão
        if 'ano' not in col_mapping:
            col_mapping['ano'] = 0
        if 'componente' not in col_mapping:
            col_mapping['componente'] = 1

        # Ajuste para matrizes que possuem coluna de sequência antes do nome do componente.
        sample_rows = [row for row in all_rows[header_row_idx + 1:] if row and any(str(cell).strip() for cell in row)][:10]
        comp_idx = col_mapping.get('componente', 1)
        next_idx = comp_idx + 1
        if sample_rows and next_idx < max(len(row) for row in sample_rows):
            comp_numeric = 0
            next_textual = 0
            for row in sample_rows:
                comp_val = str(row[comp_idx]).strip() if len(row) > comp_idx else ''
                next_val = str(row[next_idx]).strip() if len(row) > next_idx else ''
                if re.fullmatch(r'\d+', comp_val):
                    comp_numeric += 1
                if next_val and not re.fullmatch(r'\d+', next_val):
                    next_textual += 1
            if comp_numeric >= max(2, len(sample_rows) // 2) and next_textual >= max(2, len(sample_rows) // 2):
                col_mapping['sequencia'] = comp_idx
                col_mapping['componente'] = next_idx

        # Processar linhas de dados (após cabeçalho)
        data_rows = all_rows[header_row_idx + 1:]

        anos = {}
        current_ano = None
        totais_gerais = {}

        for row in data_rows:
            if not row or not any(str(cell).strip() for cell in row):
                continue

            # Determinar o ano (pode estar em coluna específica ou ser propagado)
            ano_col = col_mapping.get('ano', 0)
            ano_text = str(row[ano_col]).strip() if len(row) > ano_col else ''

            # Detectar se é linha de ano (incluindo 4º ano)
            ano_match = re.search(r'([1234]º?\s*ano)', ano_text.lower())
            if ano_match:
                current_ano = ano_match.group(1).replace(' ', ' ').strip()
                # Normalizar: "1º ano" -> "1º Ano"
                current_ano = re.sub(r'(\d+)º?\s*ano', r'\1º Ano', current_ano, flags=re.IGNORECASE)

            if not current_ano:
                # Verificar se é linha de totais gerais
                first_cell = str(row[0]).lower() if row else ''
                if 'total' in first_cell or 'ch total' in first_cell:
                    # Extrair totais
                    for key, col_idx in col_mapping.items():
                        if col_idx < len(row) and row[col_idx]:
                            try:
                                val = int(re.sub(r'[^\d]', '', str(row[col_idx])))
                                totais_gerais[key] = val
                            except (ValueError, TypeError):
                                pass
                continue

            if current_ano not in anos:
                anos[current_ano] = {
                    'ano': current_ano,
                    'componentes': [],
                    'subtotais': {}
                }

            # Extrair componente
            comp_col = col_mapping.get('componente', 1)
            componente_nome = str(row[comp_col]).strip() if len(row) > comp_col else ''

            if not componente_nome:
                continue

            componente_lower = componente_nome.lower()

            # Detectar linha de total geral (ANTES do subtotal)
            is_grand_total = (
                'total do curso' in componente_lower or
                'total geral' in componente_lower or
                ('carga' in componente_lower and 'total' in componente_lower and 'subtotal' not in componente_lower)
            )
            if is_grand_total:
                for key, col_idx in col_mapping.items():
                    if col_idx < len(row) and row[col_idx]:
                        try:
                            val = int(re.sub(r'[^\d]', '', str(row[col_idx])))
                            totais_gerais[key] = val
                        except (ValueError, TypeError):
                            pass
                current_ano = None
                continue

            # Verificar se é linha de subtotal
            if 'total' in componente_lower or 'subtotal' in componente_lower:
                for key, col_idx in col_mapping.items():
                    if col_idx < len(row) and row[col_idx]:
                        try:
                            val = int(re.sub(r'[^\d]', '', str(row[col_idx])))
                            anos[current_ano]['subtotais'][key] = val
                        except (ValueError, TypeError):
                            pass
                continue

            # Extrair dados do componente
            componente = {
                'nome': componente_nome,
                'aulas_semanais': None,
                'ch_hora_aula': None,
                'ch_teorica': None,
                'ch_pratica': None,
                'ch_hora_relogio_cnct': None
            }

            # Extrair valores numéricos
            def extract_number(col_key):
                col_idx = col_mapping.get(col_key)
                if col_idx is not None and col_idx < len(row):
                    try:
                        val = re.sub(r'[^\d]', '', str(row[col_idx]))
                        return int(val) if val else None
                    except (ValueError, TypeError):
                        return None
                return None

            componente['aulas_semanais'] = extract_number('aulas_semanais')
            componente['ch_hora_aula'] = extract_number('ch_total') or extract_number('total')
            componente['ch_teorica'] = extract_number('ch_teorica')
            componente['ch_pratica'] = extract_number('ch_pratica')
            componente['ch_hora_relogio_cnct'] = extract_number('ch_cnct')

            anos[current_ano]['componentes'].append(componente)

        if not anos:
            return None

        # Calcular totais se não encontrados
        totais = {
            'ch_total_hora_aula': 0,
            'ch_total_hora_relogio': 0
        }

        for ano_data in anos.values():
            for comp in ano_data['componentes']:
                if comp['ch_hora_aula']:
                    totais['ch_total_hora_aula'] += comp['ch_hora_aula']
                if comp['ch_hora_relogio_cnct']:
                    totais['ch_total_hora_relogio'] += comp['ch_hora_relogio_cnct']

        # Usar totais do documento se disponíveis
        if totais_gerais:
            if 'ch_total' in totais_gerais:
                totais['ch_total_hora_aula'] = totais_gerais['ch_total']
            if 'ch_cnct' in totais_gerais:
                totais['ch_total_hora_relogio'] = totais_gerais['ch_cnct']

        return {
            'tipo': 'matriz_curricular_ppc',
            'minutos_hora_aula': minutos_hora_aula,
            'semanas_ano_letivo': semanas_ano_letivo,
            'anos': list(anos.values()),
            'totais': totais
        }
