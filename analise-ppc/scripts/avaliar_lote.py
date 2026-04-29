from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anexos_visuais import descrever_anexos_visuais_lote, resolver_anexos_visuais_lote
from pre_validacoes import carregar_contexto_estrutural, verificar_bloqueios_pre_validacao
from providers import executar_prompt
from providers.prompt_builder import renderizar_prompt_lote
from providers.response_parser import extrair_json_de_resposta
from uso_tokens import atualizar_uso_tokens_rodada
from common import (
    now_iso,
    read_json,
    round_paths,
    sha256_file,
    sha256_text,
    write_json,
    write_text,
)


class ErroRespostaIncompleta(ValueError):
    pass


class ErroValidacaoResposta(ValueError):
    pass


@dataclass
class FingerprintsLote:
    ppc_sha256: str
    batch_sha256: str
    prompt_sha256: str
    anexos_visuais_sha256: list[str]
    provider: str
    model: str


def _status_path(resultados_dir: Path, batch_id: str) -> Path:
    return resultados_dir / f"{batch_id}.status.json"


def _response_path(resultados_dir: Path, batch_id: str) -> Path:
    return resultados_dir / f"{batch_id}.resposta.json"


def _raw_path(resultados_dir: Path, batch_id: str) -> Path:
    return resultados_dir / f"{batch_id}.resposta-bruta.md"


def _prompt_path(resultados_dir: Path, batch_id: str) -> Path:
    return resultados_dir / f"{batch_id}.prompt.md"


def _carregar_insumos(rodada_dir: Path, batch_id: str) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    batch_path = caminhos["batches_dir"] / f"{batch_id}.json"
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch não encontrado: {batch_path}")
    contexto_estrutural = carregar_contexto_estrutural(rodada_dir)
    return {
        "caminhos": caminhos,
        "metadata": read_json(caminhos["metadata"]),
        "batch": read_json(batch_path),
        "batch_path": batch_path,
        "ppc_markdown": caminhos["ppc"].read_text(encoding="utf-8"),
        "pre_validacoes": contexto_estrutural["pre_validacoes"],
        "condicionais_rodada": contexto_estrutural["condicionais_rodada"],
        "contexto_estrutural": contexto_estrutural["contexto_estrutural"],
    }


def _construir_fingerprints(
    caminhos: dict[str, Path],
    batch_path: Path,
    prompt_text: str,
    anexos_visuais: list[Path],
    provider: str,
    model: str,
) -> FingerprintsLote:
    return FingerprintsLote(
        ppc_sha256=sha256_file(caminhos["ppc"]),
        batch_sha256=sha256_file(batch_path),
        prompt_sha256=sha256_text(prompt_text),
        anexos_visuais_sha256=[sha256_file(anexo) for anexo in anexos_visuais],
        provider=provider,
        model=model,
    )


def _status_em_dia(status_payload: dict[str, Any], fingerprints: FingerprintsLote) -> bool:
    return (
        status_payload.get("status") == "ok"
        and status_payload.get("ppc_sha256") == fingerprints.ppc_sha256
        and status_payload.get("batch_sha256") == fingerprints.batch_sha256
        and status_payload.get("prompt_sha256") == fingerprints.prompt_sha256
        and status_payload.get("anexos_visuais_sha256", []) == fingerprints.anexos_visuais_sha256
        and status_payload.get("provider") == fingerprints.provider
        and status_payload.get("modelo") == fingerprints.model
    )


def _marcar_desatualizado(status_path: Path, batch: dict[str, Any], fingerprints: FingerprintsLote) -> dict[str, Any]:
    status_payload = {
        "batch_id": batch["batch_id"],
        "status": "desatualizado",
        "provider": fingerprints.provider,
        "modelo": fingerprints.model,
        "ppc_sha256": fingerprints.ppc_sha256,
        "batch_sha256": fingerprints.batch_sha256,
        "prompt_sha256": fingerprints.prompt_sha256,
        "anexos_visuais_sha256": fingerprints.anexos_visuais_sha256,
        "fichas_esperadas": len(batch["fichas"]),
        "fichas_recebidas": 0,
        "executado_em": now_iso(),
        "erro": "Os fingerprints atuais divergem da última execução válida.",
    }
    write_json(status_path, status_payload)
    return status_payload


