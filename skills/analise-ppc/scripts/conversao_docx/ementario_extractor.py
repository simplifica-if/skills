"""
EmentarioExtractor - Extração de ementário de componentes curriculares

Responsável por processar tabelas de ementário que contêm informações
detalhadas sobre cada componente curricular: ementa, bibliografias, carga horária.

Versão aprimorada com fuzzy matching para detecção robusta de referências ABNT.
"""

import re
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback para ambientes sem dependência opcional
    from difflib import SequenceMatcher

    class _FuzzFallback:
        @staticmethod
        def partial_ratio(a: str, b: str) -> int:
            menor, maior = sorted((a, b), key=len)
            if not menor:
                return 0

            melhor = 0.0
            janela = len(menor)
            for inicio in range(max(1, len(maior) - janela + 1)):
                trecho = maior[inicio : inicio + janela]
                melhor = max(melhor, SequenceMatcher(None, menor, trecho).ratio())
            return int(round(melhor * 100))

    fuzz = _FuzzFallback()

from .table_extractor import NormalizedTable


class EmentarioExtractor:
    """
    Extrator de ementário de componentes curriculares com fuzzy matching.

    Detecta tabelas de 1 coluna com estrutura:
    - COMPONENTE CURRICULAR: [nome]
    - Período letivo: [ano]
    - Carga horária total: [horas]
    - EMENTA: [conteúdo]
    - BIBLIOGRAFIA BÁSICA: [refs]
    - BIBLIOGRAFIA COMPLEMENTAR: [refs]

    Usa heurísticas combinadas com fuzzy matching para separar referências
    bibliográficas ABNT corretamente, mesmo quando:
    - Usam hífen como marcador de lista
    - Estão concatenadas sem espaço
    - Contêm ISBN/DOI/volumes

    Uso:
        extractor = EmentarioExtractor()
        data = extractor.extract_ementario_data(normalized_table)
    """

    # Editoras e locais comuns em referências ABNT brasileiras
    EDITORAS_CONHECIDAS = [
        "Moderna", "Saraiva", "Ática", "Contexto", "Blucher", "LTC",
        "Bookman", "Artmed", "Érica", "Atlas", "Pearson", "Elsevier",
        "Scipione", "Cortez", "Vozes", "EDUSP", "UFSC", "FURG", "UFRGS",
        "Loyola", "Papirus", "Atual", "Cengage", "Manole", "Phorte",
        "IBRACON", "Oficina de Textos", "Companhia das Letras", "Contentus",
        "Publifolha", "Record", "Objetiva", "Rocco", "Intrínseca", "Sextante",
        "Nova Fronteira", "Civilização Brasileira", "Zahar", "Companhia Editora Nacional"
    ]

    LOCAIS_CONHECIDOS = [
        "São Paulo", "Rio de Janeiro", "Porto Alegre", "Curitiba",
        "Belo Horizonte", "Campinas", "Florianópolis", "Salvador",
        "Brasília", "Recife", "Londrina", "Niterói", "Petrópolis",
        "Barueri", "Bauru", "Ribeirão Preto", "Santa Maria", "Maringá"
    ]

    def __init__(self):
        """Inicializa o extrator de ementário."""
        pass

    def _count_effective_cols(self, table: NormalizedTable) -> int:
        """
        Conta colunas efetivas (não vazias) da tabela.

        Tabelas de ementário do Google Docs podem ter colunas extras vazias
        (padding), resultando em 3 colunas onde apenas a primeira tem conteúdo.

        Args:
            table: Tabela normalizada

        Returns:
            Número de colunas com conteúdo
        """
        if table.num_cols <= 1:
            return table.num_cols

        # Verificar se colunas além da primeira são todas vazias
        all_rows = ([table.headers] if table.headers else []) + table.rows
        for row in all_rows:
            for col_idx in range(1, len(row)):
                if row[col_idx] and row[col_idx].strip():
                    return table.num_cols  # Há conteúdo em outras colunas
        return 1  # Apenas a primeira coluna tem conteúdo

    def extract_ementario_data(self, table: NormalizedTable) -> Optional[Dict]:
        """
        Extrai dados de um componente do ementário.

        Args:
            table: Tabela normalizada

        Returns:
            Dict com nome, periodo, ch, ementa, bibliografias ou None
        """
        # 1. Verificar se é tabela de 1 coluna (ou com colunas extras vazias)
        effective_cols = self._count_effective_cols(table)
        if effective_cols != 1:
            return None

        # 2. Juntar todo conteúdo (usar apenas a primeira coluna)
        all_rows = [table.headers] + table.rows if table.headers else table.rows
        all_text = '\n'.join(row[0] for row in all_rows if row and row[0])
        all_text_lower = all_text.lower()

        # 3. Verificar padrões de ementário
        if not self._is_ementario(all_text_lower):
            return None

        # 4. Extrair dados
        return {
            'nome': self._extract_nome(all_text),
            'periodo_letivo': self._extract_periodo(all_text),
            'carga_horaria_aula': self._extract_carga_horaria(all_text),
            'ementa': self._extract_ementa(all_text),
            'bibliografia_basica': self._parse_referencias_fuzzy(
                self._extract_bibliografia_basica(all_text)
            ),
            'bibliografia_complementar': self._parse_referencias_fuzzy(
                self._extract_bibliografia_complementar(all_text)
            )
        }

    def _is_ementario(self, text_lower: str) -> bool:
        """
        Verifica se o texto contém padrões de ementário.

        Args:
            text_lower: Texto em minúsculas

        Returns:
            True se for ementário, False caso contrário
        """
        # Deve ter pelo menos componente curricular e ementa
        has_componente = 'componente curricular:' in text_lower
        has_ementa = 'ementa' in text_lower
        has_bibliografia = 'bibliografia' in text_lower

        return has_componente and has_ementa and has_bibliografia

    def _extract_nome(self, text: str) -> str:
        """
        Extrai nome do componente curricular.

        Args:
            text: Texto completo da célula

        Returns:
            Nome do componente ou string vazia
        """
        # Padrão: COMPONENTE CURRICULAR: [nome]
        # O nome pode ir até "Período" ou "Carga" ou quebra de linha
        match = re.search(
            r'componente\s*curricular:\s*(.+?)(?=\n|período|carga|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            nome = match.group(1).strip()
            # Limpar caracteres de formatação
            nome = re.sub(r'\s+', ' ', nome)
            return nome
        return ''

    def _extract_periodo(self, text: str) -> Optional[str]:
        """
        Extrai período letivo (1º ano, 2º ano, etc.).

        Args:
            text: Texto completo da célula

        Returns:
            Período letivo ou None
        """
        # Padrões: "Período letivo: 1º ano", "Período: 2º Ano"
        match = re.search(
            r'período\s*(?:letivo)?:\s*(\d+º?\s*ano)',
            text,
            re.IGNORECASE
        )
        if match:
            periodo = match.group(1).strip()
            # Normalizar: "1º ano" -> "1º Ano"
            periodo = re.sub(r'(\d+)º?\s*ano', r'\1º Ano', periodo, flags=re.IGNORECASE)
            return periodo
        return None

    def _extract_carga_horaria(self, text: str) -> Optional[int]:
        """
        Extrai carga horária em horas-aula.

        Args:
            text: Texto completo da célula

        Returns:
            Carga horária em horas-aula ou None
        """
        # Padrões diversos de carga horária
        patterns = [
            r'carga\s*hor[áa]ria\s*(?:total)?(?:\s+do\s+componente)?:\s*(\d+)',
            r'c\.?\s*h\.?\s*(?:total)?:\s*(\d+)',
            r'(\d+)\s*(?:horas?[/\- ]aula|h/a)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_ementa(self, text: str) -> str:
        """
        Extrai conteúdo da ementa.

        Args:
            text: Texto completo da célula

        Returns:
            Conteúdo da ementa ou string vazia
        """
        # A ementa vai de "EMENTA:" até "BIBLIOGRAFIA"
        match = re.search(
            r'ementa:?\s*(.+?)(?=bibliografia|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            ementa = match.group(1).strip()
            # Limpar formatação excessiva mas manter estrutura
            ementa = re.sub(r'\n{3,}', '\n\n', ementa)
            ementa = re.sub(r'[ \t]+', ' ', ementa)
            return ementa.strip()
        return ''

    def _extract_bibliografia_basica(self, text: str) -> str:
        """
        Extrai texto da bibliografia básica.

        Args:
            text: Texto completo da célula

        Returns:
            Texto da bibliografia básica ou string vazia
        """
        # A bibliografia básica vai até "bibliografia complementar"
        match = re.search(
            r'bibliografia\s*b[áa]sica:?\s*(.+?)(?=bibliografia\s*complementar|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            return match.group(1).strip()
        return ''

    def _extract_bibliografia_complementar(self, text: str) -> str:
        """
        Extrai texto da bibliografia complementar.

        Args:
            text: Texto completo da célula

        Returns:
            Texto da bibliografia complementar ou string vazia
        """
        # A bibliografia complementar vai até o fim
        match = re.search(
            r'bibliografia\s*complementar:?\s*(.+?)$',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            return match.group(1).strip()
        return ''

    def _parse_referencias_fuzzy(self, texto: str) -> List[str]:
        """
        Separa referências bibliográficas usando heurísticas + fuzzy matching.

        Estratégia:
        1. Separar primeiro por blocos de linhas/listas quando existirem
        2. Detectar pontos de quebra usando padrões ABNT
        3. Detectar inícios prováveis de nova referência de forma mais permissiva
        4. Aplicar uma heurística complementar por autor quando necessário
        5. Validar as fronteiras encontradas

        Args:
            texto: Texto com as referências concatenadas

        Returns:
            Lista de referências individuais
        """
        if not texto:
            return []

        referencias: List[str] = []
        for bloco in self._separar_blocos_referencias(texto):
            referencias.extend(self._parse_referencias_bloco(bloco))

        referencias_normalizadas: List[str] = []
        vistos = set()
        for referencia in referencias:
            referencia_limpa = re.sub(r'\s+', ' ', referencia).strip()
            if not referencia_limpa or referencia_limpa in vistos:
                continue
            referencias_normalizadas.append(referencia_limpa)
            vistos.add(referencia_limpa)

        return referencias_normalizadas

    def _parse_referencias_bloco(self, texto: str) -> List[str]:
        """Processa um bloco contínuo de bibliografia."""
        if not texto:
            return []

        texto = re.sub(r'\s+', ' ', texto).strip()
        if not texto:
            return []

        # 1. DETECÇÃO DE PONTOS DE QUEBRA
        # Encontrar posições onde provavelmente termina uma referência
        quebras = self._detectar_quebras(texto)
        quebras.extend(self._detectar_quebras_por_inicio_referencia(texto))

        if not quebras:
            refs_por_autor = self._parse_referencias_por_autor(texto)
            if refs_por_autor:
                return refs_por_autor
            if self._parece_referencia(texto):
                return [texto]
            return []

        # 3. DIVIDIR E VALIDAR
        referencias = []
        inicio = 0

        for pos in sorted(set(quebras)):
            if pos <= inicio:
                continue
            candidato = texto[inicio:pos].strip()
            # Remover hífen inicial se presente
            candidato = re.sub(r'^[\-–—]\s*', '', candidato)
            if self._parece_referencia(candidato):
                referencias.append(candidato)
            inicio = pos

        # Última parte
        ultimo = texto[inicio:].strip()
        ultimo = re.sub(r'^[\-–—]\s*', '', ultimo)
        if self._parece_referencia(ultimo):
            referencias.append(ultimo)

        # Se não encontrou nada, tentar heurística por autor
        if not referencias:
            return self._parse_referencias_por_autor(texto)

        return referencias

    def _separar_blocos_referencias(self, texto: str) -> List[str]:
        """
        Separa blocos por quebras de linha ou marcadores de lista.

        Muitos PPCs mantêm uma referência por linha no Markdown convertido.
        Preservar essas fronteiras evita fundir referências antes das heurísticas
        mais permissivas entrarem em ação.
        """
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        linhas = [linha.strip() for linha in texto.split('\n')]

        blocos: List[str] = []
        atual: List[str] = []

        for linha in linhas:
            if not linha:
                if atual:
                    blocos.append(' '.join(atual).strip())
                    atual = []
                continue

            linha_limpa = re.sub(r'^[|•▪◦●]\s*', '', linha).strip()
            if re.match(r'^[\-–—]\s+', linha_limpa) and atual:
                blocos.append(' '.join(atual).strip())
                atual = [linha_limpa]
                continue

            atual.append(linha_limpa)

        if atual:
            blocos.append(' '.join(atual).strip())

        return [bloco for bloco in blocos if bloco]

    def _parse_referencias_por_autor(self, texto: str) -> List[str]:
        """
        Heurística complementar de separação por novo autor.

        Separa por padrão de novo autor (SOBRENOME em maiúsculas no início
        após ponto final e espaço).

        Args:
            texto: Texto com as referências

        Returns:
            Lista de referências individuais
        """
        if not texto:
            return []

        # Limpar texto
        texto = re.sub(r'\s+', ' ', texto).strip()

        # Separar por padrão de novo autor (SOBRENOME em maiúsculas no início)
        refs = re.split(
            r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]*,)',
            texto
        )

        # Filtrar referências válidas
        referencias = []
        for r in refs:
            r = r.strip()
            if r and len(r) > 10:
                if re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]', r):
                    referencias.append(r)

        return referencias

    def _detectar_quebras(self, texto: str) -> List[int]:
        """
        Detecta posições onde provavelmente começa uma nova referência.

        Usa combinação de:
        - Padrões regex (ano, ISBN, volume, etc.)
        - Fuzzy matching para editoras/locais

        Args:
            texto: Texto completo das referências

        Returns:
            Lista de posições (índices) onde começam novas referências
        """
        quebras = []

        # Padrão 1: Hífen marcador de lista seguido de sobrenome
        # Exemplo: "...2020. - MATOSO, Rubiane..." ou "...2020.-SILVA, José..."
        pattern_hifen = re.compile(
            r'[.\s]+'           # Fim da referência anterior (ponto e/ou espaços)
            r'[\-–—]\s*'       # Hífen marcador
            r'(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]*,)',  # Início de SOBRENOME,
            re.UNICODE
        )

        for match in pattern_hifen.finditer(texto):
            # Posição após o hífen (onde começa o sobrenome)
            pos = match.end()
            # Ajustar para pular espaços
            while pos < len(texto) and texto[pos] in ' \t':
                pos += 1
            quebras.append(pos)

        # Padrão 2: Após ano/ISBN/volume, seguido de início de nova referência (sem hífen)
        # Exemplo: "...2013.IEZZI, Gelson..." ou "...v. 1.ISAIA, G. C..."
        pattern_ano = re.compile(
            r'('
            # Fim da referência anterior
            r'(?:(?:19|20)\d{2})'          # Ano 1900-2099
            r'|(?:ISBN\s*[\d\-X]+)'         # ISBN
            r'|(?:v\.\s*\d+)'               # Volume
            r'|(?:p\.\s*\d+[\-\d]*)'        # Páginas
            r'|(?:n\.\s*\d+)'               # Número
            r')'
            r'[.\s]*'                       # Separador (ponto e/ou espaços, opcionais)
            r'(?='                          # Lookahead para início de nova ref
            r'[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}'        # 2+ letras maiúsculas (SOBRENOME)
            r'[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]*'         # Mais maiúsculas ou espaços
            r',\s*[A-Za-záéíóúàâêôãõç]'     # Vírgula e início do nome próprio
            r')',
            re.UNICODE
        )

        for match in pattern_ano.finditer(texto):
            pos = match.end()
            # Não adicionar se já temos uma quebra muito próxima
            if not any(abs(q - pos) < 5 for q in quebras):
                quebras.append(pos)

        # Padrão 3: Fuzzy matching para detectar padrões "Local: Editora" que indicam fim
        quebras.extend(self._detectar_quebras_fuzzy(texto))

        return list(set(quebras))  # Remover duplicatas

    def _detectar_quebras_por_inicio_referencia(self, texto: str) -> List[int]:
        """
        Detecta novas referências a partir de padrões de início de autor.

        Cobre casos em que a referência anterior termina com uma frase, URL ou
        observação e a próxima inicia logo em seguida, sem um ano/ISBN/volume
        imediatamente antes.
        """
        pattern_inicio = re.compile(
            r'(?:(?<=^)|(?<=[.!?])\s+|(?<=[.!?])(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ_]))'
            r'(?='
            r'(?:[\-–—]\s*)?'
            r'(?:'
            r'(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇáéíóúàâêôãõç]+'
            r'(?:[\s\-]+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇáéíóúàâêôãõç]+){0,3}'
            r'|[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}'
            r'(?:[\s\-]+(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}|DA|DE|DI|DO|DU|DAS|DOS|DEL|E)){0,6})'
            r',+\s*(?![A-Z]{2}\s*:)[A-ZÁÉÍÓÚÀÂÊÔÃÕÇa-záéíóúàâêôãõç]'
            r'|_{3,}\.'
            r'|BRASIL\.'
            r'|(?:[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}(?:[\s/&()\-]+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}){1,8}(?:\s+\([A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇáéíóúàâêôãõç]{2,}\))?)\.'
            r')'
            r')',
            re.UNICODE
        )

        quebras: List[int] = []
        for match in pattern_inicio.finditer(texto):
            pos = match.start()
            if pos == 0:
                continue
            if not any(abs(q - pos) < 5 for q in quebras):
                quebras.append(pos)

        return quebras

    def _detectar_quebras_fuzzy(self, texto: str) -> List[int]:
        """
        Usa fuzzy matching para detectar padrões de editoras/locais
        que indicam fim de referência.

        Procura por padrões "Local: Editora, ano." e verifica se após
        vem uma nova referência.

        Args:
            texto: Texto completo das referências

        Returns:
            Lista de posições onde começam novas referências
        """
        quebras = []

        # Procurar padrões "Local: Editora, ano."
        for local in self.LOCAIS_CONHECIDOS:
            # Buscar ocorrências aproximadas do local
            matches = self._find_fuzzy_occurrences(texto, local, threshold=85)
            for pos, _ in matches:
                # Verificar se após o local vem ": Editora, ano."
                resto = texto[pos:pos + 150]
                # Padrão: Local: Editora, ano. (opcionalmente com volume/ISBN)
                match_fim = re.search(
                    r':\s*[^,]+,\s*(?:19|20)\d{2}'  # : Editora, ano
                    r'(?:\.\s*v\.\s*\d+)?'          # Opcional: . v. N
                    r'(?:\.\s*ISBN[^.]+)?'          # Opcional: . ISBN ...
                    r'[.\s]*',                      # Ponto final e espaços
                    resto
                )
                if match_fim:
                    quebra_pos = pos + match_fim.end()
                    # Verificar se após vem nova referência (SOBRENOME, ou hífen+SOBRENOME)
                    if quebra_pos < len(texto):
                        proximo = texto[quebra_pos:quebra_pos + 60].strip()
                        if re.match(r'^[\-–—]?\s*[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]*,', proximo):
                            # Ajustar posição para pular hífen/espaços iniciais
                            ajuste = 0
                            temp = texto[quebra_pos:]
                            for i, c in enumerate(temp):
                                if c in '-–— \t':
                                    ajuste = i + 1
                                elif c.isupper():
                                    break
                                else:
                                    break
                            quebras.append(quebra_pos + ajuste)

        return quebras

    def _find_fuzzy_occurrences(self, texto: str, termo: str, threshold: int = 80) -> List[Tuple[int, int]]:
        """
        Encontra ocorrências fuzzy de um termo no texto.

        Args:
            texto: Texto onde buscar
            termo: Termo a buscar
            threshold: Score mínimo (0-100) para considerar match

        Returns:
            Lista de (posição, score) para matches acima do threshold.
        """
        resultados = []
        janela = len(termo) + 5  # Janela de busca um pouco maior que o termo

        i = 0
        while i < len(texto) - len(termo) + 1:
            trecho = texto[i:i + janela]
            score = fuzz.partial_ratio(termo.lower(), trecho.lower())
            if score >= threshold:
                resultados.append((i, score))
                # Pular para evitar matches sobrepostos
                i += len(termo)
            else:
                i += 1

        return resultados

    def _parece_referencia(self, texto: str) -> bool:
        """
        Verifica se o texto parece uma referência bibliográfica válida.

        Critérios:
        - Mínimo 20 caracteres
        - Começa com letra maiúscula, número ou sobrenome
        - Contém vírgula (separador autor/nome)
        - Contém ponto (fim de campos)

        Args:
            texto: Texto candidato a referência

        Returns:
            True se parece referência válida, False caso contrário
        """
        if not texto or len(texto) < 20:
            return False

        texto = texto.strip()

        # Remover hífen inicial se presente
        texto = re.sub(r'^[\-–—]\s*', '', texto)

        if not texto:
            return False

        # Deve começar com maiúscula ou número
        if not re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ0-9_]', texto):
            return False

        # Deve ter vírgula (autor, Nome ou Local: Ed)
        if ',' not in texto:
            if not self._parece_referencia_institucional(texto):
                return False

        # Deve ter pelo menos um ponto
        if '.' not in texto:
            return False

        return True

    def _parece_referencia_institucional(self, texto: str) -> bool:
        """Aceita referências institucionais ou normativas sem vírgula no autor."""
        inicio_institucional = re.match(
            r'^(?:_{3,}|BRASIL|[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}(?:[\s/&()\-]+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]{2,}){1,8}(?:\s+\([A-Za-zÁÉÍÓÚÀÂÊÔÃÕÇáéíóúàâêôãõç]{2,}\))?)\.',
            texto
        )
        if not inicio_institucional:
            return False

        return bool(
            re.search(
                r'((?:19|20)\d{2}|c(?:19|20)\d{2}|Disponível em:|Lei nº|Resolução nº|Ministério|Secretaria|Política de|Proposta Pedagógica)',
                texto,
                re.IGNORECASE
            )
        )
