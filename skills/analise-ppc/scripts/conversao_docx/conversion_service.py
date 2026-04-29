# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
"""Serviço de conversão DOCX -> artefatos estruturados do PPC."""

from __future__ import annotations

from pathlib import Path

from .artefatos import ConversaoArtefatos


class ConversionService:
    """Converte um PPC DOCX em Markdown e JSONs estruturados."""

    def convert(
        self,
        arquivo_docx: Path,
        output_dir: Path | None = None,
        verbose: bool = False,
    ) -> ConversaoArtefatos:
        arquivo_docx = arquivo_docx.resolve()
        if not arquivo_docx.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_docx}")
        if arquivo_docx.suffix.lower() != ".docx":
            raise ValueError(f"O arquivo deve ser .docx: {arquivo_docx}")

        from .markdown_writer import PPCConverter

        converter = PPCConverter(arquivo_docx)
        converter.convert(verbose=verbose)

        destino = (output_dir or arquivo_docx.with_suffix("")).resolve()
        destino.mkdir(parents=True, exist_ok=True)

        base_name = arquivo_docx.stem
        saved = converter.save(
            md_path=destino / f"{base_name}.md",
            json_path=destino / f"{base_name}_dados.json",
        )

        return ConversaoArtefatos(
            output_dir=destino,
            markdown=Path(saved["markdown"]) if "markdown" in saved else None,
            markdown_bruto=Path(saved["markdown_bruto"]) if "markdown_bruto" in saved else None,
            dados=Path(saved["json"]) if "json" in saved else None,
            matriz_curricular=Path(saved["json_matriz"]) if "json_matriz" in saved else None,
            ementario=Path(saved["json_ementario"]) if "json_ementario" in saved else None,
        )