def validar_resposta_lote(batch: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ErroValidacaoResposta("A resposta normalizada precisa ser um objeto JSON.")
    if not payload.get("batch_id"):
        raise ErroValidacaoResposta("A resposta não contém `batch_id`.")
    if payload["batch_id"] != batch["batch_id"]:
        raise ErroValidacaoResposta("O `batch_id` da resposta não corresponde ao lote avaliado.")
    resultados = payload.get("resultados")
    if not isinstance(resultados, list):
        raise ErroValidacaoResposta("A resposta não contém uma lista `resultados` válida.")

    fichas_por_id = {ficha["id"]: ficha for ficha in batch["fichas"]}
    vistos: set[str] = set()
    normalizados: list[dict[str, Any]] = []

    for item in resultados:
        if not isinstance(item, dict):
            raise ErroValidacaoResposta("Cada resultado precisa ser um objeto JSON.")
        ficha_id = item.get("ficha_id")
        if not ficha_id:
            raise ErroValidacaoResposta("Um item do lote não contém `ficha_id`.")
        if ficha_id not in fichas_por_id:
            raise ErroRespostaIncompleta(f"Foi recebido `ficha_id` estranho ao lote: {ficha_id}")
        if ficha_id in vistos:
            raise ErroRespostaIncompleta(f"Foi recebido `ficha_id` duplicado: {ficha_id}")
        vistos.add(ficha_id)

        ficha = fichas_por_id[ficha_id]
        estado = item.get("estado")
        if estado not in ficha.get("estados_permitidos", []):
            raise ErroValidacaoResposta(f"Estado inválido para {ficha_id}: {estado}")

        confianca = item.get("confianca")
        if not isinstance(confianca, (int, float)) or not (0 <= float(confianca) <= 1):
            raise ErroValidacaoResposta(f"Confianca inválida para {ficha_id}: {confianca}")

        justificativa = item.get("justificativa")
        if not isinstance(justificativa, str) or not justificativa.strip():
            raise ErroValidacaoResposta(f"`justificativa` inválida para {ficha_id}")

        evidencias = item.get("evidencias")
        if not isinstance(evidencias, list):
            raise ErroValidacaoResposta(f"`evidencias` inválida para {ficha_id}")
        evidencias_normalizadas = [str(evidencia).strip() for evidencia in evidencias if str(evidencia).strip()]
        if len(evidencias_normalizadas) < int(ficha.get("evidencia_minima", 1)):
            raise ErroValidacaoResposta(f"{ficha_id} trouxe menos evidências que o mínimo exigido.")

        lacunas = item.get("lacunas")
        if not isinstance(lacunas, list):
            raise ErroValidacaoResposta(f"`lacunas` inválida para {ficha_id}")

        revisao_humana = item.get("revisao_humana_obrigatoria")
        if not isinstance(revisao_humana, bool):
            raise ErroValidacaoResposta(f"`revisao_humana_obrigatoria` inválido para {ficha_id}")

        normalizados.append(
            {
                "ficha_id": ficha_id,
                "estado": estado,
                "confianca": float(confianca),
                "justificativa": justificativa.strip(),
                "evidencias": evidencias_normalizadas,
                "lacunas": [str(lacuna).strip() for lacuna in lacunas if str(lacuna).strip()],
                "revisao_humana_obrigatoria": revisao_humana,
                "secoes_preferenciais": list(ficha.get("secoes_preferenciais", [])),
            }
        )

    faltantes = [ficha_id for ficha_id in fichas_por_id if ficha_id not in vistos]
    if faltantes:
        raise ErroRespostaIncompleta(f"Fichas sem resposta no lote: {', '.join(sorted(faltantes))}")

    return {
        "batch_id": batch["batch_id"],
        "resultados": normalizados,
    }


def avaliar_lote(
    rodada_dir: Path,
    batch_id: str,
    provider: str,
    model: str,
    forcar: bool = False,
) -> dict[str, Any]:
    insumos = _carregar_insumos(rodada_dir, batch_id)
    caminhos = insumos["caminhos"]
    batch = insumos["batch"]
    resultados_dir = caminhos["resultados_dir"]
    status_path = _status_path(resultados_dir, batch_id)
    resposta_path = _response_path(resultados_dir, batch_id)
    resposta_bruta_path = _raw_path(resultados_dir, batch_id)
    prompt_path = _prompt_path(resultados_dir, batch_id)
    anexos_visuais_paths = resolver_anexos_visuais_lote(batch, insumos.get("contexto_estrutural") or {})
    anexos_visuais = descrever_anexos_visuais_lote(batch, anexos_visuais_paths)

    prompt_text = renderizar_prompt_lote(
        insumos["metadata"],
        insumos["ppc_markdown"],
        batch,
        pre_validacoes=insumos.get("pre_validacoes"),
        condicionais_rodada=insumos.get("condicionais_rodada"),
        contexto_estrutural=insumos.get("contexto_estrutural"),
        anexos_visuais=anexos_visuais,
    )
    write_text(prompt_path, prompt_text)
    fingerprints = _construir_fingerprints(caminhos, insumos["batch_path"], prompt_text, anexos_visuais_paths, provider, model)

    if status_path.exists() and not forcar:
        status_existente = read_json(status_path)
        if _status_em_dia(status_existente, fingerprints) and resposta_path.exists():
            atualizar_uso_tokens_rodada(rodada_dir)
            return status_existente
        if status_existente.get("status") == "ok":
            _marcar_desatualizado(status_path, batch, fingerprints)

    execucao = executar_prompt(
        prompt_path=prompt_path,
        raw_output_path=resposta_bruta_path,
        provider=provider,
        model=model,
        workdir=rodada_dir,
        image_paths=anexos_visuais_paths,
    )
    fichas_recebidas = 0
    status = "ok"
    erro = None

    if execucao["exit_code"] != 0:
        status = "erro_cli"
        erro = execucao["stderr"] or execucao["stdout"] or "A CLI do provider falhou."
        payload_status = {
            "batch_id": batch_id,
            "status": status,
            "provider": provider,
            "modelo": model,
            "ppc_sha256": fingerprints.ppc_sha256,
            "batch_sha256": fingerprints.batch_sha256,
            "prompt_sha256": fingerprints.prompt_sha256,
            "anexos_visuais": anexos_visuais,
            "anexos_visuais_sha256": fingerprints.anexos_visuais_sha256,
            "fichas_esperadas": len(batch["fichas"]),
            "fichas_recebidas": fichas_recebidas,
            "executado_em": now_iso(),
            "erro": erro,
        }
        if execucao.get("uso_tokens"):
            payload_status["uso_tokens"] = execucao["uso_tokens"]
        write_json(status_path, payload_status)
        atualizar_uso_tokens_rodada(rodada_dir)
        return payload_status

    texto_bruto = resposta_bruta_path.read_text(encoding="utf-8") if resposta_bruta_path.exists() else ""
    try:
        payload_json = extrair_json_de_resposta(texto_bruto)
        write_json(resposta_path, payload_json)
        fichas_recebidas = len(payload_json.get("resultados", [])) if isinstance(payload_json.get("resultados"), list) else 0
        validado = validar_resposta_lote(batch, payload_json)
        write_json(resposta_path, validado)
    except ErroRespostaIncompleta as exc:
        status = "erro_incompleto"
        erro = str(exc)
    except ErroValidacaoResposta as exc:
        status = "erro_validacao"
        erro = str(exc)
    except Exception as exc:  # noqa: BLE001
        status = "erro_json"
        erro = str(exc)

    payload_status = {
        "batch_id": batch_id,
        "status": status,
        "provider": provider,
        "modelo": model,
        "ppc_sha256": fingerprints.ppc_sha256,
        "batch_sha256": fingerprints.batch_sha256,
        "prompt_sha256": fingerprints.prompt_sha256,
        "anexos_visuais": anexos_visuais,
        "anexos_visuais_sha256": fingerprints.anexos_visuais_sha256,
        "fichas_esperadas": len(batch["fichas"]),
        "fichas_recebidas": fichas_recebidas,
        "executado_em": now_iso(),
    }
    if execucao.get("uso_tokens"):
        payload_status["uso_tokens"] = execucao["uso_tokens"]
    if erro:
        payload_status["erro"] = erro
    write_json(status_path, payload_status)
    atualizar_uso_tokens_rodada(rodada_dir)
    return payload_status


def avaliar_todos(
    rodada_dir: Path,
    provider: str,
    model: str,
    forcar: bool = False,
    batch_ids: list[str] | None = None,
) -> dict[str, Any]:
    contexto_estrutural = verificar_bloqueios_pre_validacao(rodada_dir)
    caminhos = round_paths(rodada_dir)
    batches = sorted(caminhos["batches_dir"].glob("batch-*.json"))
    if not batches:
        raise RuntimeError("Nenhum batch foi encontrado para avaliar. Execute `gerar-batches` antes de `avaliar-todos`.")
    if batch_ids:
        batches_por_id = {batch.stem: batch for batch in batches}
        faltantes = [batch_id for batch_id in batch_ids if batch_id not in batches_por_id]
        if faltantes:
            raise RuntimeError("Batches solicitados não encontrados: " + ", ".join(faltantes))
        batches = [batches_por_id[batch_id] for batch_id in batch_ids]
    resultados: list[dict[str, Any]] = []
    for batch_path in batches:
        resultados.append(
            avaliar_lote(
                rodada_dir=rodada_dir,
                batch_id=batch_path.stem,
                provider=provider,
                model=model,
                forcar=forcar,
            )
        )
    uso_tokens = atualizar_uso_tokens_rodada(rodada_dir)
    return {
        "rodada_dir": str(rodada_dir.resolve()),
        "pre_validacoes": contexto_estrutural["pre_validacoes"],
        "total_batches": len(resultados),
        "status": resultados,
        "uso_tokens": uso_tokens,
    }
