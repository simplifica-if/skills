from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _extrair_uso_tokens_codex(stdout: str, model: str) -> dict[str, Any] | None:
    for linha in stdout.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if evento.get("type") != "turn.completed":
            continue
        usage = evento.get("usage")
        if not isinstance(usage, dict):
            continue
        input_tokens = int(usage.get("input_tokens") or 0)
        cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        return {
            "metodo": "provider",
            "cli": "codex",
            "provider": "codex",
            "modelo": model,
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "detalhes_provider": usage,
        }
    return None


def executar_prompt_codex(
    prompt_path: Path,
    raw_output_path: Path,
    model: str,
    workdir: Path,
    image_paths: list[Path] | None = None,
) -> dict[str, Any]:
    workdir = workdir.resolve()
    prompt_path = prompt_path.resolve()
    raw_output_path = raw_output_path.resolve()
    prompt = prompt_path.read_text(encoding="utf-8")
    comando = [
        os.environ.get("ANALISE_PPC_CODEX_BIN", "codex"),
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",
        "--output-last-message",
        str(raw_output_path),
        "-C",
        str(workdir),
    ]
    if model and model != "codex-default":
        comando.extend(["-m", model])
    for image_path in image_paths or []:
        comando.extend(["--image", str(Path(image_path).resolve())])
    comando.append("-")

    processo = subprocess.run(
        comando,
        input=prompt,
        text=True,
        capture_output=True,
        cwd=str(workdir),
    )
    if not raw_output_path.exists():
        raw_output_path.write_text(processo.stdout or processo.stderr, encoding="utf-8")
    return {
        "exit_code": processo.returncode,
        "stdout": processo.stdout,
        "stderr": processo.stderr,
        "raw_output_path": str(raw_output_path),
        "command": comando,
        "uso_tokens": _extrair_uso_tokens_codex(processo.stdout, model),
    }
