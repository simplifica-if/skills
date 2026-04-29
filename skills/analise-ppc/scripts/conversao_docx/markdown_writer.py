"""
MarkdownWriter - Módulo de geração de Markdown

Responsável por converter elementos do documento para formato Markdown,
gerando o arquivo final de saída.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, TextIO, Union

from .docx_reader import (
    DocxReader, DocumentElement, ElementType,
    HeadingElement, ParagraphElement, TableElement, TextRun, ImageElement
)
from .ementario_extractor import EmentarioExtractor
from .identification_extractor import IdentificationExtractor
from .image_extractor import ImageExtractor
from .markdown_normalizer import MarkdownNormalizer
from .matrix_extractor import MatrixExtractor
from .section_detector import Section, SectionDetector
from .table_extractor import TableExtractor


class MarkdownWriter:
    """
    Escritor de Markdown para documentos PPC.

    Converte elementos do documento DOCX para formato Markdown,
    preservando a estrutura e formatação.

    Uso:
        writer = MarkdownWriter()
        markdown = writer.convert(elements)
        writer.save("output.md", markdown)
    """

    def __init__(self):
        """Inicializa o escritor."""
        self.table_extractor = TableExtractor()
        self._list_state = {'active': False, 'type': None, 'level': 0}

    def convert(self, elements: List[DocumentElement]) -> str:
        """
        Converte lista de elementos para Markdown.

        Args:
            elements: Lista de elementos do documento

        Returns:
            String Markdown
        """
        lines = []
        self._list_state = {'active': False, 'type': None, 'level': 0}

        for i, element in enumerate(elements):
            md = self._convert_element(element)

            if md:
                # Adicionar quebra antes de headings (exceto primeiro)
                if element.type == ElementType.HEADING and lines:
                    # Verificar se já tem linha em branco
                    if lines[-1].strip():
                        lines.append('')

                lines.append(md)

                # Adicionar quebra após headings e tabelas
                if element.type in (ElementType.HEADING, ElementType.TABLE):
                    lines.append('')

        # Finalizar lista se estiver ativa
        if self._list_state['active']:
            lines.append('')

        return '\n'.join(lines)

    def _convert_element(self, element: DocumentElement) -> str:
        """Converte um elemento para Markdown."""
        if element.type == ElementType.HEADING:
            return self._convert_heading(element)
        elif element.type == ElementType.TABLE:
            return self._convert_table(element)
        elif element.type == ElementType.PARAGRAPH:
            return self._convert_paragraph(element)
        return ''

    def _convert_heading(self, heading: HeadingElement) -> str:
        """Converte heading para Markdown."""
        # Fechar lista ativa se houver
        prefix = ''
        if self._list_state['active']:
            self._list_state = {'active': False, 'type': None, 'level': 0}
            prefix = '\n'

        # Limitar nível a 6
        level = min(heading.level, 6)
        hashes = '#' * level

        return f"{prefix}{hashes} {heading.text}"

    def _convert_table(self, table: TableElement) -> str:
        """Converte tabela para Markdown."""
        # Fechar lista ativa se houver
        prefix = ''
        if self._list_state['active']:
            self._list_state = {'active': False, 'type': None, 'level': 0}
            prefix = '\n'

        normalized = self.table_extractor.normalize(table)
        md = self.table_extractor.to_markdown(normalized)

        return f"{prefix}{md}"

    def _convert_paragraph(self, para: ParagraphElement) -> str:
        """Converte parágrafo para Markdown."""
        if para.is_empty:
            # Parágrafos vazios podem indicar fim de lista
            if self._list_state['active']:
                self._list_state = {'active': False, 'type': None, 'level': 0}
                return ''
            return ''

        # Converter runs para texto com formatação
        text = self._convert_runs(para.runs)

        if para.is_list_item:
            return self._convert_list_item(text, para)

        # Se estava em lista, fechar
        if self._list_state['active']:
            self._list_state = {'active': False, 'type': None, 'level': 0}
            return '\n' + text

        return text

    def _format_single_run(self, run: TextRun) -> str:
        """Aplica formatação Markdown a um único run."""
        text = run.text
        if not text:
            return ''

        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"

        if run.strike:
            text = f"~~{text}~~"

        return text

    def _convert_runs(self, runs: List[TextRun]) -> str:
        """Converte lista de runs para texto formatado, agrupando hyperlinks."""
        parts = []
        # Buffer para acumular runs do mesmo hyperlink
        link_buffer: List[str] = []
        current_url: Optional[str] = None

        def flush_link():
            """Emite o hyperlink acumulado no buffer."""
            if link_buffer:
                link_text = ''.join(link_buffer)
                if current_url:
                    parts.append(f"[{link_text}]({current_url})")
                else:
                    parts.append(link_text)
                link_buffer.clear()

        for run in runs:
            if not run.text:
                continue

            formatted = self._format_single_run(run)

            if run.hyperlink_url != current_url:
                flush_link()
                current_url = run.hyperlink_url

            link_buffer.append(formatted)

        flush_link()

        result = ''.join(parts)

        # Limpar formatação duplicada (ex: ****texto**** -> **texto**)
        result = re.sub(r'\*{4,}', '**', result)

        return result

    def _convert_list_item(self, text: str, para: ParagraphElement) -> str:
        """Converte item de lista."""
        level = para.list_level
        indent = '  ' * level

        if para.list_type == 'number':
            # Lista numerada
            marker = '1.'
        else:
            # Lista com marcadores
            marker = '-'

        # Atualizar estado da lista
        self._list_state = {
            'active': True,
            'type': para.list_type,
            'level': level
        }

        # Remover marcadores já presentes no texto
        text = re.sub(r'^[\d]+[.)]\s*', '', text)
        text = re.sub(r'^[•\-\*–—]\s*', '', text)

        return f"{indent}{marker} {text}"

    def convert_with_sections(self, sections: List[Section]) -> str:
        """
        Converte documento organizado em seções.

        Args:
            sections: Lista de seções do SectionDetector

        Returns:
            String Markdown
        """
        lines = []
        self._list_state = {'active': False, 'type': None, 'level': 0}

        for section in sections:
            lines.append(self._convert_section(section))

        return '\n'.join(lines)

    def _convert_section(self, section: Section, depth: int = 0) -> str:
        """Converte uma seção e suas subsections."""
        lines = []

        # Heading da seção
        level = min(section.level, 6)
        hashes = '#' * level
        lines.append(f"{hashes} {section.full_title}")
        lines.append('')

        # Elementos da seção
        for element in section.elements:
            md = self._convert_element(element)
            if md:
                lines.append(md)
                if element.type == ElementType.TABLE:
                    lines.append('')

        # Subsections
        for subsection in section.subsections:
            lines.append('')
            lines.append(self._convert_section(subsection, depth + 1))

        return '\n'.join(lines)

    def save(self, filepath: Union[str, Path], content: str) -> None:
        """
        Salva conteúdo Markdown em arquivo.

        Args:
            filepath: Caminho do arquivo
            content: Conteúdo Markdown
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)


