from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import PROMPTS_DIR

OUTPUT_SCHEMA = {
    "batch_id": "string",
    "resultados": [
        {
            "ficha_id": "string",
            "estado": "ATENDE | NAO_ATENDE | INCONCLUSIVO | NAO_APLICAVEL",
            "confianca": "number 0..1",
            "justificativa": "string",
            "evidencias": ["string", "string"],
            "lacunas": ["string"],
            "revisao_humana_obrigatoria": "boolean",
        }
    ],
}

VALIDACOES_CRUZADAS_SCHEMA = {
    "escopo": "validacoes_cruzadas",
    "validacoes": [
        {
            "validacao_id": "string",
            "estado": "ATENDE | NAO_ATENDE | INCONCLUSIVO | NAO_APLICAVEL",
            "confianca": "number 0..1",
            "justificativa": "string",
            "evidencias": ["string", "string"],
            "lacunas": ["string"],
            "revisao_humana_obrigatoria": "boolean",
        }
    ],
}


def _sem_campos_volateis(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            chave: _sem_campos_volateis(valor)
            for chave, valor in payload.items()
            if chave not in {"gerado_em", "executado_em"}
        }
    if isinstance(payload, list):
        return [_sem_campos_volateis(item) for item in payload]
    return payload


def renderizar_prompt_lote(
    metadata: dict[str, Any],
    ppc_markdown: str,
    batch_payload: dict[str, Any],
    pre_validacoes: dict[str, Any] | None = None,
    condicionais_rodada: dict[str, Any] | None = None,
    contexto_estrutural: dict[str, Any] | None = None,
    anexos_visuais: list[dict[str, Any]] | None = None,
    template_path: Path | None = None,
) -> str:
    template = (template_path or PROMPTS_DIR / "lote_fichas.md").read_text(encoding="utf-8")
    substituicoes = {
        "{{METADATA_JSON}}": json.dumps(_sem_campos_volateis(metadata), ensure_ascii=False, indent=2),
        "{{PRE_VALIDACOES_JSON}}": json.dumps(_sem_campos_volateis(pre_validacoes or {}), ensure_ascii=False, indent=2),
        "{{CONDICIONAIS_JSON}}": json.dumps(_sem_campos_volateis(condicionais_rodada or {}), ensure_ascii=False, indent=2),
        "{{CONTEXTO_ESTRUTURAL_JSON}}": json.dumps(_sem_campos_volateis(contexto_estrutural or {}), ensure_ascii=False, indent=2),
        "{{ANEXOS_VISUAIS_JSON}}": json.dumps(_sem_campos_volateis(anexos_visuais or []), ensure_ascii=False, indent=2),
        "{{SCHEMA_JSON}}": json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
        "{{BATCH_JSON}}": json.dumps(batch_payload, ensure_ascii=False, indent=2),
        "{{PPC_MARKDOWN}}": ppc_markdown,
    }
    for marcador, valor in substituicoes.items():
        template = template.replace(marcador, valor)
    return template


def renderizar_prompt_validacoes_cruzadas(
    metadata: dict[str, Any],
    ppc_markdown: str,
    validacoes_payload: dict[str, Any],
    pre_validacoes: dict[str, Any] | None = None,
    condicionais_rodada: dict[str, Any] | None = None,
    contexto_estrutural: dict[str, Any] | None = None,
    template_path: Path | None = None,
) -> str:
    template = (template_path or PROMPTS_DIR / "validacoes_cruzadas.md").read_text(encoding="utf-8")
    substituicoes = {
        "{{METADATA_JSON}}": json.dumps(_sem_campos_volateis(metadata), ensure_ascii=False, indent=2),
        "{{PRE_VALIDACOES_JSON}}": json.dumps(_sem_campos_volateis(pre_validacoes or {}), ensure_ascii=False, indent=2),
        "{{CONDICIONAIS_JSON}}": json.dumps(_sem_campos_volateis(condicionais_rodada or {}), ensure_ascii=False, indent=2),
        "{{CONTEXTO_ESTRUTURAL_JSON}}": json.dumps(_sem_campos_volateis(contexto_estrutural or {}), ensure_ascii=False, indent=2),
        "{{SCHEMA_JSON}}": json.dumps(VALIDACOES_CRUZADAS_SCHEMA, ensure_ascii=False, indent=2),
        "{{VALIDACOES_JSON}}": json.dumps(validacoes_payload, ensure_ascii=False, indent=2),
        "{{PPC_MARKDOWN}}": ppc_markdown,
    }
    for marcador, valor in substituicoes.items():
        template = template.replace(marcador, valor)
    return template
