from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    OUTPUT_DIR,
    copy_file,
    ensure_directory,
    extract_identificacao_from_conversion_json,
    infer_identificacao_from_markdown,
    now_iso,
    read_json,
    round_paths,
    safe_relpath,
    timestamp_slug,
    update_manifesto_base,
    write_json,
)


def _criar_rodada(output_base: Path, nome_base: str) -> Path:
    rodada_dir = output_base.resolve() / f"{timestamp_slug()}-{nome_base}"
    sufixo = 2
    while rodada_dir.exists():
        rodada_dir = output_base.resolve() / f"{timestamp_slug()}-{nome_base}-{sufixo}"
        sufixo += 1
    ensure_directory(rodada_dir)
    return rodada_dir


def _preparar_markdown(arquivo: Path, caminhos: dict[str, Path]) -> dict[str, Any]:
    caminho_ppc = copy_file(arquivo, caminhos["ppc"])
    texto = caminho_ppc.read_text(encoding="utf-8")
    identificacao = infer_identificacao_from_markdown(texto, fallback_nome=arquivo.stem)
    return {
        "ppc_path": caminho_ppc,
        "identificacao": identificacao,
    }


def _preparar_docx(arquivo: Path, caminhos: dict[str, Path]) -> dict[str, Any]:
    from conversao_docx import ConversionService

    artefatos_base = caminhos["artefatos_conversao_dir"]
    ensure_directory(artefatos_base)
    artefatos = ConversionService().convert(
        arquivo_docx=arquivo,
        output_dir=artefatos_base,
        verbose=False,
    )
    if artefatos.markdown is None:
        raise RuntimeError("A conversão DOCX não gerou Markdown normalizado.")
    caminho_ppc = copy_file(artefatos.markdown, caminhos["ppc"])
    if artefatos.markdown_bruto:
        copy_file(artefatos.markdown_bruto, caminhos["ppc_bruto"])
    identificacao = infer_identificacao_from_markdown(caminho_ppc.read_text(encoding="utf-8"), fallback_nome=arquivo.stem)
    if artefatos.dados and artefatos.dados.exists():
        try:
            identificacao = extract_identificacao_from_conversion_json(read_json(artefatos.dados), fallback_nome=arquivo.stem)
        except Exception:
            pass
    conversao_docx = {
        "output_dir": str(artefatos.output_dir) if artefatos.output_dir else None,
        "markdown": str(artefatos.markdown) if artefatos.markdown else None,
        "markdown_bruto": str(artefatos.markdown_bruto) if artefatos.markdown_bruto else None,
        "dados": str(artefatos.dados) if artefatos.dados else None,
        "matriz_curricular": str(artefatos.matriz_curricular) if artefatos.matriz_curricular else None,
        "ementario": str(artefatos.ementario) if artefatos.ementario else None,
    }
    write_json(caminhos["preparacao_docx"], conversao_docx)
    return {
        "ppc_path": caminho_ppc,
        "identificacao": identificacao,
        "conversao_docx": conversao_docx,
    }


def preparar_documento(
    arquivo_entrada: Path,
    output_base: Path | None = None,
) -> dict[str, Any]:
    arquivo_entrada = arquivo_entrada.resolve()
    if not arquivo_entrada.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_entrada}")
    if arquivo_entrada.suffix.lower() not in {".md", ".docx"}:
        raise ValueError("A entrada deve ser um arquivo .md ou .docx.")

    rodada_dir = _criar_rodada(output_base or OUTPUT_DIR, arquivo_entrada.stem.lower().replace(" ", "-"))
    caminhos = round_paths(rodada_dir)
    ensure_directory(caminhos["suporte_dir"])

    if arquivo_entrada.suffix.lower() == ".md":
        artefatos = _preparar_markdown(arquivo_entrada, caminhos)
    else:
        artefatos = _preparar_docx(arquivo_entrada, caminhos)

    identificacao = artefatos["identificacao"]
    metadata = {
        "curso": identificacao["curso"],
        "campus": identificacao["campus"],
        "modalidade": identificacao["modalidade"],
        "arquivo_origem": str(arquivo_entrada),
        "ppc_markdown": str(caminhos["ppc"].relative_to(rodada_dir)),
        "rodada_dir": str(rodada_dir.resolve()),
        "suporte_dir": str(caminhos["suporte_dir"].resolve()),
        "criado_em": now_iso(),
    }
    for chave in ("forma_oferta", "modalidade_ensino", "eixo_tecnologico"):
        if identificacao.get(chave):
            metadata[chave] = identificacao[chave]
    if "conversao_docx" in artefatos:
        metadata["artefatos_conversao_docx"] = artefatos["conversao_docx"]

    write_json(caminhos["metadata"], metadata)
    manifesto = update_manifesto_base(rodada_dir=rodada_dir)

    return {
        "rodada_dir": rodada_dir,
        "metadata": caminhos["metadata"],
        "manifesto": caminhos["manifesto"],
        "ppc": caminhos["ppc"],
        "resumo": {
            "rodada_dir": safe_relpath(rodada_dir, Path.cwd()),
            "curso": metadata["curso"],
            "campus": metadata["campus"],
            "modalidade": metadata["modalidade"],
            "ppc_sha256": manifesto["ppc_sha256"],
        },
    }
