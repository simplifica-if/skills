from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from common import TEMPLATES_DIR, read_json, round_paths


def _escape_script_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _classe_valor(valor: str) -> str:
    return valor.lower().replace("_", "-")


def gerar_relatorio_html(rodada_dir: Path) -> dict[str, Path]:
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    resultados = read_json(caminhos["resultados_fichas"])
    achados = read_json(caminhos["achados"])
    parecer = read_json(caminhos["parecer_final"])
    pre_validacoes = read_json(caminhos["pre_validacoes"]) if caminhos["pre_validacoes"].exists() else {}
    condicionais_rodada = read_json(caminhos["condicionais_rodada"]) if caminhos["condicionais_rodada"].exists() else {}
    contexto_estrutural = read_json(caminhos["contexto_estrutural"]) if caminhos["contexto_estrutural"].exists() else {}
    validacoes_cruzadas = read_json(caminhos["validacoes_cruzadas"]) if caminhos["validacoes_cruzadas"].exists() else {}
    uso_tokens = read_json(caminhos["uso_tokens"]) if caminhos["uso_tokens"].exists() else {}

    template_html = (TEMPLATES_DIR / "relatorio.html").read_text(encoding="utf-8")
    template_css = (TEMPLATES_DIR / "relatorio.css").read_text(encoding="utf-8")
    template_js = (TEMPLATES_DIR / "relatorio.js").read_text(encoding="utf-8")

    substituicoes = {
        "{{TITLE}}": escape(f"Relatório de análise · {metadata['curso']}"),
        "{{CURSO}}": escape(metadata["curso"]),
        "{{CAMPUS}}": escape(metadata["campus"]),
        "{{MODALIDADE}}": escape(metadata["modalidade"]),
        "{{RODADA_DIR}}": escape(metadata["rodada_dir"]),
        "{{RESUMO}}": escape(parecer["resumo"]),
        "{{SITUACAO}}": escape(parecer["situacao"]),
        "{{SITUACAO_CLASSE}}": escape(_classe_valor(parecer["situacao"])),
        "{{TOTAL_FICHAS}}": str(resultados["totais"]["fichas"]),
        "{{TOTAL_ACHADOS}}": str(len(achados["achados"])),
        "{{CSS}}": template_css,
        "{{JS}}": template_js,
        "{{REPORT_DATA}}": _escape_script_json(
            {
                "metadata": metadata,
                "resultados": resultados,
                "achados": achados,
                "parecer": parecer,
                "pre_validacoes": pre_validacoes,
                "condicionais_rodada": condicionais_rodada,
                "contexto_estrutural": contexto_estrutural,
                "validacoes_cruzadas": validacoes_cruzadas,
                "uso_tokens": uso_tokens,
            }
        ),
    }
    html = template_html
    for marcador, valor in substituicoes.items():
        html = html.replace(marcador, valor)

    destino = caminhos["relatorio_html"]
    destino.write_text(html, encoding="utf-8")
    return {"relatorio_html": destino}
