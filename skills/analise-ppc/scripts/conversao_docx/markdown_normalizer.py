"""
Normalização determinística do Markdown extraído de PPCs.

Responsável por limpar ruídos recorrentes da conversão bruta do DOCX
antes da análise auditável e da geração de evidências por linha.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class MarkdownNormalizationResult:
    """Resultado da normalização com métricas simples de diagnóstico."""

    markdown_bruto: str
    markdown_normalizado: str
    linhas_brutas: int
    linhas_normalizadas: int


class MarkdownNormalizer:
    """Aplica heurísticas estáveis de limpeza e reparo do Markdown."""

    _PAGINATION_PATTERNS = [
        re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4},?\s+\d{1,2}:\d{2}(:\d{2})?\s*$"),
        re.compile(r"^\s*https?://sei\.ifpr\.edu\.br/sei/controlador\.php\S*\s*$", re.IGNORECASE),
        re.compile(r"^\s*p[aá]gina\s+\d+(\s+de\s+\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*pag\.\s*\d+(\s+de\s+\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*sei/ifpr\s*[-–].*$", re.IGNORECASE),
        re.compile(r"^\s*documento assinado eletronicamente.*$", re.IGNORECASE),
        re.compile(r"^\s*consulta autenticidade.*$", re.IGNORECASE),
        re.compile(r"^\s*c[oó]digo verificador.*$", re.IGNORECASE),
    ]

    _TOC_LINE_PATTERN = re.compile(r"^\s*\d+(\.\d+)*\s+.+\.{2,}\s*\d+\s*$")
    _SECTION_NUMBER_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(.+?)\s*$")
    _HEADING_PATTERN = re.compile(r"^\s*(#{1,6})\s*(.+?)\s*$")
    _LIST_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

    def normalize(self, markdown: str) -> MarkdownNormalizationResult:
        """Executa o pipeline de normalização do Markdown."""
        bruto = markdown.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").replace("\t", "    ")
        linhas = bruto.split("\n")
        linhas = self._corrigir_heading_quebrado(linhas)
        linhas = [self._limpar_linha(linha) for linha in linhas]
        linhas = self._remover_ruidos(linhas)
        linhas = self._normalizar_headings(linhas)
        linhas = self._remover_blocos_duplicados(linhas)
        linhas = self._consolidar_paragrafos(linhas)
        linhas = self._normalizar_tabelas_pipe(linhas)
        linhas = self._colapsar_linhas_em_branco(linhas)
        normalizado = "\n".join(linhas).strip() + "\n"
        return MarkdownNormalizationResult(
            markdown_bruto=bruto,
            markdown_normalizado=normalizado,
            linhas_brutas=bruto.count("\n") + 1 if bruto else 0,
            linhas_normalizadas=normalizado.count("\n") + 1 if normalizado else 0,
        )

    def _limpar_linha(self, linha: str) -> str:
        """Aplica limpeza leve sem descaracterizar tabelas e listas."""
        linha = linha.rstrip()
        if not linha:
            return ""
        if "|" not in linha:
            linha = re.sub(r" {2,}", " ", linha)
        linha = re.sub(r"\*{4,}", "**", linha)
        linha = re.sub(r"\*\*\s+([^*]+?)\s+\*\*", r"**\1**", linha)
        linha = re.sub(r"\s+([,.;:])", r"\1", linha)
        return linha.strip()

    def _corrigir_heading_quebrado(self, linhas: List[str]) -> List[str]:
        """Une linhas com marcador `#` isolado à linha de título subsequente."""
        corrigidas: List[str] = []
        indice = 0
        while indice < len(linhas):
            atual = linhas[indice].strip()
            if re.fullmatch(r"#{1,6}", atual) and indice + 1 < len(linhas):
                proxima = linhas[indice + 1].strip()
                if proxima and not proxima.startswith("#"):
                    corrigidas.append(f"{atual} {proxima}")
                    indice += 2
                    continue
            corrigidas.append(linhas[indice])
            indice += 1
        return corrigidas

    def _remover_ruidos(self, linhas: List[str]) -> List[str]:
        """Remove cabeçalhos, rodapés e artefatos de paginação conhecidos."""
        filtradas: List[str] = []
        dentro_sumario = False
        sumario_visto = False

        for linha in linhas:
            conteudo = linha.strip()
            if not conteudo:
                filtradas.append("")
                continue

            if any(pattern.match(conteudo) for pattern in self._PAGINATION_PATTERNS):
                continue

            if re.fullmatch(r"[_\-–—]{3,}", conteudo):
                continue

            if conteudo.lower() in {"sumário", "sumario"}:
                if sumario_visto:
                    dentro_sumario = True
                    continue
                sumario_visto = True
                filtradas.append("## Sumário")
                continue

            if dentro_sumario:
                if self._TOC_LINE_PATTERN.match(conteudo):
                    continue
                if self._parece_heading(conteudo):
                    dentro_sumario = False
                else:
                    continue

            filtradas.append(linha)

        return filtradas

    def _normalizar_headings(self, linhas: List[str]) -> List[str]:
        """Corrige níveis de heading e promove títulos numéricos plausíveis."""
        normalizadas: List[str] = []
        linha_anterior = ""

        for linha in linhas:
            conteudo = linha.strip()
            if not conteudo:
                normalizadas.append("")
                linha_anterior = ""
                continue

            match_heading = self._HEADING_PATTERN.match(conteudo)
            if match_heading:
                titulo = match_heading.group(2).strip()
                nivel = self._nivel_heading(titulo, fallback=len(match_heading.group(1)))
                normalizadas.append(f"{'#' * nivel} {titulo}")
                linha_anterior = conteudo
                continue

            if self._deve_promover_a_heading(conteudo, linha_anterior):
                nivel = self._nivel_heading(conteudo)
                normalizadas.append(f"{'#' * nivel} {conteudo}")
                linha_anterior = conteudo
                continue

            normalizadas.append(conteudo)
            linha_anterior = conteudo

        return normalizadas

    def _remover_blocos_duplicados(self, linhas: List[str]) -> List[str]:
        """Elimina repetições consecutivas simples de linhas ou blocos curtos."""
        deduplicadas: List[str] = []
        ultimo_conteudo = None
        for linha in linhas:
            conteudo = linha.strip()
            if conteudo and conteudo == ultimo_conteudo:
                continue
            deduplicadas.append(linha)
            if conteudo:
                ultimo_conteudo = conteudo
        return deduplicadas

    def _consolidar_paragrafos(self, linhas: List[str]) -> List[str]:
        """Une linhas partidas artificialmente sem afetar headings, listas e tabelas."""
        resultado: List[str] = []
        indice = 0

        while indice < len(linhas):
            atual = linhas[indice]
            if not self._eh_paragrafo_continuavel(atual):
                resultado.append(atual)
                indice += 1
                continue

            consolidado = atual.strip()
            while indice + 1 < len(linhas) and self._deve_unir_linhas(consolidado, linhas[indice + 1]):
                proxima = linhas[indice + 1].strip()
                if consolidado.endswith("-"):
                    consolidado = consolidado[:-1].rstrip() + proxima
                else:
                    consolidado = f"{consolidado} {proxima}"
                indice += 1

            resultado.append(consolidado)
            indice += 1

        return resultado

    def _colapsar_linhas_em_branco(self, linhas: List[str]) -> List[str]:
        """Mantém no máximo uma linha em branco consecutiva."""
        colapsadas: List[str] = []
        ultima_vazia = False
        for linha in linhas:
            vazia = not linha.strip()
            if vazia and ultima_vazia:
                continue
            colapsadas.append("" if vazia else linha)
            ultima_vazia = vazia
        return colapsadas

    def _normalizar_tabelas_pipe(self, linhas: List[str]) -> List[str]:
        """Padroniza blocos de tabelas pipe já reconhecíveis."""
        normalizadas: List[str] = []
        indice = 0

        while indice < len(linhas):
            if not self._eh_linha_tabela_pipe(linhas[indice]):
                normalizadas.append(linhas[indice])
                indice += 1
                continue

            inicio = indice
            while indice < len(linhas) and self._eh_linha_tabela_pipe(linhas[indice]):
                indice += 1
            bloco = linhas[inicio:indice]

            if self._bloco_parece_tabela_pipe(bloco):
                if normalizadas and normalizadas[-1].strip():
                    normalizadas.append("")
                normalizadas.extend(self._normalizar_bloco_tabela_pipe(bloco))
                if indice < len(linhas) and linhas[indice].strip():
                    normalizadas.append("")
                continue

            normalizadas.extend(bloco)

        return normalizadas

    def _eh_paragrafo_continuavel(self, linha: str) -> bool:
        conteudo = linha.strip()
        if not conteudo:
            return False
        if conteudo.startswith(("#", ">", "![", "<")):
            return False
        if conteudo.startswith("|") or conteudo.endswith("|"):
            return False
        if self._LIST_PATTERN.match(conteudo):
            return False
        if re.fullmatch(r"`{3,}.*", conteudo):
            return False
        if self._parece_heading(conteudo):
            return False
        return True

    def _deve_promover_a_heading(self, conteudo: str, linha_anterior: str) -> bool:
        if self._LIST_PATTERN.match(conteudo):
            return False
        if self._SECTION_NUMBER_PATTERN.match(conteudo):
            return True
        if linha_anterior.strip():
            return False
        if not self._parece_heading(conteudo):
            return False
        return True

    def _deve_unir_linhas(self, atual: str, proxima: str) -> bool:
        """Decide se a quebra entre duas linhas parece artificial."""
        atual = atual.strip()
        proxima = proxima.strip()
        if not atual or not proxima:
            return False
        if not self._eh_paragrafo_continuavel(atual) or not self._eh_paragrafo_continuavel(proxima):
            return False
        if re.search(r"[.!?]$", atual):
            return False
        if atual.endswith("-"):
            return True
        if re.match(r"^[a-zà-ÿ0-9(]", proxima):
            return True
        return False

    def _eh_linha_tabela_pipe(self, linha: str) -> bool:
        conteudo = linha.strip()
        return bool(conteudo) and conteudo.count("|") >= 2

    def _bloco_parece_tabela_pipe(self, bloco: List[str]) -> bool:
        if len(bloco) < 2:
            return False

        linhas_processadas = [self._extrair_celulas_tabela_pipe(linha) for linha in bloco]
        if any(not celulas for celulas in linhas_processadas):
            return False

        total_colunas = len(linhas_processadas[0])
        if total_colunas < 2:
            return False

        if any(len(celulas) != total_colunas for celulas in linhas_processadas):
            return False

        return self._eh_linha_separadora_tabela_pipe(bloco[1])

    def _normalizar_bloco_tabela_pipe(self, bloco: List[str]) -> List[str]:
        linhas_processadas = [self._extrair_celulas_tabela_pipe(linha) for linha in bloco]
        if not linhas_processadas:
            return bloco

        normalizadas = [self._formatar_linha_tabela_pipe(linhas_processadas[0])]
        normalizadas.append(self._formatar_separador_tabela_pipe(linhas_processadas[1]))

        for celulas in linhas_processadas[2:]:
            normalizadas.append(self._formatar_linha_tabela_pipe(celulas))

        return normalizadas

    def _extrair_celulas_tabela_pipe(self, linha: str) -> List[str]:
        conteudo = linha.strip()
        if not conteudo:
            return []

        partes: List[str] = []
        atual: List[str] = []
        escape = False

        for caractere in conteudo:
            if caractere == "\\" and not escape:
                atual.append(caractere)
                escape = True
                continue
            if caractere == "|" and not escape:
                partes.append("".join(atual).strip())
                atual = []
                continue
            atual.append(caractere)
            escape = False

        partes.append("".join(atual).strip())

        if partes and partes[0] == "":
            partes = partes[1:]
        if partes and partes[-1] == "":
            partes = partes[:-1]

        return [parte.strip() for parte in partes]

    def _eh_linha_separadora_tabela_pipe(self, linha: str) -> bool:
        celulas = self._extrair_celulas_tabela_pipe(linha)
        if not celulas:
            return False
        return all(re.fullmatch(r":?-{2,}:?", celula.replace(" ", "")) for celula in celulas)

    def _formatar_linha_tabela_pipe(self, celulas: List[str]) -> str:
        return f"| {' | '.join(celula.strip() for celula in celulas)} |"

    def _formatar_separador_tabela_pipe(self, celulas: List[str]) -> str:
        separadores: List[str] = []
        for celula in celulas:
            bruto = celula.replace(" ", "")
            largura = max(3, bruto.count("-"))
            if bruto.startswith(":") and bruto.endswith(":"):
                separadores.append(f":{'-' * largura}:")
            elif bruto.endswith(":"):
                separadores.append(f"{'-' * largura}:")
            elif bruto.startswith(":"):
                separadores.append(f":{'-' * largura}")
            else:
                separadores.append("-" * largura)
        return "|" + "|".join(separadores) + "|"

    def _parece_heading(self, conteudo: str) -> bool:
        if self._SECTION_NUMBER_PATTERN.match(conteudo):
            return True
        if len(conteudo) > 120:
            return False
        letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", conteudo)
        if not letras:
            return False
        return conteudo == conteudo.upper() and len(letras) >= 6

    def _nivel_heading(self, titulo: str, fallback: int = 2) -> int:
        match = self._SECTION_NUMBER_PATTERN.match(titulo)
        if not match:
            return max(1, min(fallback, 6))
        profundidade = match.group(1).count(".") + 1
        return max(1, min(profundidade, 6))
