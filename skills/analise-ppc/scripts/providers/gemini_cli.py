from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _normalizar_uso_tokens_gemini(stats: dict[str, Any], model: str) -> dict[str, Any] | None:
    modelos = stats.get("models")
    if not isinstance(modelos, dict):
        return None

    detalhes_modelos: dict[str, Any] = {}
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    for nome_modelo, payload_modelo in modelos.items():
        if not isinstance(payload_modelo, dict):
            continue
        tokens = payload_modelo.get("tokens")
        if not isinstance(tokens, dict):
            continue
        prompt_tokens = int(tokens.get("prompt") or tokens.get("input") or 0)
        cached_tokens = int(tokens.get("cached") or 0)
        candidate_tokens = int(tokens.get("candidates") or 0)
        thought_tokens = int(tokens.get("thoughts") or 0)
        tool_tokens = int(tokens.get("tool") or 0)
        total_modelo = int(tokens.get("total") or (prompt_tokens + candidate_tokens + thought_tokens + tool_tokens))
        output_modelo = candidate_tokens + thought_tokens + tool_tokens

        input_tokens += prompt_tokens
        cached_input_tokens += cached_tokens
        output_tokens += output_modelo
        total_tokens += total_modelo
        detalhes_modelos[str(nome_modelo)] = {
            "input_tokens": prompt_tokens,
            "cached_input_tokens": cached_tokens,
            "output_tokens": output_modelo,
            "total_tokens": total_modelo,
            "detalhes_provider": tokens,
        }

    if not detalhes_modelos:
        return None

    return {
        "metodo": "provider",
        "cli": "gemini",
        "provider": "gemini",
        "modelo": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "modelos": detalhes_modelos,
    }


def executar_prompt_gemini(
    prompt_path: Path,
    raw_output_path: Path,
    model: str,
    workdir: Path,
) -> dict[str, Any]:
    prompt = prompt_path.read_text(encoding="utf-8")
    comando = [
        os.environ.get("ANALISE_PPC_GEMINI_BIN", "gemini"),
        "--prompt",
        "",
        "--output-format",
        "json",
    ]
    if model and model != "gemini-default":
        comando.extend(["-m", model])
    processo = subprocess.run(
        comando,
        input=prompt,
        text=True,
        capture_output=True,
        cwd=str(workdir),
    )
    uso_tokens = None
    try:
        payload = json.loads(processo.stdout) if processo.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    resposta = payload.get("response") if isinstance(payload, dict) else None
    if isinstance(resposta, str):
        raw_output_path.write_text(resposta, encoding="utf-8")
    else:
        raw_output_path.write_text(processo.stdout or processo.stderr, encoding="utf-8")

    stats = payload.get("stats") if isinstance(payload, dict) else None
    if isinstance(stats, dict):
        uso_tokens = _normalizar_uso_tokens_gemini(stats, model)

    return {
        "exit_code": processo.returncode,
        "stdout": processo.stdout,
        "stderr": processo.stderr,
        "raw_output_path": str(raw_output_path),
        "command": comando,
        "uso_tokens": uso_tokens,
    }
