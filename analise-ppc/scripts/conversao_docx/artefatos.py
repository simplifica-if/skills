from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConversaoArtefatos:
    """Artefatos produzidos pela conversão DOCX."""

    output_dir: Path
    markdown: Path | None = None
    markdown_bruto: Path | None = None
    dados: Path | None = None
    matriz_curricular: Path | None = None
    ementario: Path | None = None
