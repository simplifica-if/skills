from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_iso, read_json, round_paths, write_json


def _uso_vazio() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def _somar_uso(destino: dict[str, int], uso_tokens: dict[str, Any]) -> None:
    for campo in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
        destino[campo] += int(uso_tokens.get(campo) or 0)


def _cli_item(item: dict[str, Any]) -> str | None:
    uso_tokens = item.get("uso_tokens")
    if isinstance(uso_tokens, dict):
        cli = uso_tokens.get("cli") or uso_tokens.get("provider")
        if cli:
            return str(cli)
    provider = item.get("provider")
    return str(provider) if provider else None


def _modelos_item(item: dict[str, Any]) -> list[str]:
    uso_tokens = item.get("uso_tokens")
    if isinstance(uso_tokens, dict):
        modelos_provider = uso_tokens.get("modelos")
        if isinstance(modelos_provider, dict) and modelos_provider:
            return sorted(str(modelo) for modelo in modelos_provider)
        modelo = uso_tokens.get("modelo")
        if modelo:
            return [str(modelo)]
    modelo = item.get("modelo")
    return [str(modelo)] if modelo else []


def _item_status(status_path: Path, escopo: str) -> dict[str, Any] | None:
    if not status_path.exists():
        return None
    status = read_json(status_path)
    uso_tokens = status.get("uso_tokens")
    if not isinstance(uso_tokens, dict):
        return None
    item = {
        "escopo": escopo,
        "status_path": str(status_path),
        "status": status.get("status"),
        "provider": status.get("provider"),
        "modelo": status.get("modelo"),
        "executado_em": status.get("executado_em"),
        "uso_tokens": uso_tokens,
    }
    if status.get("batch_id"):
        item["batch_id"] = status["batch_id"]
    if status.get("ids"):
        item["ids"] = status["ids"]
    return item


def construir_resumo_uso_tokens(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    itens: list[dict[str, Any]] = []
    totais = _uso_vazio()
    totais_por_escopo: dict[str, dict[str, int]] = {}
    clis: set[str] = set()
    modelos: set[str] = set()
    modelos_por_cli: dict[str, set[str]] = {}

    for status_path in sorted(caminhos["resultados_dir"].glob("batch-*.status.json")):
        item = _item_status(status_path, "lote")
        if item:
            itens.append(item)

    item_cruzadas = _item_status(caminhos["validacoes_cruzadas_status"], "validacoes_cruzadas")
    if item_cruzadas:
        itens.append(item_cruzadas)

    for status_path in sorted(caminhos["execucoes_avulsas_fichas_dir"].glob("*/status.json")):
        item = _item_status(status_path, "reavaliacao_fichas")
        if item:
            itens.append(item)

    for status_path in sorted(caminhos["execucoes_avulsas_validacoes_dir"].glob("*/status.json")):
        item = _item_status(status_path, "reavaliacao_validacoes_cruzadas")
        if item:
            itens.append(item)

    for item in itens:
        escopo = str(item["escopo"])
        uso_tokens = item["uso_tokens"]
        if escopo not in totais_por_escopo:
            totais_por_escopo[escopo] = _uso_vazio()
        _somar_uso(totais, uso_tokens)
        _somar_uso(totais_por_escopo[escopo], uso_tokens)
        cli = _cli_item(item)
        modelos_item = _modelos_item(item)
        if cli:
            clis.add(cli)
            modelos_por_cli.setdefault(cli, set()).update(modelos_item)
        modelos.update(modelos_item)

    return {
        "rodada_dir": str(caminhos["rodada_dir"]),
        "gerado_em": now_iso(),
        "metodo": "provider",
        "total_execucoes_com_uso": len(itens),
        "clis": sorted(clis),
        "modelos": sorted(modelos),
        "modelos_por_cli": {cli: sorted(modelos_cli) for cli, modelos_cli in sorted(modelos_por_cli.items())},
        "totais": totais,
        "totais_por_escopo": totais_por_escopo,
        "itens": itens,
    }


def atualizar_uso_tokens_rodada(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    resumo = construir_resumo_uso_tokens(rodada_dir)
    write_json(caminhos["uso_tokens"], resumo)
    return resumo
