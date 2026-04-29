from __future__ import annotations

from pathlib import Path
from typing import Any

FICHA_REPRESENTACAO_GRAFICA = "CT-CURR-10"


def lote_requer_representacao_grafica(batch: dict[str, Any]) -> bool:
    fichas = batch.get("fichas")
    if not isinstance(fichas, list):
        return False
    return any(isinstance(ficha, dict) and ficha.get("id") == FICHA_REPRESENTACAO_GRAFICA for ficha in fichas)


def resolver_anexos_visuais_lote(batch: dict[str, Any], contexto_estrutural: dict[str, Any]) -> list[Path]:
    if not lote_requer_representacao_grafica(batch):
        return []

    representacao = contexto_estrutural.get("representacao_grafica")
    if not isinstance(representacao, dict) or not representacao.get("extraida"):
        return []

    caminho = representacao.get("caminho")
    if not isinstance(caminho, str) or not caminho.strip():
        return []

    imagem = Path(caminho)
    if not imagem.is_absolute():
        artefatos = contexto_estrutural.get("artefatos")
        if not isinstance(artefatos, dict):
            return []
        base = artefatos.get("dados") or artefatos.get("markdown") or artefatos.get("markdown_bruto")
        if not isinstance(base, str) or not base.strip():
            return []
        imagem = Path(base).resolve().parent / imagem

    imagem = imagem.resolve()
    return [imagem] if imagem.exists() else []


def descrever_anexos_visuais_lote(batch: dict[str, Any], anexos: list[Path]) -> list[dict[str, str]]:
    if not lote_requer_representacao_grafica(batch):
        return []
    return [
        {
            "ficha_id": FICHA_REPRESENTACAO_GRAFICA,
            "tipo": "imagem",
            "descricao": "Representação gráfica do processo formativo extraída do PPC.",
            "arquivo": str(anexo.resolve()),
        }
        for anexo in anexos
    ]