class PPCConverter:
    """
    Conversor completo de PPC DOCX para Markdown.

    Orquestra todos os módulos para converter um documento PPC.

    Uso:
        converter = PPCConverter("PPC.docx")
        converter.convert()
        converter.save("output/ppc.md", "output/ppc_dados.json")
    """

    # Padrões para detectar seção de representação gráfica
    GRAPHIC_SECTION_PATTERNS = [
        r'representa[çc][ãa]o\s+gr[áa]fica',
        r'fluxograma',
        r'diagrama\s+do\s+(curso|processo)',
        r'organiza[çc][ãa]o\s+visual',
    ]

    def __init__(self, docx_path: Union[str, Path]):
        """
        Inicializa o conversor.

        Args:
            docx_path: Caminho para o arquivo DOCX
        """
        self.docx_path = Path(docx_path)
        self.reader = DocxReader(docx_path)
        self.section_detector = SectionDetector()
        self.table_extractor = TableExtractor()
        self.matrix_extractor = MatrixExtractor()
        self.identification_extractor = IdentificationExtractor()
        self.ementario_extractor = EmentarioExtractor()
        self.markdown_writer = MarkdownWriter()
        self.markdown_normalizer = MarkdownNormalizer()
        self.image_extractor = ImageExtractor(docx_path)

        self._elements: List[DocumentElement] = []
        self._sections: List[Section] = []
        self._markdown: str = ''
        self._markdown_bruto: str = ''
        self._data: Dict = {}
        self._graphic_section: Dict = {'found': False}
        self._graphic_image_path: Optional[Path] = None

    def convert(self, verbose: bool = False) -> None:
        """
        Executa a conversão completa.

        Args:
            verbose: Se True, imprime informações durante conversão
        """
        if verbose:
            print(f"Lendo: {self.docx_path.name}")

        # 1. Ler elementos do DOCX
        self._elements = list(self.reader.elements())

        if verbose:
            print(f"  - {len(self._elements)} elementos encontrados")

        # 2. Detectar seções
        self._sections = self.section_detector.detect(self._elements)

        if verbose:
            section_list = self.section_detector.get_section_list(self._sections)
            print(f"  - {len(section_list)} seções detectadas")

        # 3. Detectar seção de representação gráfica
        self._detect_graphic_representation()

        if verbose and self._graphic_section.get('found'):
            print(f"  - Representação gráfica detectada: {self._graphic_section.get('section_title', 'N/A')}")

        # 4. Converter para Markdown
        if self._sections:
            self._markdown_bruto = self.markdown_writer.convert_with_sections(self._sections)
        else:
            self._markdown_bruto = self.markdown_writer.convert(self._elements)

        resultado_normalizacao = self.markdown_normalizer.normalize(self._markdown_bruto)
        self._markdown_bruto = resultado_normalizacao.markdown_bruto
        self._markdown = resultado_normalizacao.markdown_normalizado

        if verbose:
            linhas_brutas = self._markdown_bruto.count('\n') + 1
            linhas_normalizadas = self._markdown.count('\n') + 1
            print(f"  - {linhas_brutas} linhas de Markdown bruto geradas")
            print(f"  - {linhas_normalizadas} linhas de Markdown normalizado geradas")

        # 5. Extrair dados
        self._extract_data()

        if verbose:
            print(f"  - {len(self._data.get('dados_extraidos', {}))} campos de dados extraídos")

    def _extract_data(self) -> None:
        """Extrai dados estruturados do documento."""
        metadata = self.reader.get_metadata()

        # Dados básicos
        self._data = {
            'arquivo_origem': self.docx_path.name,
            'data_conversao': datetime.now().isoformat(),
            'metadata_documento': {
                k: v for k, v in metadata.items() if v
            },
            'dados_extraidos': {},
            'estrutura': {
                'secoes_detectadas': self.section_detector.get_section_list(self._sections),
                'total_elementos': len(self._elements),
                'total_tabelas': sum(1 for e in self._elements if e.type == ElementType.TABLE),
            }
        }

        # Extrair dados das seções
        hints = self.section_detector.extract_data_hints(self._sections)
        self._data['dados_extraidos'].update(hints)

        # Extrair dados de tabelas
        for element in self._elements:
            if element.type == ElementType.TABLE:
                normalized = self.table_extractor.normalize(element)

                # 1. Tentar ementário (tabela de 1 coluna com ementa/bibliografia)
                ementario = self.ementario_extractor.extract_ementario_data(normalized)
                if ementario:
                    if 'ementario' not in self._data:
                        self._data['ementario'] = {
                            'tipo': 'ementario_ppc',
                            'componentes': [],
                            'por_ano': {}
                        }
                    self._data['ementario']['componentes'].append(ementario)
                    ano = ementario.get('periodo_letivo', 'Indefinido')
                    if ano not in self._data['ementario']['por_ano']:
                        self._data['ementario']['por_ano'][ano] = []
                    self._data['ementario']['por_ano'][ano].append(ementario['nome'])
                    continue

                # 2. Tentar tabela de identificação (1-2 colunas, tipo campo|valor)
                if normalized.num_cols <= 2:
                    id_data = self.identification_extractor.extract_identification_data(normalized)
                    if id_data:
                        self._data['dados_extraidos'].update(id_data)

                # 3. Tentar matriz curricular PPC (extrator especializado)
                ppc_matrix = self.matrix_extractor.extract_ppc_matrix_data(normalized)
                if ppc_matrix and ppc_matrix.get('anos'):
                    self._data['matriz_curricular'] = ppc_matrix
                elif not self._data.get('matriz_curricular'):
                    # Fallback para extrator genérico
                    matrix = self.matrix_extractor.extract_matrix_data(normalized)
                    if matrix:
                        self._data['matriz_curricular'] = matrix

        # Adicionar estatísticas do ementário
        if 'ementario' in self._data:
            em = self._data['ementario']
            em['total_componentes'] = len(em['componentes'])
            em['estatisticas'] = {
                'total_por_ano': {ano: len(comps) for ano, comps in em['por_ano'].items()},
                'total_referencias_basicas': sum(
                    len(c.get('bibliografia_basica', [])) for c in em['componentes']
                ),
                'total_referencias_complementares': sum(
                    len(c.get('bibliografia_complementar', [])) for c in em['componentes']
                )
            }

    def _detect_graphic_representation(self) -> None:
        """
        Detecta a seção de Representação Gráfica do Processo Formativo.

        Busca nas seções do documento por padrões que indicam
        a presença de um fluxograma ou diagrama do curso.
        """
        self._graphic_section = {'found': False}

        def search_sections(sections: List[Section]) -> Optional[Section]:
            """Busca recursivamente nas seções."""
            for section in sections:
                # Verificar se o título corresponde a algum padrão
                for pattern in self.GRAPHIC_SECTION_PATTERNS:
                    if re.search(pattern, section.title, re.IGNORECASE):
                        return section
                    if re.search(pattern, section.full_title, re.IGNORECASE):
                        return section

                # Buscar em subseções
                found = search_sections(section.subsections)
                if found:
                    return found

            return None

        graphic_section = search_sections(self._sections)

        if graphic_section:
            # Verificar se há ImageElement na seção
            images = [e for e in graphic_section.elements if e.type == ElementType.IMAGE]
            has_bitmap = any(not img.is_drawing for img in images)
            bitmap_partname = next(
                (img.partname for img in images if not img.is_drawing and img.partname),
                None
            )
            has_drawings = any(img.is_drawing for img in images)

            self._graphic_section = {
                'found': True,
                'section_title': graphic_section.full_title,
                'has_bitmap': has_bitmap,
                'bitmap_partname': bitmap_partname,
                'has_drawings': has_drawings or (not has_bitmap and not images),
                'image_count': len(images),
            }

    def _insert_graphic_reference_in_markdown(self) -> str:
        """
        Insere referência à imagem da representação gráfica no Markdown.

        Localiza a seção de representação gráfica no markdown e adiciona
        a referência à imagem logo após o heading da seção.

        Returns:
            Markdown atualizado com referência à imagem
        """
        if not self._graphic_section.get('found'):
            return self._markdown_bruto
        if "imagens/representacao_grafica.png" in self._markdown_bruto:
            return self._markdown_bruto

        # Construir padrão para encontrar o heading da seção
        section_title = self._graphic_section.get('section_title', '')

        # Criar padrões de busca para diferentes formatos
        patterns = self.GRAPHIC_SECTION_PATTERNS + [re.escape(section_title)]

        # Buscar o heading no markdown
        lines = self._markdown_bruto.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#'):
                # Verificar se é o heading da seção de representação gráfica
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Inserir referência à imagem após o heading
                        image_ref = "\n![Representação Gráfica do Processo Formativo](imagens/representacao_grafica.png)\n"

                        # Encontrar próxima linha não vazia ou fim
                        insert_pos = i + 1
                        while insert_pos < len(lines) and not lines[insert_pos].strip():
                            insert_pos += 1

                        # Inserir na posição correta
                        lines.insert(insert_pos, image_ref)
                        return '\n'.join(lines)

        return self._markdown_bruto

    @property
    def markdown_bruto(self) -> str:
        """Retorna o Markdown bruto gerado antes da normalização."""
        return self._markdown_bruto

    @property
    def markdown(self) -> str:
        """Retorna o Markdown gerado."""
        return self._markdown

    @property
    def data(self) -> Dict:
        """Retorna os dados extraídos."""
        return self._data

    @property
    def sections(self) -> List[Section]:
        """Retorna as seções detectadas."""
        return self._sections

    def save(
        self,
        md_path: Optional[Union[str, Path]] = None,
        json_path: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Path]:
        """
        Salva os arquivos de saída.

        Args:
            md_path: Caminho para o arquivo Markdown
            json_path: Caminho para o arquivo JSON
            output_dir: Diretório de saída (se paths não especificados)

        Returns:
            Dict com paths dos arquivos salvos
        """
        saved = {}
        md_bruto_path: Optional[Path] = None

        # Determinar paths
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            base_name = self.docx_path.stem
            if md_path is None:
                md_path = output_dir / f"{base_name}.md"
            if json_path is None:
                json_path = output_dir / f"{base_name}_dados.json"

        if md_path:
            md_path = Path(md_path)
            md_bruto_path = md_path.with_name(f"{md_path.stem}-bruto{md_path.suffix}")
        if json_path:
            json_path = Path(json_path)

        # Extrair imagem da representação gráfica antes de salvar Markdown e JSON.
        if self._graphic_section.get('found'):
            actual_output_dir = output_dir or (md_path.parent if md_path else json_path.parent if json_path else None)
            if actual_output_dir:
                img_saved = self._save_graphic_image(Path(actual_output_dir))
                if img_saved:
                    saved.update(img_saved)
                    self._markdown_bruto = self._insert_graphic_reference_in_markdown()
                    resultado_normalizacao = self.markdown_normalizer.normalize(self._markdown_bruto)
                    self._markdown_bruto = resultado_normalizacao.markdown_bruto
                    self._markdown = resultado_normalizacao.markdown_normalizado

        # Salvar Markdown
        if md_path:
            md_path.parent.mkdir(parents=True, exist_ok=True)

            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(self._markdown)
            with open(md_bruto_path, 'w', encoding='utf-8') as f:
                f.write(self._markdown_bruto)
            saved['markdown'] = md_path
            saved['markdown_bruto'] = md_bruto_path

        # Salvar JSON (após extração de imagem para ter metadados corretos)
        if json_path:
            json_path.parent.mkdir(parents=True, exist_ok=True)

            saved.update(
                self._save_split_json_files(
                    json_path,
                    markdown_filename=md_path.name if md_path else None,
                    markdown_bruto_filename=md_bruto_path.name if md_bruto_path else None,
                )
            )

        return saved

    def _save_split_json_files(
        self,
        json_path: Path,
        markdown_filename: Optional[str] = None,
        markdown_bruto_filename: Optional[str] = None,
    ) -> Dict[str, Path]:
        """
        Salva dados em arquivos JSON separados.

        Args:
            json_path: Caminho base para o arquivo JSON principal
            markdown_filename: Nome do Markdown normalizado, quando salvo
            markdown_bruto_filename: Nome do Markdown bruto, quando salvo

        Returns:
            Dict com paths dos arquivos salvos
        """
        saved = {}
        base_name = json_path.stem.replace('_dados', '')
        output_dir = json_path.parent

        # Nomes dos arquivos relacionados
        matriz_filename = f"{base_name}_matriz_curricular.json"
        ementario_filename = f"{base_name}_ementario.json"

        matriz_path = output_dir / matriz_filename
        ementario_path = output_dir / ementario_filename

        # Extrair dados grandes
        matriz_data = self._data.get('matriz_curricular', {})
        ementario_data = self._data.get('ementario', {})

        # Criar dados principais com referências
        main_data = self._create_main_data(
            matriz_filename,
            ementario_filename,
            markdown_filename=markdown_filename,
            markdown_bruto_filename=markdown_bruto_filename,
        )

        # Salvar arquivo principal
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False)
        saved['json'] = json_path

        # Salvar matriz curricular (se existir)
        if matriz_data:
            with open(matriz_path, 'w', encoding='utf-8') as f:
                json.dump(matriz_data, f, indent=2, ensure_ascii=False)
            saved['json_matriz'] = matriz_path

        # Salvar ementário (se existir)
        if ementario_data:
            with open(ementario_path, 'w', encoding='utf-8') as f:
                json.dump(ementario_data, f, indent=2, ensure_ascii=False)
            saved['json_ementario'] = ementario_path

        return saved

    def _create_main_data(
        self,
        matriz_filename: str,
        ementario_filename: str,
        markdown_filename: Optional[str] = None,
        markdown_bruto_filename: Optional[str] = None,
    ) -> Dict:
        """
        Cria o dicionário de dados principal com referências aos arquivos relacionados.

        Args:
            matriz_filename: Nome do arquivo de matriz curricular
            ementario_filename: Nome do arquivo de ementário

        Returns:
            Dict com dados principais e referências
        """
        matriz_data = self._data.get('matriz_curricular', {})
        ementario_data = self._data.get('ementario', {})

        main_data = {
            'arquivo_origem': self._data.get('arquivo_origem'),
            'data_conversao': self._data.get('data_conversao'),
            'metadata_documento': self._data.get('metadata_documento', {}),
            'dados_extraidos': self._data.get('dados_extraidos', {}),
            'estrutura': self._data.get('estrutura', {}),
        }

        # Adicionar referências aos arquivos relacionados
        arquivos_relacionados = {}
        if markdown_filename:
            arquivos_relacionados['markdown_normalizado'] = markdown_filename
        if markdown_bruto_filename:
            arquivos_relacionados['markdown_bruto'] = markdown_bruto_filename
        if matriz_data:
            arquivos_relacionados['matriz_curricular'] = matriz_filename
        if ementario_data:
            arquivos_relacionados['ementario'] = ementario_filename
        if self._graphic_image_path:
            arquivos_relacionados['representacao_grafica'] = 'imagens/representacao_grafica.png'

        if arquivos_relacionados:
            main_data['arquivos_relacionados'] = arquivos_relacionados

        # Adicionar informações sobre representação gráfica
        if self._graphic_section.get('found'):
            main_data['representacao_grafica'] = {
                'encontrada': True,
                'secao': self._graphic_section.get('section_title', ''),
                'tem_bitmap': self._graphic_section.get('has_bitmap', False),
                'tem_desenhos_vetoriais': self._graphic_section.get('has_drawings', False),
                'extraida': self._graphic_image_path is not None,
                'metodo': self._graphic_section.get('extraction_method', 'não extraída'),
                'caminho': 'imagens/representacao_grafica.png' if self._graphic_image_path else None,
            }

        # Adicionar resumo da matriz curricular
        if matriz_data:
            main_data['resumo_matriz_curricular'] = self._criar_resumo_matriz(matriz_data)

        # Adicionar resumo do ementário
        if ementario_data:
            main_data['resumo_ementario'] = self._criar_resumo_ementario(ementario_data)

        return main_data

    def _criar_resumo_matriz(self, matriz_data: Dict) -> Dict:
        """Cria resumo da matriz curricular."""
        resumo = {}

        if 'anos' in matriz_data:
            anos = matriz_data['anos']
            resumo['total_anos'] = len(anos)

            total_componentes = 0
            total_ha = 0
            total_hr = 0

            # Suporta tanto dicionário quanto lista
            anos_iter = anos.values() if isinstance(anos, dict) else anos
            for ano_data in anos_iter:
                if isinstance(ano_data, dict):
                    componentes = ano_data.get('componentes', [])
                    total_componentes += len(componentes)
                    total_ha += ano_data.get('total_ha', 0)
                    total_hr += ano_data.get('total_hr', 0)

            resumo['total_componentes'] = total_componentes
            resumo['total_ha'] = total_ha
            resumo['total_hr'] = total_hr

        # Incluir totais gerais se existirem
        if 'totais' in matriz_data:
            resumo['totais'] = matriz_data['totais']

        return resumo

    def _criar_resumo_ementario(self, ementario_data: Dict) -> Dict:
        """Cria resumo do ementário."""
        resumo = {
            'total_componentes': ementario_data.get('total_componentes', 0),
        }

        # Adicionar estatísticas se existirem
        if 'estatisticas' in ementario_data:
            stats = ementario_data['estatisticas']
            resumo['total_referencias_basicas'] = stats.get('total_referencias_basicas', 0)
            resumo['total_referencias_complementares'] = stats.get('total_referencias_complementares', 0)
            resumo['total_por_ano'] = stats.get('total_por_ano', {})

        return resumo

    def _save_graphic_image(self, output_dir: Path) -> Dict[str, Path]:
        """
        Extrai e salva a imagem da representação gráfica.

        Estratégia:
        1. Se há bitmap na seção, extrai diretamente do ZIP do DOCX
        2. Se há apenas shapes/drawings, renderiza a página via Word+PDF

        Args:
            output_dir: Diretório base de saída

        Returns:
            Dict com path do arquivo salvo, ou vazio se falhar
        """
        if not self._graphic_section.get('found'):
            return {}

        images_dir = output_dir / "imagens"
        output_path = images_dir / "representacao_grafica.png"

        try:
            # Tentar extração - padrão específico para o heading da seção
            # Ex: "5.12 REPRESENTAÇÃO GRÁFICA DO PROCESSO FORMATIVO"
            path, method = self.image_extractor.extract_section_image(
                section_pattern=r'representa[çc][ãa]o\s+gr[áa]fica\s+do\s+processo',
                output_path=output_path,
                has_bitmap=self._graphic_section.get('has_bitmap', False),
                bitmap_partname=self._graphic_section.get('bitmap_partname'),
            )
            self._graphic_image_path = path
            self._graphic_section['extraction_method'] = method
            return {'imagem_representacao_grafica': path}

        except ImportError as e:
            # Dependências não instaladas para renderização
            print(f"Aviso: Não foi possível extrair imagem (dependências faltando): {e}")
            self._graphic_section['extraction_method'] = 'falha_dependencias'
            return {}

        except ValueError as e:
            # Seção não encontrada no PDF
            print(f"Aviso: Não foi possível extrair imagem: {e}")
            self._graphic_section['extraction_method'] = 'falha_secao_nao_encontrada'
            return {}

        except Exception as e:
            # Outros erros
            print(f"Aviso: Erro ao extrair imagem: {e}")
            self._graphic_section['extraction_method'] = f'falha_{type(e).__name__}'
            return {}
