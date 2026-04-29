from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from common import TEMPLATES_DIR, read_json


def _escape_script_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _classe_valor(valor: str) -> str:
    return valor.lower().replace("_", "-")


def gerar_relatorio_html(rodada_dir: Path) -> dict[str, Path]:
    metadata = read_json(rodada_dir / "metadata.json")
    resultados = read_json(rodada_dir / "resultados-fichas.json")
    achados = read_json(rodada_dir / "achados.json")
    parecer = read_json(rodada_dir / "parecer-final.json")
    pre_validacoes = read_json(rodada_dir / "pre-validacoes.json") if (rodada_dir / "pre-validacoes.json").exists() else {}
    condicionais_rodada = read_json(rodada_dir / "condicionais-rodada.json") if (rodada_dir / "condicionais-rodada.json").exists() else {}
    contexto_estrutural = read_json(rodada_dir / "contexto-estrutural.json") if (rodada_dir / "contexto-estrutural.json").exists() else {}
    validacoes_cruzadas = read_json(rodada_dir / "validacoes-cruzadas.json") if (rodada_dir / "validacoes-cruzadas.json").exists() else {}
    uso_tokens = read_json(rodada_dir / "uso-tokens.json") if (rodada_dir / "uso-tokens.json").exists() else {}

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

    destino = rodada_dir / "relatorio-analise.html"
    destino.write_text(html, encoding="utf-8")
    return {"relatorio_html": destino}
