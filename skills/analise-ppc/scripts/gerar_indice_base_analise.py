from __future__ import annotations

from pathlib import Path

from common import (
    BASE_ANALISE_DIR,
    BASE_ANALISE_INDICE_PATH,
    CONTRATOS_DIR,
    FICHAS_DIR,
    VALIDACOES_CRUZADAS_DIR,
    now_iso,
    read_json,
    write_json,
)


def _item_ficha(caminho: Path) -> dict[str, object]:
    payload = read_json(caminho)
    return {
        "categoria": "ficha",
        "id": payload["id"],
        "titulo": payload["titulo"],
        "dominio": payload.get("dominio"),
        "criticidade": payload.get("criticidade"),
        "secoes": payload.get("secoes_preferenciais", []),
        "referencias_normativas": payload.get("referencias_normativas", []),
        "arquivo": str(caminho.relative_to(BASE_ANALISE_DIR)),
    }


def _item_validacao(caminho: Path) -> dict[str, object]:
    payload = read_json(caminho)
    return {
        "categoria": "validacao_cruzada",
        "id": payload["id"],
        "titulo": payload["titulo"],
        "dominio": payload.get("dominio"),
        "criticidade": payload.get("criticidade"),
        "tipo": payload.get("tipo"),
        "secoes": payload.get("secoes_relacionadas", []),
        "arquivo": str(caminho.relative_to(BASE_ANALISE_DIR)),
    }


def _item_contrato(caminho: Path) -> dict[str, object]:
    payload = read_json(caminho)
    return {
        "categoria": "contrato",
        "id": caminho.stem,
        "titulo": caminho.name,
        "tipo_contrato": (
            "ficha"
            if "ficha" in caminho.stem
            else "batch"
            if "batch" in caminho.stem
            else "resposta_lote"
        ),
        "campos_raiz": sorted(payload.keys()),
        "arquivo": str(caminho.relative_to(BASE_ANALISE_DIR)),
    }


def gerar_indice_base_analise() -> dict[str, object]:
    fichas = [_item_ficha(caminho) for caminho in sorted(FICHAS_DIR.glob("*.json"))]
    validacoes = [_item_validacao(caminho) for caminho in sorted(VALIDACOES_CRUZADAS_DIR.glob("*.json"))]
    contratos = [_item_contrato(caminho) for caminho in sorted(CONTRATOS_DIR.glob("*.json"))]
    payload = {
        "gerado_em": now_iso(),
        "base_analise_dir": str(BASE_ANALISE_DIR.resolve()),
        "resumo": {
            "total_fichas": len(fichas),
            "total_validacoes_cruzadas": len(validacoes),
            "total_contratos": len(contratos),
            "total_itens": len(fichas) + len(validacoes) + len(contratos),
        },
        "itens": fichas + validacoes + contratos,
    }
    write_json(BASE_ANALISE_INDICE_PATH, payload)
    return payload


if __name__ == "__main__":
    indice = gerar_indice_base_analise()
    print(
        "Índice da base de análise gerado: "
        f"{indice['resumo']['total_fichas']} fichas, "
        f"{indice['resumo']['total_validacoes_cruzadas']} validações cruzadas, "
        f"{indice['resumo']['total_contratos']} contratos."
    )
