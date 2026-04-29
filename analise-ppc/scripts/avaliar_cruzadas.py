from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pre_validacoes import carregar_contexto_estrutural, gerar_pre_validacoes_rodada
from providers import executar_prompt
from providers.prompt_builder import renderizar_prompt_validacoes_cruzadas
from providers.response_parser import extrair_json_de_resposta
from uso_tokens import atualizar_uso_tokens_rodada
from common import (
    VALIDACOES_CRUZADAS_DIR,
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

ESTADOS_PERMITIDOS = {"ATENDE", "NAO_ATENDE", "INCONCLUSIVO", "NAO_APLICAVEL"}
IGNORAR_BLOQUEIOS_CRUZADAS = {"PV-005"}


class ErroValidacaoCruzadaIncompleta(ValueError):
    pass


class ErroValidacaoCruzadaResposta(ValueError):
    pass


@dataclass
class FingerprintsValidacoesCruzadas:
    ppc_sha256: str
    catalogo_sha256: str
    prompt_sha256: str
    provider: str
    model: str


def _catalogo_payload(validacoes_dir: Path | None = None) -> dict[str, Any]:
    validacoes = sorted(load_validacoes_cruzadas(validacoes_dir or VALIDACOES_CRUZADAS_DIR), key=lambda item: item["id"])
    if not validacoes:
        raise RuntimeError("Nenhuma validação cruzada JSON foi encontrada.")
    return {
        "escopo": "validacoes_cruzadas",
        "total_validacoes": len(validacoes),
        "validacoes": validacoes,
    }


def _construir_fingerprints(
    caminhos: dict[str, Path],
    prompt_text: str,
    provider: str,
    model: str,
    catalogo: dict[str, Any],
) -> FingerprintsValidacoesCruzadas:
    return FingerprintsValidacoesCruzadas(
        ppc_sha256=sha256_file(caminhos["ppc"]),
        catalogo_sha256=sha256_json_payload(catalogo),
        prompt_sha256=sha256_text(prompt_text),
        provider=provider,
        model=model,
    )


def _status_em_dia(status_payload: dict[str, Any], fingerprints: FingerprintsValidacoesCruzadas) -> bool:
    return (
        status_payload.get("status") == "ok"
        and status_payload.get("ppc_sha256") == fingerprints.ppc_sha256
        and status_payload.get("catalogo_sha256") == fingerprints.catalogo_sha256
        and status_payload.get("prompt_sha256") == fingerprints.prompt_sha256
        and status_payload.get("provider") == fingerprints.provider
        and status_payload.get("modelo") == fingerprints.model
    )


def _marcar_desatualizado(
    status_path: Path,
    total_validacoes: int,
    fingerprints: FingerprintsValidacoesCruzadas,
) -> dict[str, Any]:
    payload = {
        "escopo": "validacoes_cruzadas",
        "status": "desatualizado",
        "provider": fingerprints.provider,
        "modelo": fingerprints.model,
        "ppc_sha256": fingerprints.ppc_sha256,
        "catalogo_sha256": fingerprints.catalogo_sha256,
        "prompt_sha256": fingerprints.prompt_sha256,
        "validacoes_esperadas": total_validacoes,
        "validacoes_recebidas": 0,
        "executado_em": now_iso(),
        "erro": "Os fingerprints atuais divergem da última execução válida.",
    }
    write_json(status_path, payload)
    return payload


def _carregar_contexto_sem_regravar(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    if caminhos["pre_validacoes"].exists() and caminhos["condicionais_rodada"].exists() and caminhos["contexto_estrutural"].exists():
        return carregar_contexto_estrutural(rodada_dir)
    payload = gerar_pre_validacoes_rodada(rodada_dir)
    return {
        "pre_validacoes": payload["pre_validacoes"],
        "condicionais_rodada": payload["condicionais"],
        "contexto_estrutural": payload["contexto_estrutural"],
    }


def validar_resposta_validacoes_cruzadas(
    catalogo: dict[str, Any],
    resposta: dict[str, Any],
    provider: str,
    model: str,
) -> dict[str, Any]:
    if not isinstance(resposta, dict):
        raise ErroValidacaoCruzadaResposta("A resposta normalizada precisa ser um objeto JSON.")
    resultados = resposta.get("validacoes") or resposta.get("resultados")
    if not isinstance(resultados, list):
        raise ErroValidacaoCruzadaResposta("A resposta não contém uma lista `validacoes` válida.")

    validacoes_por_id = {item["id"]: item for item in catalogo["validacoes"]}
    vistos: set[str] = set()
    normalizados: list[dict[str, Any]] = []

    for item in resultados:
        if not isinstance(item, dict):
            raise ErroValidacaoCruzadaResposta("Cada validação precisa ser um objeto JSON.")
        validacao_id = item.get("validacao_id") or item.get("id")
        if not validacao_id:
            raise ErroValidacaoCruzadaResposta("Um item não contém `validacao_id`.")
        if validacao_id not in validacoes_por_id:
            raise ErroValidacaoCruzadaIncompleta(f"Foi recebido `validacao_id` estranho ao catálogo: {validacao_id}")
        if validacao_id in vistos:
            raise ErroValidacaoCruzadaIncompleta(f"Foi recebido `validacao_id` duplicado: {validacao_id}")
        vistos.add(validacao_id)

        validacao = validacoes_por_id[validacao_id]
        estado = item.get("estado") or item.get("status")
        if estado not in validacao.get("estados_permitidos", ESTADOS_PERMITIDOS):
            raise ErroValidacaoCruzadaResposta(f"Estado inválido para {validacao_id}: {estado}")

        confianca = item.get("confianca")
        if not isinstance(confianca, (int, float)) or not (0 <= float(confianca) <= 1):
            raise ErroValidacaoCruzadaResposta(f"Confiança inválida para {validacao_id}: {confianca}")

        justificativa = item.get("justificativa")
        if not isinstance(justificativa, str) or not justificativa.strip():
            raise ErroValidacaoCruzadaResposta(f"`justificativa` inválida para {validacao_id}")

        evidencias = item.get("evidencias")
        if not isinstance(evidencias, list):
            raise ErroValidacaoCruzadaResposta(f"`evidencias` inválida para {validacao_id}")
        evidencias_normalizadas = [str(evidencia).strip() for evidencia in evidencias if str(evidencia).strip()]
        if len(evidencias_normalizadas) < int(validacao.get("evidencia_minima", 1)):
            raise ErroValidacaoCruzadaResposta(f"{validacao_id} trouxe menos evidências que o mínimo exigido.")

        lacunas = item.get("lacunas")
        if not isinstance(lacunas, list):
            raise ErroValidacaoCruzadaResposta(f"`lacunas` inválida para {validacao_id}")

        revisao_humana = item.get("revisao_humana_obrigatoria")
        if not isinstance(revisao_humana, bool):
            raise ErroValidacaoCruzadaResposta(f"`revisao_humana_obrigatoria` inválido para {validacao_id}")

        normalizados.append(
            {
                "id": validacao_id,
                "validacao_id": validacao_id,
                "titulo": validacao["titulo"],
                "criticidade": validacao["criticidade"],
                "tipo": validacao["tipo"],
                "secoes_relacionadas": list(validacao.get("secoes_relacionadas", [])),
                "condicionais_relacionadas": list(validacao.get("condicionais_relacionadas", [])),
                "estado": estado,
                "status": estado,
                "confianca": float(confianca),
                "justificativa": justificativa.strip(),
                "evidencias": evidencias_normalizadas,
                "lacunas": [str(lacuna).strip() for lacuna in lacunas if str(lacuna).strip()],
                "revisao_humana_obrigatoria": revisao_humana,
            }
        )

    faltantes = [validacao_id for validacao_id in validacoes_por_id if validacao_id not in vistos]
    if faltantes:
        raise ErroValidacaoCruzadaIncompleta(
            "Validações cruzadas sem resposta: " + ", ".join(sorted(faltantes))
        )

    return {
        "escopo": "validacoes_cruzadas",
        "gerado_em": now_iso(),
        "provider": provider,
        "modelo": model,
        "total_validacoes": len(normalizados),
        "validacoes": normalizados,
    }


def avaliar_validacoes_cruzadas(
    rodada_dir: Path,
    provider: str,
    model: str,
    forcar: bool = False,
    validacoes_dir: Path | None = None,
) -> dict[str, Any]:
    contexto = _carregar_contexto_sem_regravar(rodada_dir)
    bloqueios = [
        bloqueio
        for bloqueio in contexto.get("pre_validacoes", {}).get("bloqueios", [])
        if bloqueio not in IGNORAR_BLOQUEIOS_CRUZADAS
    ]
    if bloqueios:
        raise RuntimeError(
            "A rodada possui bloqueios estruturais e não pode seguir para `avaliar-cruzadas`: "
            + ", ".join(bloqueios)
        )
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    ppc_markdown = caminhos["ppc"].read_text(encoding="utf-8")
    catalogo = _catalogo_payload(validacoes_dir)
    write_json(caminhos["validacoes_cruzadas_catalogo"], catalogo)
    prompt_text = renderizar_prompt_validacoes_cruzadas(
        metadata,
        ppc_markdown,
        catalogo,
        pre_validacoes=contexto.get("pre_validacoes"),
        condicionais_rodada=contexto.get("condicionais_rodada"),
        contexto_estrutural=contexto.get("contexto_estrutural"),
    )
    write_text(caminhos["validacoes_cruzadas_prompt"], prompt_text)
    fingerprints = _construir_fingerprints(caminhos, prompt_text, provider, model, catalogo)

    status_path = caminhos["validacoes_cruzadas_status"]
    destino_path = caminhos["validacoes_cruzadas"]
    if status_path.exists() and not forcar:
        status_existente = read_json(status_path)
        if _status_em_dia(status_existente, fingerprints) and destino_path.exists():
            atualizar_uso_tokens_rodada(rodada_dir)
            return status_existente
        if status_existente.get("status") == "ok":
            _marcar_desatualizado(status_path, catalogo["total_validacoes"], fingerprints)

    execucao = executar_prompt(
        prompt_path=caminhos["validacoes_cruzadas_prompt"],
        raw_output_path=caminhos["validacoes_cruzadas_resposta_bruta"],
        provider=provider,
        model=model,
        workdir=rodada_dir,
    )
    validacoes_recebidas = 0
    status = "ok"
    erro = None

    if execucao["exit_code"] != 0:
        status = "erro_cli"
        erro = execucao["stderr"] or execucao["stdout"] or "A CLI do provider falhou."
    else:
        texto_bruto = (
            caminhos["validacoes_cruzadas_resposta_bruta"].read_text(encoding="utf-8")
            if caminhos["validacoes_cruzadas_resposta_bruta"].exists()
            else ""
        )
        try:
            payload_json = extrair_json_de_resposta(texto_bruto)
            validacoes_recebidas = len(payload_json.get("validacoes", []) or payload_json.get("resultados", []))
            validado = validar_resposta_validacoes_cruzadas(catalogo, payload_json, provider, model)
            write_json(destino_path, validado)
        except ErroValidacaoCruzadaIncompleta as exc:
            status = "erro_incompleto"
            erro = str(exc)
        except ErroValidacaoCruzadaResposta as exc:
            status = "erro_validacao"
            erro = str(exc)
        except Exception as exc:  # noqa: BLE001
            status = "erro_json"
            erro = str(exc)

    payload_status = {
        "escopo": "validacoes_cruzadas",
        "status": status,
        "provider": provider,
        "modelo": model,
        "ppc_sha256": fingerprints.ppc_sha256,
        "catalogo_sha256": fingerprints.catalogo_sha256,
        "catalogo_path": str(caminhos["validacoes_cruzadas_catalogo"]),
        "prompt_sha256": fingerprints.prompt_sha256,
        "validacoes_esperadas": catalogo["total_validacoes"],
        "validacoes_recebidas": validacoes_recebidas,
        "executado_em": now_iso(),
    }
    if execucao.get("uso_tokens"):
        payload_status["uso_tokens"] = execucao["uso_tokens"]
    if erro:
        payload_status["erro"] = erro
    write_json(status_path, payload_status)
    atualizar_uso_tokens_rodada(rodada_dir)
    return payload_status
