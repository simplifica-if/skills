from __future__ import annotations

from pathlib import Path
from typing import Any

from providers.codex_cli import executar_prompt_codex
from providers.gemini_cli import executar_prompt_gemini


def executar_prompt(
    prompt_path: Path,
    raw_output_path: Path,
    provider: str,
    model: str,
    workdir: Path,
    image_paths: list[Path] | None = None,
) -> dict[str, Any]:
    provider_normalizado = provider.lower()
    if provider_normalizado == "codex":
        return executar_prompt_codex(prompt_path, raw_output_path, model=model, workdir=workdir, image_paths=image_paths)
    if provider_normalizado == "gemini":
        if image_paths:
            return {
                "exit_code": 2,
                "stdout": "",
                "stderr": "O provider gemini ainda não suporta anexos visuais neste fluxo. Use provider codex para avaliar CT-CURR-10 com imagem.",
                "raw_output_path": str(raw_output_path),
                "command": [],
                "uso_tokens": None,
            }
        return executar_prompt_gemini(prompt_path, raw_output_path, model=model, workdir=workdir)
    raise ValueError(f"Provider não suportado: {provider}")
