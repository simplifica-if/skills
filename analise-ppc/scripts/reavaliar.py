from __future__ import annotations

from pathlib import Path
from typing import Any

from avaliar_cruzadas import validar_resposta_validacoes_cruzadas
from avaliar_lote import validar_resposta_lote
from consolidar_resultados import consolidar_rodada
from gerar_relatorio_html import gerar_relatorio_html
from pre_validacoes import carregar_contexto_estrutural
from providers import executar_prompt
from providers.prompt_builder import renderizar_prompt_lote, renderizar_prompt_validacoes_cruzadas
from providers.response_parser import extrair_json_de_resposta
from uso_tokens import atualizar_uso_tokens_rodada
from common import (
    VALIDACOES_CRUZADAS_DIR,
    FICHAS_DIR,
    load_fichas,
    load_validacoes_cruzadas,
    now_iso,
    read_json,
    round_paths,
    sha256_file,
    sha256_json_payload,
    sha256_text,
    write_json,
    write_text,
)


class ErroReavaliacao(ValueError):
    pass


def _verificar_ids_unicos(ids: list[str], tipo: str) -> None:
    vistos: set[str] = set()
    duplicados: list[str] = []
    for item_id in ids:
        if item_id in vistos and item_id not in duplicados:
            duplicados.append(item_id)
        vistos.add(item_id)
    if duplicados:
        raise ErroReavaliacao(f"{tipo} duplicados: " + ", ".join(duplicados))


def _selecionar_por_id(catalogo: list[dict[str, Any]], ids: list[str], tipo: str) -> list[dict[str, Any]]:
    _verificar_ids_unicos(ids, tipo)
    por_id = {item["id"]: item for item in catalogo}
    faltantes = [item_id for item_id in ids if item_id not in por_id]
    if faltantes:
        raise ErroReavaliacao(f"{tipo} não encontrados: " + ", ".join(faltantes))
    return [por_id[item_id] for item_id in ids]


def _execution_id(prefixo: str, ids: list[str], itens: list[dict[str, Any]]) -> str:
    payload = {
        "ids": ids,
        "itens_sha256": [sha256_json_payload(item) for item in itens],
    }
    return f"avulso-{prefixo}-{sha256_json_payload(payload)[:12]}"


def _ler_indice(path: Path) -> dict[str, Any]:
    if path.exists():
        payload = read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("itens"), dict):
            return payload
    return {"gerado_em": now_iso(), "itens": {}}


