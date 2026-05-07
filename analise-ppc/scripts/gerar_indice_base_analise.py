from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import BASE_ANALISE_DIR


INDICE_PATH = BASE_ANALISE_DIR / "indice.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _arquivo_relativo(path: Path) -> str:
    return path.relative_to(BASE_ANALISE_DIR).as_posix()


def _item_ficha(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return {
        "categoria": "ficha",
        "id": payload["id"],
        "titulo": payload["titulo"],
        "dominio": payload.get("dominio", ""),
        "criticidade": payload["criticidade"],
        "secoes": payload.get("secoes_preferenciais", []),
        "referencias_normativas": payload.get("referencias_normativas", []),
        "arquivo": _arquivo_relativo(path),
    }


def _item_validacao_cruzada(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return {
        "categoria": "validacao_cruzada",
        "id": payload["id"],
        "titulo": payload["titulo"],
        "dominio": payload.get("dominio", "validacao_cruzada"),
        "criticidade": payload["criticidade"],
        "tipo": payload["tipo"],
        "secoes": payload.get("secoes_relacionadas", []),
        "arquivo": _arquivo_relativo(path),
    }


def _tipo_contrato(path: Path) -> str:
    return path.stem.removesuffix(".exemplo")


def _item_contrato(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return {
        "categoria": "contrato",
        "id": path.stem,
        "titulo": path.name,
        "tipo_contrato": _tipo_contrato(path),
        "campos_raiz": sorted(payload),
        "arquivo": _arquivo_relativo(path),
    }


def gerar_indice(gerado_em: str | None = None) -> dict[str, Any]:
    fichas = [_item_ficha(path) for path in sorted((BASE_ANALISE_DIR / "fichas").glob("*.json"))]
    validacoes = [
        _item_validacao_cruzada(path)
        for path in sorted((BASE_ANALISE_DIR / "validacoes-cruzadas").glob("*.json"))
    ]
    contratos = [_item_contrato(path) for path in sorted((BASE_ANALISE_DIR / "contratos").glob("*.json"))]
    itens = [*fichas, *validacoes, *contratos]
    return {
        "base_analise_dir": "analise-ppc/base-analise",
        "gerado_em": gerado_em or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "resumo": {
            "total_fichas": len(fichas),
            "total_validacoes_cruzadas": len(validacoes),
            "total_contratos": len(contratos),
            "total_itens": len(itens),
        },
        "itens": itens,
    }


def escrever_indice(path: Path = INDICE_PATH) -> dict[str, Any]:
    indice = gerar_indice()
    path.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return indice


def indice_atualizado(path: Path = INDICE_PATH) -> bool:
    if not path.exists():
        return False
    atual = _read_json(path)
    esperado = gerar_indice(gerado_em=str(atual.get("gerado_em", "")))
    return atual == esperado


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar ou verificar o índice consolidado da base de análise.")
    parser.add_argument("--check", action="store_true", help="Verificar se indice.json está atualizado sem reescrever.")
    args = parser.parse_args()

    if args.check:
        if indice_atualizado():
            print(f"OK: {INDICE_PATH}")
            return 0
        print(f"ERRO: {INDICE_PATH} está desatualizado. Rode scripts/gerar_indice_base_analise.py.")
        return 1

    indice = escrever_indice()
    print(
        f"Índice gerado em {INDICE_PATH} "
        f"({indice['resumo']['total_fichas']} fichas, {indice['resumo']['total_itens']} itens)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
