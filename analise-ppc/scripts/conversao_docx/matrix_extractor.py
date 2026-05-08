"""
MatrixExtractor - Extração de matrizes curriculares.

Responsável por processar tabelas de PPCs e extrair dados estruturados
das matrizes curriculares. O extrator mantém dois caminhos explícitos:

- ``legacy``: formato com CH hora-aula e CH hora-relógio por período.
- ``nucleos_ftp_fgb_np``: formato com distribuição FTP/FGB/NP.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from .table_extractor import NormalizedTable


class MatrixExtractor:
    """Extrator de matrizes curriculares de PPCs."""

    def extract_matrix_data(self, table: NormalizedTable) -> Optional[Dict[str, Any]]:
        """
        Fallback genérico para matrizes simples.

        Este caminho é deliberadamente conservador para não classificar quadro
        docente como matriz curricular apenas por conter a coluna
        ``Componente Curricular``.
        """
        if not table.headers or not table.rows:
            return None
        if self._is_staff_table(table):
            return None

        headers_lower = [self._norm(header) for header in table.headers]
        header_text = " ".join(headers_lower)

        has_component = any("componente" in header or "disciplina" in header for header in headers_lower)
        has_workload = any(
            pattern in header_text
            for pattern in ("carga", "ch ", "hora-aula", "hora aula", "hora-relogio", "hora relogio")
        )
        has_period = any(
            pattern in header_text
            for pattern in ("ano", "semestre", "periodo", "serie")
        )
        if not (has_component and has_workload and has_period):
            return None

        componente_col = None
        ch_cols: list[int] = []
        total_col = None

        for index, header in enumerate(headers_lower):
            if any(pattern in header for pattern in ("componente", "disciplina", "unidade")):
                componente_col = index
            elif any(pattern in header for pattern in ("ano", "semestre", "periodo", "serie", "carga", "ch", "hora")):
                ch_cols.append(index)
            if "total" in header and any(pattern in header for pattern in ("ch", "carga", "hora")):
                total_col = index

        if componente_col is None:
            return None

        componentes: list[dict[str, Any]] = []
        for row in table.rows:
            if componente_col >= len(row):
                continue
            nome = row[componente_col].strip()
            if not nome or self._is_non_component_row(nome):
                continue

            componente: dict[str, Any] = {"nome": nome, "cargas": {}}
            for ch_col in ch_cols:
                if ch_col >= len(row):
                    continue
                valor = row[ch_col].strip()
                if not valor:
                    continue
                componente["cargas"][table.headers[ch_col]] = self._parse_int(valor) or valor

            if total_col is not None and total_col < len(row) and row[total_col].strip():
                componente["total"] = self._parse_int(row[total_col]) or row[total_col].strip()

            if componente["cargas"] or "total" in componente:
                componentes.append(componente)

        if not componentes:
            return None

        return {
            "tipo": "matriz_curricular",
            "headers": table.headers,
            "componentes": componentes,
            "total_rows": len(componentes),
        }

    def extract_ppc_matrix_data(self, table: NormalizedTable) -> Optional[Dict[str, Any]]:
        """Extrai matriz curricular usando os formatos PPC conhecidos."""
        return (
            self.extract_ppc_matrix_format_nucleos(table)
            or self.extract_ppc_matrix_format_legacy(table)
        )

    def extract_ppc_matrix_format_legacy(self, table: NormalizedTable) -> Optional[Dict[str, Any]]:
        """Extrai o formato legado de matriz curricular."""
        all_rows = self._all_rows(table)
        if not self._looks_like_legacy_matrix(all_rows):
            return None

        minutos_hora_aula = self._extract_metadata_number(
            all_rows,
            required_terms=("hora aula", "min"),
            minimum=40,
            maximum=60,
            default=50,
        )
        semanas_ano_letivo = self._extract_metadata_number(
            all_rows,
            required_terms=("semanas", "ano letivo"),
            minimum=30,
            maximum=50,
            default=40,
        )

        anos: dict[str, dict[str, Any]] = {}
        linhas_modelo: list[dict[str, Any]] = []
        totais: dict[str, int] = {}
        mapping: dict[str, int] | None = None
        current_ano: str | None = None

        for row in all_rows:
            if not self._row_has_content(row):
                continue
            if self._is_header_row(row, formato="legacy"):
                mapping = self._map_legacy_header(row)
                continue
            if mapping is None:
                inferred = self._infer_legacy_mapping_from_row(row)
                if inferred is None:
                    continue
                mapping = inferred

            row_text = self._row_text(row)
            ano = self._normalize_year(self._cell(row, mapping.get("ano")))
            if ano:
                current_ano = ano

            componente_nome = self._cell(row, mapping.get("componente"))
            if not componente_nome:
                continue

            componente_norm = self._norm(componente_nome)
            if self._is_model_line(row_text):
                linhas_modelo.append(
                    {
                        "nome": componente_nome,
                        "ch_hora_aula": self._workload_number_from(row, mapping.get("ch_total")),
                        "ch_hora_relogio": self._workload_number_from(row, mapping.get("ch_relogio")),
                    }
                )
                continue

            if self._is_grand_total(row_text):
                total_ha = self._number_from(row, mapping.get("ch_total"))
                total_hr = self._number_from(row, mapping.get("ch_relogio"))
                if total_ha is not None:
                    totais["ch_total_hora_aula"] = total_ha
                if total_hr is not None:
                    totais["ch_total_hora_relogio"] = total_hr
                current_ano = None
                continue

            if self._is_subtotal(componente_norm):
                if current_ano:
                    ano_data = self._ensure_ano(anos, current_ano)
                    self._update_legacy_subtotals(ano_data["subtotais"], row, mapping)
                continue

            if not current_ano or self._is_non_component_row(componente_nome):
                continue

            componente = {
                "nome": componente_nome,
                "aulas_semanais": self._number_from(row, mapping.get("aulas_semanais")),
                "ch_hora_aula": self._number_from(row, mapping.get("ch_total")),
                "ch_teorica": None,
                "ch_pratica": None,
                "ch_hora_relogio_cnct": self._number_from(row, mapping.get("ch_relogio")),
            }
            self._ensure_ano(anos, current_ano)["componentes"].append(componente)

        if not anos:
            return None

        computed_ha = sum(
            comp.get("ch_hora_aula") or 0
            for ano in anos.values()
            for comp in ano["componentes"]
        )
        computed_hr = sum(
            comp.get("ch_hora_relogio_cnct") or 0
            for ano in anos.values()
            for comp in ano["componentes"]
        )
        totais.setdefault("ch_total_hora_aula", computed_ha)
        totais.setdefault("ch_total_hora_relogio", computed_hr)

        return {
            "tipo": "matriz_curricular_ppc",
            "formato": "legacy",
            "minutos_hora_aula": minutos_hora_aula,
            "semanas_ano_letivo": semanas_ano_letivo,
            "anos": list(anos.values()),
            "linhas_modelo": linhas_modelo,
            "totais": totais,
        }

    def extract_ppc_matrix_format_nucleos(self, table: NormalizedTable) -> Optional[Dict[str, Any]]:
        """Extrai o formato de matriz com núcleos FTP/FGB/NP."""
        all_rows = self._all_rows(table)
        if not self._looks_like_nucleos_matrix(all_rows):
            return None

        minutos_hora_aula = self._extract_metadata_number(
            all_rows,
            required_terms=("hora aula", "min"),
            minimum=40,
            maximum=60,
            default=50,
        )
        semanas_ano_letivo = self._extract_metadata_number(
            all_rows,
            required_terms=("semanas", "ano letivo"),
            minimum=30,
            maximum=50,
            default=40,
        )

        anos: dict[str, dict[str, Any]] = {}
        linhas_modelo: list[dict[str, Any]] = []
        totais: dict[str, int] = {}
        mapping: dict[str, int] | None = None
        current_ano: str | None = None

        for row in all_rows:
            if not self._row_has_content(row):
                continue
            if self._is_header_row(row, formato="nucleos"):
                mapping = self._map_nucleos_header(row)
                continue
            if mapping is None:
                inferred = self._infer_nucleos_mapping_from_row(row)
                if inferred is None:
                    continue
                mapping = inferred

            row_text = self._row_text(row)
            ano = self._normalize_year(self._cell(row, mapping.get("ano")))
            if ano:
                current_ano = ano

            componente_nome = self._cell(row, mapping.get("componente"))
            if not componente_nome:
                continue

            componente_norm = self._norm(componente_nome)
            if self._is_model_line(row_text):
                linhas_modelo.append(
                    {
                        "nome": componente_nome,
                        "ch_ftp": self._workload_number_from(row, mapping.get("ch_ftp")),
                        "ch_fgb": self._workload_number_from(row, mapping.get("ch_fgb")),
                        "ch_np": self._workload_number_from(row, mapping.get("ch_np")),
                        "ch_hora_aula": self._workload_number_from(row, mapping.get("ch_total")),
                        "ch_hora_relogio": self._workload_number_from(row, mapping.get("ch_relogio")),
                    }
                )
                continue

            if self._is_grand_total(row_text):
                self._update_nucleos_totais(totais, row, mapping)
                current_ano = None
                continue

            if self._is_subtotal(componente_norm) or "total ano" in row_text:
                if current_ano:
                    ano_data = self._ensure_ano(anos, current_ano)
                    self._update_nucleos_subtotals(ano_data["subtotais"], row, mapping)
                continue

            if not current_ano or self._is_non_component_row(componente_nome):
                continue

            componente = {
                "nome": componente_nome,
                "aulas_semanais": self._number_from(row, mapping.get("aulas_semanais")),
                "ch_hora_aula": self._number_from(row, mapping.get("ch_total")),
                "ch_hora_relogio_cnct": self._number_from(row, mapping.get("ch_relogio")),
                "ch_ftp": self._number_from(row, mapping.get("ch_ftp")),
                "ch_fgb": self._number_from(row, mapping.get("ch_fgb")),
                "ch_np": self._number_from(row, mapping.get("ch_np")),
            }
            self._ensure_ano(anos, current_ano)["componentes"].append(componente)

        if not anos:
            return None

        computed_ha = sum(
            comp.get("ch_hora_aula") or 0
            for ano in anos.values()
            for comp in ano["componentes"]
        )
        computed_hr = sum(
            comp.get("ch_hora_relogio_cnct") or 0
            for ano in anos.values()
            for comp in ano["componentes"]
        )
        totais.setdefault("ch_total_hora_aula", computed_ha)
        totais.setdefault("ch_total_hora_relogio", computed_hr)
        totais.setdefault("ch_ftp", sum(
            comp.get("ch_ftp") or 0 for ano in anos.values() for comp in ano["componentes"]
        ))
        totais.setdefault("ch_fgb", sum(
            comp.get("ch_fgb") or 0 for ano in anos.values() for comp in ano["componentes"]
        ))
        totais.setdefault("ch_np", sum(
            comp.get("ch_np") or 0 for ano in anos.values() for comp in ano["componentes"]
        ))

        return {
            "tipo": "matriz_curricular_ppc",
            "formato": "nucleos_ftp_fgb_np",
            "minutos_hora_aula": minutos_hora_aula,
            "semanas_ano_letivo": semanas_ano_letivo,
            "anos": list(anos.values()),
            "linhas_modelo": linhas_modelo,
            "totais": totais,
        }

    def merge_matrix_data(
        self,
        current: Optional[Dict[str, Any]],
        incoming: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Mescla partes de uma mesma matriz curricular extraídas em tabelas separadas."""
        if not incoming:
            return current
        if not current:
            return incoming
        if current.get("tipo") != "matriz_curricular_ppc" or incoming.get("tipo") != "matriz_curricular_ppc":
            return incoming if self.score_matrix(incoming) > self.score_matrix(current) else current
        if current.get("formato") != incoming.get("formato"):
            return incoming if self.score_matrix(incoming) > self.score_matrix(current) else current

        merged = dict(current)
        by_year: dict[str, dict[str, Any]] = {
            str(ano.get("ano")): {
                "ano": ano.get("ano"),
                "componentes": list(ano.get("componentes", [])),
                "subtotais": dict(ano.get("subtotais", {})),
            }
            for ano in current.get("anos", [])
            if isinstance(ano, dict)
        }
        for ano in incoming.get("anos", []):
            if not isinstance(ano, dict):
                continue
            chave = str(ano.get("ano"))
            if chave not in by_year:
                by_year[chave] = {
                    "ano": ano.get("ano"),
                    "componentes": list(ano.get("componentes", [])),
                    "subtotais": dict(ano.get("subtotais", {})),
                }
                continue
            existing_names = {comp.get("nome") for comp in by_year[chave]["componentes"]}
            for comp in ano.get("componentes", []):
                if comp.get("nome") not in existing_names:
                    by_year[chave]["componentes"].append(comp)
            by_year[chave]["subtotais"].update(ano.get("subtotais", {}))

        merged["anos"] = sorted(by_year.values(), key=lambda item: self._year_sort_key(str(item.get("ano", ""))))
        merged["linhas_modelo"] = self._merge_linhas_modelo(
            current.get("linhas_modelo", []),
            incoming.get("linhas_modelo", []),
        )
        merged["totais"] = self._merge_totais(current.get("totais", {}), incoming.get("totais", {}), merged)
        return merged

    def score_matrix(self, matrix: Dict[str, Any]) -> int:
        """Pontua matrizes candidatas para evitar falsos positivos."""
        if matrix.get("tipo") == "matriz_curricular_ppc":
            componentes = sum(len(ano.get("componentes", [])) for ano in matrix.get("anos", []))
            score = 1000 + componentes * 10
            if matrix.get("totais"):
                score += 100
            if matrix.get("formato") == "nucleos_ftp_fgb_np":
                score += 20
            return score
        return len(matrix.get("componentes", []))

    def matrix_to_markdown(self, matrix: Dict[str, Any]) -> str:
        """Renderiza a matriz estruturada em Markdown canônico."""
        if matrix.get("formato") == "nucleos_ftp_fgb_np":
            return self._nucleos_matrix_to_markdown(matrix)
        if matrix.get("formato") == "legacy":
            return self._legacy_matrix_to_markdown(matrix)
        return ""

    def replace_matrix_markdown(self, markdown: str, matrix: Dict[str, Any]) -> str:
        """Substitui a tabela da seção 5.6 pela representação canônica."""
        canonical = self.matrix_to_markdown(matrix)
        if not canonical:
            return markdown

        lines = markdown.splitlines()
        for heading_idx, line in enumerate(lines):
            if not re.match(r"^#{1,6}\s+5\.6\s+MATRIZ CURRICULAR\b", line.strip(), re.IGNORECASE):
                continue

            start = None
            for index in range(heading_idx + 1, len(lines)):
                stripped = lines[index].strip()
                if stripped.startswith("#") and index > heading_idx + 1:
                    break
                if stripped.startswith("|") and (
                    "MATRIZ CURRICULAR" in stripped.upper()
                    or "Componente Curricular" in stripped
                    or re.match(r"^\|\s*\d", stripped)
                ):
                    start = index
                    break
            if start is None:
                continue

            end = start
            seen_table = False
            while end < len(lines):
                stripped = lines[end].strip()
                if stripped.startswith("|"):
                    seen_table = True
                    end += 1
                    continue
                if seen_table and not stripped:
                    end += 1
                    continue
                if seen_table and (
                    stripped.startswith("- **Nota")
                    or stripped.startswith("#")
                    or (stripped and not stripped.startswith("|"))
                ):
                    break
                end += 1

            new_lines = lines[:start]
            if new_lines and new_lines[-1].strip():
                new_lines.append("")
            new_lines.extend(canonical.splitlines())
            if end < len(lines) and lines[end].strip():
                new_lines.append("")
            new_lines.extend(lines[end:])
            return "\n".join(new_lines).strip() + "\n"

        return markdown

    def _looks_like_legacy_matrix(self, rows: list[list[str]]) -> bool:
        if self._contains_ementario_text(rows):
            return False
        text = self._rows_text(rows)
        has_component_header = "componente curricular" in text
        has_workload = any(pattern in text for pattern in ("ch hora-aula", "hora-aula no periodo", "hora relogio no periodo", "hora-relogio no periodo"))
        has_year_rows = any(self._normalize_year(row[0] if row else "") for row in rows)
        has_continuation_rows = self._count_year_workload_rows(rows, min_cols=5) >= 3
        return has_year_rows and ((has_component_header and has_workload) or has_continuation_rows)

    def _looks_like_nucleos_matrix(self, rows: list[list[str]]) -> bool:
        if self._contains_ementario_text(rows):
            return False
        text = self._rows_text(rows)
        has_component_header = "componente curricular" in text
        has_nucleos = all(term in text for term in ("ftp", "fgb", "np"))
        has_workload = "hora-aula" in text and ("hora relogio" in text or "hora-relogio" in text)
        has_year_rows = any(self._normalize_year(row[0] if row else "") for row in rows)
        has_continuation_rows = self._count_year_workload_rows(rows, min_cols=8) >= 3
        return has_year_rows and ((has_component_header and has_nucleos and has_workload) or has_continuation_rows)

    def _all_rows(self, table: NormalizedTable) -> list[list[str]]:
        rows: list[list[str]] = []
        if table.headers:
            rows.append(table.headers)
        rows.extend(table.rows)
        return rows

    def _is_staff_table(self, table: NormalizedTable) -> bool:
        text = self._norm(" ".join(table.headers))
        return all(term in text for term in ("nome", "area de formacao", "perfil de formacao", "componente curricular"))

    def _contains_ementario_text(self, rows: list[list[str]]) -> bool:
        text = self._rows_text(rows[:10])
        return any(term in text for term in ("ementa:", "bibliografia", "basica:", "complementar:"))

    def _count_year_workload_rows(self, rows: list[list[str]], min_cols: int) -> int:
        total = 0
        for row in rows:
            if len(row) < min_cols or not self._normalize_year(row[0]):
                continue
            if not str(row[1]).strip() or self._is_subtotal(self._norm(row[1])):
                continue
            numeric_cells = sum(1 for cell in row[2:] if self._parse_int(cell) is not None)
            if numeric_cells >= 2:
                total += 1
        return total

    def _is_header_row(self, row: list[str], formato: str) -> bool:
        text = self._row_text(row)
        if "componente curricular" not in text:
            return False
        if formato == "nucleos":
            return all(term in text for term in ("ftp", "fgb", "np")) and "hora-aula" in text
        return ("ch hora-aula" in text or "hora-aula no periodo" in text) and (
            "hora-relogio" in text or "hora relogio" in text
        )

    def _map_legacy_header(self, row: list[str]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for index, cell in enumerate(row):
            norm = self._norm(cell)
            if norm == "ano" or ("periodo" in norm and "hora" not in norm):
                mapping["ano"] = index
            elif "componente" in norm or "disciplina" in norm:
                mapping["componente"] = index
            elif "aulas semanais" in norm or "numero de aulas" in norm or "no. de aulas" in norm:
                mapping["aulas_semanais"] = index
            elif "hora-aula" in norm or "hora aula" in norm or "ch hora-aula" in norm:
                mapping["ch_total"] = index
            elif "hora-relogio" in norm or "hora relogio" in norm:
                mapping["ch_relogio"] = index
        return mapping

    def _map_nucleos_header(self, row: list[str]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for index, cell in enumerate(row):
            norm = self._norm(cell)
            if norm == "ano" or ("periodo" in norm and "hora" not in norm):
                mapping["ano"] = index
            elif "componente" in norm or "disciplina" in norm:
                mapping["componente"] = index
            elif "aulas semanais" in norm or "numero de aulas" in norm or "no. de aulas" in norm:
                mapping["aulas_semanais"] = index
            elif "ftp" in norm:
                mapping["ch_ftp"] = index
            elif "fgb" in norm:
                mapping["ch_fgb"] = index
            elif re.fullmatch(r".*\bnp\b.*", norm):
                mapping["ch_np"] = index
            elif ("hora-aula" in norm or "hora aula" in norm) and "total" in norm:
                mapping["ch_total"] = index
            elif "relogio" in norm and "total" in norm:
                mapping["ch_relogio"] = index
        return mapping

    def _infer_legacy_mapping_from_row(self, row: list[str]) -> Optional[dict[str, int]]:
        if len(row) >= 5 and self._normalize_year(row[0]) and row[1].strip():
            return {"ano": 0, "componente": 1, "aulas_semanais": 2, "ch_total": 3, "ch_relogio": 4}
        return None

    def _infer_nucleos_mapping_from_row(self, row: list[str]) -> Optional[dict[str, int]]:
        if len(row) >= 8 and self._normalize_year(row[0]) and row[1].strip():
            return {
                "ano": 0,
                "componente": 1,
                "aulas_semanais": 2,
                "ch_ftp": 3,
                "ch_fgb": 4,
                "ch_np": 5,
                "ch_total": 6,
                "ch_relogio": 7,
            }
        return None

    def _ensure_ano(self, anos: dict[str, dict[str, Any]], ano: str) -> dict[str, Any]:
        if ano not in anos:
            anos[ano] = {"ano": ano, "componentes": [], "subtotais": {}}
        return anos[ano]

    def _update_legacy_subtotals(self, subtotais: dict[str, int], row: list[str], mapping: dict[str, int]) -> None:
        aulas = self._number_from(row, mapping.get("aulas_semanais"))
        total_ha = self._number_from(row, mapping.get("ch_total"))
        total_hr = self._number_from(row, mapping.get("ch_relogio"))
        if aulas is not None:
            subtotais["aulas_semanais"] = aulas
        if total_ha is not None:
            subtotais["ch_total_hora_aula"] = total_ha
        if total_hr is not None:
            subtotais["ch_total_hora_relogio"] = total_hr

    def _update_nucleos_subtotals(self, subtotais: dict[str, int], row: list[str], mapping: dict[str, int]) -> None:
        row_text = self._row_text(row)
        is_relogio = "relogio" in row_text
        suffix = "_hora_relogio" if is_relogio else ""
        for key in ("ch_ftp", "ch_fgb", "ch_np"):
            value = self._number_from(row, mapping.get(key))
            if value is not None:
                subtotais[f"{key}{suffix}"] = value
        total = self._number_from(row, mapping.get("ch_total"))
        relogio_total = self._number_from(row, mapping.get("ch_relogio"))
        if total is not None:
            subtotais["ch_total_hora_relogio" if is_relogio else "ch_total_hora_aula"] = total
        if relogio_total is not None:
            subtotais["ch_total_hora_relogio"] = relogio_total

    def _update_nucleos_totais(self, totais: dict[str, int], row: list[str], mapping: dict[str, int]) -> None:
        for key in ("ch_ftp", "ch_fgb", "ch_np"):
            value = self._number_from(row, mapping.get(key))
            if value is not None:
                totais[key] = value
        total = self._number_from(row, mapping.get("ch_total"))
        relogio_total = self._number_from(row, mapping.get("ch_relogio"))
        if total is not None:
            totais["ch_total_hora_relogio"] = total
        if relogio_total is not None:
            totais["ch_total_hora_relogio"] = relogio_total

    def _merge_linhas_modelo(self, current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = list(current)
        seen = {item.get("nome") for item in merged}
        for item in incoming:
            if item.get("nome") not in seen:
                merged.append(item)
        return merged

    def _merge_totais(self, current: dict[str, int], incoming: dict[str, int], matrix: dict[str, Any]) -> dict[str, int]:
        merged = dict(current)
        merged.update({key: value for key, value in incoming.items() if value is not None})
        computed_ha = sum(
            comp.get("ch_hora_aula") or 0
            for ano in matrix.get("anos", [])
            for comp in ano.get("componentes", [])
        )
        computed_hr = sum(
            comp.get("ch_hora_relogio_cnct") or 0
            for ano in matrix.get("anos", [])
            for comp in ano.get("componentes", [])
        )
        if computed_ha:
            merged.setdefault("ch_total_hora_aula", computed_ha)
        if computed_hr:
            merged.setdefault("ch_total_hora_relogio", computed_hr)
        if matrix.get("formato") == "nucleos_ftp_fgb_np":
            for key in ("ch_ftp", "ch_fgb", "ch_np"):
                computed = sum(
                    comp.get(key) or 0
                    for ano in matrix.get("anos", [])
                    for comp in ano.get("componentes", [])
                )
                merged.setdefault(key, computed)
        return merged

    def _legacy_matrix_to_markdown(self, matrix: Dict[str, Any]) -> str:
        lines = [
            "| Ano | Componente Curricular | Número de aulas semanais | CH hora-aula no período | CH hora-relógio no período |",
            "|---|---|---:|---:|---:|",
        ]
        for ano in matrix.get("anos", []):
            for comp in ano.get("componentes", []):
                lines.append(self._md_row([
                    ano.get("ano", ""),
                    comp.get("nome", ""),
                    comp.get("aulas_semanais"),
                    comp.get("ch_hora_aula"),
                    comp.get("ch_hora_relogio_cnct"),
                ]))
            subtotais = ano.get("subtotais", {})
            if subtotais:
                lines.append(self._md_row([
                    ano.get("ano", ""),
                    "Subtotal (Total do período)",
                    subtotais.get("aulas_semanais"),
                    subtotais.get("ch_total_hora_aula"),
                    subtotais.get("ch_total_hora_relogio"),
                ]))
        for linha in matrix.get("linhas_modelo", []):
            lines.append(self._md_row([
                linha.get("nome", ""),
                linha.get("nome", ""),
                "",
                linha.get("ch_hora_aula"),
                linha.get("ch_hora_relogio"),
            ]))
        totais = matrix.get("totais", {})
        if totais:
            lines.append(self._md_row([
                "CARGA HORÁRIA TOTAL DO CURSO",
                "CARGA HORÁRIA TOTAL DO CURSO",
                "",
                totais.get("ch_total_hora_aula"),
                totais.get("ch_total_hora_relogio"),
            ]))
        return "\n".join(lines)

    def _nucleos_matrix_to_markdown(self, matrix: Dict[str, Any]) -> str:
        lines = [
            "| Ano | Componente Curricular | No. de aulas semanais | Hora-aula FTP | Hora-aula FGB | Hora-aula NP | Hora-aula TOTAL | Hora relógio TOTAL |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
        for ano in matrix.get("anos", []):
            for comp in ano.get("componentes", []):
                lines.append(self._md_row([
                    self._year_number(ano.get("ano", "")),
                    comp.get("nome", ""),
                    comp.get("aulas_semanais"),
                    comp.get("ch_ftp"),
                    comp.get("ch_fgb"),
                    comp.get("ch_np"),
                    comp.get("ch_hora_aula"),
                    comp.get("ch_hora_relogio_cnct"),
                ]))
            subtotais = ano.get("subtotais", {})
            if subtotais:
                lines.append(self._md_row([
                    "TOTAL ANO HORA-AULA",
                    "TOTAL ANO HORA-AULA",
                    "",
                    subtotais.get("ch_ftp"),
                    subtotais.get("ch_fgb"),
                    subtotais.get("ch_np"),
                    subtotais.get("ch_total_hora_aula"),
                    "",
                ]))
                if any(key.endswith("_hora_relogio") for key in subtotais):
                    lines.append(self._md_row([
                        "TOTAL ANO HORA-RELÓGIO",
                        "TOTAL ANO HORA-RELÓGIO",
                        "",
                        subtotais.get("ch_ftp_hora_relogio"),
                        subtotais.get("ch_fgb_hora_relogio"),
                        subtotais.get("ch_np_hora_relogio"),
                        "",
                        subtotais.get("ch_total_hora_relogio"),
                    ]))
        for linha in matrix.get("linhas_modelo", []):
            lines.append(self._md_row([
                linha.get("nome", ""),
                linha.get("nome", ""),
                "",
                linha.get("ch_ftp"),
                linha.get("ch_fgb"),
                linha.get("ch_np"),
                linha.get("ch_hora_aula"),
                linha.get("ch_hora_relogio"),
            ]))
        totais = matrix.get("totais", {})
        if totais:
            lines.append(self._md_row([
                "C.H. (HORA RELÓGIO) TOTAL DO CURSO",
                "C.H. (HORA RELÓGIO) TOTAL DO CURSO",
                "",
                totais.get("ch_ftp"),
                totais.get("ch_fgb"),
                totais.get("ch_np"),
                totais.get("ch_total_hora_relogio"),
                "",
            ]))
        return "\n".join(lines)

    def _md_row(self, values: Iterable[Any]) -> str:
        return "| " + " | ".join("" if value is None else str(value) for value in values) + " |"

    def _extract_metadata_number(
        self,
        rows: list[list[str]],
        required_terms: tuple[str, ...],
        minimum: int,
        maximum: int,
        default: int,
    ) -> int:
        for row in rows[:12]:
            row_text = self._row_text(row)
            if all(term in row_text for term in required_terms):
                for cell in row:
                    value = self._parse_int(cell)
                    if value is not None and minimum <= value <= maximum:
                        return value
        return default

    def _number_from(self, row: list[str], index: Optional[int]) -> Optional[int]:
        if index is None or index >= len(row):
            return None
        return self._parse_int(row[index])

    def _workload_number_from(self, row: list[str], index: Optional[int]) -> Optional[int]:
        if index is None or index >= len(row):
            return None
        cell = row[index]
        if self._is_model_line(self._norm(cell)):
            return None
        return self._parse_int(cell)

    def _parse_int(self, value: Any) -> Optional[int]:
        text = str(value or "")
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    def _cell(self, row: list[str], index: Optional[int]) -> str:
        if index is None or index >= len(row):
            return ""
        return str(row[index]).strip()

    def _row_has_content(self, row: list[str]) -> bool:
        return any(str(cell).strip() for cell in row)

    def _row_text(self, row: list[str]) -> str:
        return self._norm(" ".join(str(cell) for cell in row))

    def _rows_text(self, rows: list[list[str]]) -> str:
        return self._norm(" ".join(" ".join(str(cell) for cell in row) for row in rows))

    def _norm(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = text.replace("º", "").replace("°", "")
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = re.sub(r"\s+", " ", text)
        return text

    def _normalize_year(self, value: Any) -> Optional[str]:
        text = self._norm(value)
        match = re.fullmatch(r"([1-4])(?:\s*ano)?", text) or re.search(r"\b([1-4])\s*ano\b", text)
        if not match:
            return None
        return f"{match.group(1)}º Ano"

    def _year_number(self, value: Any) -> str:
        ano = self._normalize_year(value)
        if not ano:
            return str(value or "")
        return ano[0]

    def _year_sort_key(self, value: str) -> int:
        ano = self._normalize_year(value)
        return int(ano[0]) if ano else 99

    def _is_non_component_row(self, value: str) -> bool:
        norm = self._norm(value)
        return (
            not norm
            or norm in {"ano", "componente curricular"}
            or "matriz curricular" in norm
            or "legenda" in norm
            or "semanas do ano letivo" in norm
            or "ch em hora-aula" in norm
            or "hora-aula" in norm
            or "hora-relogio" in norm
            or "hora relogio" in norm
            or "formacao geral basica" in norm
        )

    def _is_model_line(self, row_text: str) -> bool:
        return "atividades complementares" in row_text or "estagio supervisionado" in row_text

    def _is_subtotal(self, value_norm: str) -> bool:
        return "subtotal" in value_norm or "total ano" in value_norm or "total do periodo" in value_norm

    def _is_grand_total(self, row_text: str) -> bool:
        return "total do curso" in row_text or "carga horaria total do curso" in row_text