def _atualizar_indice(path: Path, entradas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = _ler_indice(path)
    payload["gerado_em"] = now_iso()
    payload["itens"].update(entradas)
    write_json(path, payload)
    return payload


def _status_em_dia(
    status: dict[str, Any],
    *,
    ppc_sha256: str,
    selecao_sha256: str,
    prompt_sha256: str,
    provider: str,
    model: str,
) -> bool:
    return (
        status.get("status") == "ok"
        and status.get("ppc_sha256") == ppc_sha256
        and status.get("selecao_sha256") == selecao_sha256
        and status.get("prompt_sha256") == prompt_sha256
        and status.get("provider") == provider
        and status.get("modelo") == model
    )


def _resposta_em_dia(status: dict[str, Any], resposta: dict[str, Any]) -> bool:
    resposta_sha256 = status.get("resposta_sha256")
    return not resposta_sha256 or resposta_sha256 == sha256_json_payload(resposta)


def _carregar_contexto(rodada_dir: Path) -> dict[str, Any]:
    contexto = carregar_contexto_estrutural(rodada_dir)
    return {
        "pre_validacoes": contexto["pre_validacoes"],
        "condicionais_rodada": contexto["condicionais_rodada"],
        "contexto_estrutural": contexto["contexto_estrutural"],
    }


def _executar_fichas_avulsas(
    rodada_dir: Path,
    ficha_ids: list[str],
    provider: str,
    model: str,
    forcar: bool,
) -> dict[str, Any] | None:
    if not ficha_ids:
        return None

    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    ppc_markdown = caminhos["ppc"].read_text(encoding="utf-8")
    contexto = _carregar_contexto(rodada_dir)
    fichas = _selecionar_por_id(load_fichas(FICHAS_DIR), ficha_ids, "Fichas")
    batch_id = _execution_id("fichas", ficha_ids, fichas)
    batch = {
        "batch_id": batch_id,
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    exec_dir = caminhos["execucoes_avulsas_fichas_dir"] / batch_id
    prompt_path = exec_dir / "prompt.md"
    raw_path = exec_dir / "resposta-bruta.md"
    resposta_path = exec_dir / "resposta.json"
    status_path = exec_dir / "status.json"

    prompt_text = renderizar_prompt_lote(
        metadata,
        ppc_markdown,
        batch,
        pre_validacoes=contexto["pre_validacoes"],
        condicionais_rodada=contexto["condicionais_rodada"],
        contexto_estrutural=contexto["contexto_estrutural"],
    )
    write_text(prompt_path, prompt_text)
    ppc_sha256 = sha256_file(caminhos["ppc"])
    selecao_sha256 = sha256_json_payload(batch)
    prompt_sha256 = sha256_text(prompt_text)

    if status_path.exists() and resposta_path.exists() and not forcar:
        status_existente = read_json(status_path)
        if _status_em_dia(
            status_existente,
            ppc_sha256=ppc_sha256,
            selecao_sha256=selecao_sha256,
            prompt_sha256=prompt_sha256,
            provider=provider,
            model=model,
        ):
            resposta = read_json(resposta_path)
            if _resposta_em_dia(status_existente, resposta):
                try:
                    resposta_validada = validar_resposta_lote(batch, resposta)
                    _registrar_sobreposicoes_fichas(rodada_dir, fichas, resposta_validada, status_existente, exec_dir)
                    return status_existente
                except Exception:  # noqa: BLE001
                    pass

    execucao = executar_prompt(prompt_path, raw_path, provider, model, rodada_dir)
    status = "ok"
    erro = None
    fichas_recebidas = 0
    resposta_validada: dict[str, Any] | None = None
    if execucao["exit_code"] != 0:
        status = "erro_cli"
        erro = execucao["stderr"] or execucao["stdout"] or "A CLI do provider falhou."
    else:
        try:
            resposta_json = extrair_json_de_resposta(raw_path.read_text(encoding="utf-8") if raw_path.exists() else "")
            fichas_recebidas = len(resposta_json.get("resultados", [])) if isinstance(resposta_json.get("resultados"), list) else 0
            resposta_validada = validar_resposta_lote(batch, resposta_json)
            write_json(resposta_path, resposta_validada)
        except Exception as exc:  # noqa: BLE001
            status = "erro_validacao"
            erro = str(exc)

    status_payload = {
        "escopo": "reavaliacao_fichas",
        "batch_id": batch_id,
        "status": status,
        "provider": provider,
        "modelo": model,
        "ppc_sha256": ppc_sha256,
        "selecao_sha256": selecao_sha256,
        "prompt_sha256": prompt_sha256,
        "fichas_esperadas": len(fichas),
        "fichas_recebidas": fichas_recebidas,
        "ids": ficha_ids,
        "executado_em": now_iso(),
    }
    if resposta_validada is not None:
        status_payload["resposta_sha256"] = sha256_json_payload(resposta_validada)
    if execucao.get("uso_tokens"):
        status_payload["uso_tokens"] = execucao["uso_tokens"]
    if erro:
        status_payload["erro"] = erro
    write_json(status_path, status_payload)
    if status == "ok" and resposta_validada:
        _registrar_sobreposicoes_fichas(rodada_dir, fichas, resposta_validada, status_payload, exec_dir)
    return status_payload


def _registrar_sobreposicoes_fichas(
    rodada_dir: Path,
    fichas: list[dict[str, Any]],
    resposta: dict[str, Any],
    status: dict[str, Any],
    exec_dir: Path,
) -> None:
    caminhos = round_paths(rodada_dir)
    fichas_por_id = {ficha["id"]: ficha for ficha in fichas}
    entradas: dict[str, dict[str, Any]] = {}
    for resultado in resposta.get("resultados", []):
        ficha_id = resultado["ficha_id"]
        entradas[ficha_id] = {
            "id": ficha_id,
            "status": "ok",
            "resultado": resultado,
            "ppc_sha256": status["ppc_sha256"],
            "item_sha256": sha256_json_payload(fichas_por_id[ficha_id]),
            "prompt_sha256": status["prompt_sha256"],
            "resposta_sha256": status.get("resposta_sha256") or sha256_json_payload(resposta),
            "provider": status["provider"],
            "modelo": status["modelo"],
            "executado_em": status["executado_em"],
            "execucao_path": str(exec_dir),
            "resposta_path": str(exec_dir / "resposta.json"),
        }
    _atualizar_indice(caminhos["sobreposicoes_fichas"], entradas)


def _executar_validacoes_avulsas(
    rodada_dir: Path,
    validacao_ids: list[str],
    provider: str,
    model: str,
    forcar: bool,
) -> dict[str, Any] | None:
    if not validacao_ids:
        return None

    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    ppc_markdown = caminhos["ppc"].read_text(encoding="utf-8")
    contexto = _carregar_contexto(rodada_dir)
    validacoes = _selecionar_por_id(load_validacoes_cruzadas(VALIDACOES_CRUZADAS_DIR), validacao_ids, "Validações")
    exec_id = _execution_id("validacoes", validacao_ids, validacoes)
    catalogo = {
        "escopo": "validacoes_cruzadas_avulsas",
        "total_validacoes": len(validacoes),
        "validacoes": validacoes,
    }
    exec_dir = caminhos["execucoes_avulsas_validacoes_dir"] / exec_id
    prompt_path = exec_dir / "prompt.md"
    raw_path = exec_dir / "resposta-bruta.md"
    resposta_path = exec_dir / "resposta.json"
    status_path = exec_dir / "status.json"
    catalogo_path = exec_dir / "catalogo.json"

    prompt_text = renderizar_prompt_validacoes_cruzadas(
        metadata,
        ppc_markdown,
        catalogo,
        pre_validacoes=contexto["pre_validacoes"],
        condicionais_rodada=contexto["condicionais_rodada"],
        contexto_estrutural=contexto["contexto_estrutural"],
    )
    write_json(catalogo_path, catalogo)
    write_text(prompt_path, prompt_text)
    ppc_sha256 = sha256_file(caminhos["ppc"])
    selecao_sha256 = sha256_json_payload(catalogo)
    prompt_sha256 = sha256_text(prompt_text)

    if status_path.exists() and resposta_path.exists() and not forcar:
        status_existente = read_json(status_path)
        if _status_em_dia(
            status_existente,
            ppc_sha256=ppc_sha256,
            selecao_sha256=selecao_sha256,
            prompt_sha256=prompt_sha256,
            provider=provider,
            model=model,
        ):
            resposta = read_json(resposta_path)
            if _resposta_em_dia(status_existente, resposta):
                try:
                    resposta_validada = validar_resposta_validacoes_cruzadas(catalogo, resposta, provider, model)
                    _registrar_sobreposicoes_validacoes(rodada_dir, validacoes, resposta_validada, status_existente, exec_dir)
                    return status_existente
                except Exception:  # noqa: BLE001
                    pass

    execucao = executar_prompt(prompt_path, raw_path, provider, model, rodada_dir)
    status = "ok"
    erro = None
    validacoes_recebidas = 0
    resposta_validada: dict[str, Any] | None = None
    if execucao["exit_code"] != 0:
        status = "erro_cli"
        erro = execucao["stderr"] or execucao["stdout"] or "A CLI do provider falhou."
    else:
        try:
            resposta_json = extrair_json_de_resposta(raw_path.read_text(encoding="utf-8") if raw_path.exists() else "")
            validacoes_recebidas = len(resposta_json.get("validacoes", []) or resposta_json.get("resultados", []))
            resposta_validada = validar_resposta_validacoes_cruzadas(catalogo, resposta_json, provider, model)
            write_json(resposta_path, resposta_validada)
        except Exception as exc:  # noqa: BLE001
            status = "erro_validacao"
            erro = str(exc)

    status_payload = {
        "escopo": "reavaliacao_validacoes_cruzadas",
        "status": status,
        "provider": provider,
        "modelo": model,
        "ppc_sha256": ppc_sha256,
        "selecao_sha256": selecao_sha256,
        "prompt_sha256": prompt_sha256,
        "validacoes_esperadas": len(validacoes),
        "validacoes_recebidas": validacoes_recebidas,
        "ids": validacao_ids,
        "executado_em": now_iso(),
    }
    if resposta_validada is not None:
        status_payload["resposta_sha256"] = sha256_json_payload(resposta_validada)
    if execucao.get("uso_tokens"):
        status_payload["uso_tokens"] = execucao["uso_tokens"]
    if erro:
        status_payload["erro"] = erro
    write_json(status_path, status_payload)
    if status == "ok" and resposta_validada:
        _registrar_sobreposicoes_validacoes(rodada_dir, validacoes, resposta_validada, status_payload, exec_dir)
    return status_payload


def _registrar_sobreposicoes_validacoes(
    rodada_dir: Path,
    validacoes: list[dict[str, Any]],
    resposta: dict[str, Any],
    status: dict[str, Any],
    exec_dir: Path,
) -> None:
    caminhos = round_paths(rodada_dir)
    validacoes_por_id = {validacao["id"]: validacao for validacao in validacoes}
    entradas: dict[str, dict[str, Any]] = {}
    for resultado in resposta.get("validacoes", []):
        validacao_id = resultado["id"]
        entradas[validacao_id] = {
            "id": validacao_id,
            "status": "ok",
            "resultado": resultado,
            "ppc_sha256": status["ppc_sha256"],
            "item_sha256": sha256_json_payload(validacoes_por_id[validacao_id]),
            "prompt_sha256": status["prompt_sha256"],
            "resposta_sha256": status.get("resposta_sha256") or sha256_json_payload(resposta),
            "provider": status["provider"],
            "modelo": status["modelo"],
            "executado_em": status["executado_em"],
            "execucao_path": str(exec_dir),
            "resposta_path": str(exec_dir / "resposta.json"),
        }
    _atualizar_indice(caminhos["sobreposicoes_validacoes_cruzadas"], entradas)


def reavaliar_rodada(
    rodada_dir: Path,
    ficha_ids: list[str] | None = None,
    validacao_ids: list[str] | None = None,
    provider: str = "codex",
    model: str = "codex-default",
    forcar: bool = False,
    gerar_relatorio: bool = True,
) -> dict[str, Any]:
    ficha_ids = list(ficha_ids or [])
    validacao_ids = list(validacao_ids or [])
    if not ficha_ids and not validacao_ids:
        raise ErroReavaliacao("Informe ao menos um --ficha-id ou --validacao-id.")

    status_fichas = _executar_fichas_avulsas(rodada_dir, ficha_ids, provider, model, forcar)
    status_validacoes = _executar_validacoes_avulsas(rodada_dir, validacao_ids, provider, model, forcar)
    status_itens = [item for item in (status_fichas, status_validacoes) if item is not None]
    uso_tokens = atualizar_uso_tokens_rodada(rodada_dir)

    payload: dict[str, Any] = {
        "rodada_dir": str(rodada_dir.resolve()),
        "status": status_itens,
        "uso_tokens": uso_tokens,
        "consolidado": None,
        "relatorio_html": None,
    }
    if gerar_relatorio and all(item.get("status") == "ok" for item in status_itens):
        consolidado = consolidar_rodada(rodada_dir)
        relatorio = gerar_relatorio_html(rodada_dir)
        payload["consolidado"] = {
            "resultados_fichas": str(consolidado["resultados_fichas"]),
            "achados": str(consolidado["achados"]),
            "parecer_final": str(consolidado["parecer_final"]),
            "situacao": consolidado["parecer"]["situacao"],
        }
        relatorio_html = relatorio["relatorio_html"].resolve()
        payload["relatorio_html"] = str(relatorio_html)
        payload["relatorio_url"] = relatorio_html.as_uri()
    return payload
