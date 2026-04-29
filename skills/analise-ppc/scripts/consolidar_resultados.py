from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from anexos_visuais import descrever_anexos_visuais_lote, resolver_anexos_visuais_lote
from pre_validacoes import carregar_contexto_estrutural
from providers.prompt_builder import renderizar_prompt_lote, renderizar_prompt_validacoes_cruzadas
from common import (
    POLITICA_PARECER_PATH,
    FICHAS_DIR,
    VALIDACOES_CRUZADAS_DIR,
    load_fichas,
    load_validacoes_cruzadas,
    now_iso,
    read_json,
    round_paths,
    sha256_file,
    sha256_json_payload,
    sha256_text,
    write_json,
)

SITUACAO_LABELS = {
    "padrao": {
        "APROVADO": "APROVADO",
        "COM_RESSALVAS": "COM_RESSALVAS",
        "DILIGENCIA": "DILIGENCIA",
        "NAO_APROVADO": "NAO_APROVADO",
    },
    "sintetico": {
        "APROVADO": "APROVAVEL",
        "COM_RESSALVAS": "APROVAVEL",
        "DILIGENCIA": "DILIGENCIA",
        "NAO_APROVADO": "INADEQUADO",
    },
}

ENCAMINHAMENTOS = {
    "APROVADO": "Encaminhar para tramitação regular.",
    "COM_RESSALVAS": "Encaminhar com registro das ressalvas e monitoramento dos ajustes.",
    "DILIGENCIA": "Devolver para diligência e complementação.",
    "NAO_APROVADO": "Recomendar revisão estrutural antes de novo envio.",
    "APROVAVEL": "Encaminhar para tramitação regular.",
    "INADEQUADO": "Recomendar revisão estrutural antes de novo envio.",
}

FICHA_RISCO_GLOBAL = "CT-TRANS-05"
FICHAS_SINTETICAS_EXCLUIDAS = {FICHA_RISCO_GLOBAL, "CT-TRANS-06"}


def _validar_status_em_dia(
    rodada_dir: Path,
    batch: dict[str, Any],
    status: dict[str, Any],
    manifesto: dict[str, Any],
    metadata: dict[str, Any],
    ppc_markdown: str,
    contexto_estrutural: dict[str, Any],
) -> None:
    anexos_visuais_paths = resolver_anexos_visuais_lote(batch, contexto_estrutural.get("contexto_estrutural") or {})
    anexos_visuais = descrever_anexos_visuais_lote(batch, anexos_visuais_paths)
    prompt_text = renderizar_prompt_lote(
        metadata,
        ppc_markdown,
        batch,
        pre_validacoes=contexto_estrutural.get("pre_validacoes"),
        condicionais_rodada=contexto_estrutural.get("condicionais_rodada"),
        contexto_estrutural=contexto_estrutural.get("contexto_estrutural"),
        anexos_visuais=anexos_visuais,
    )
    if status.get("status") != "ok":
        raise RuntimeError(f"O lote {batch['batch_id']} não está válido: {status.get('status')}")
    if status.get("ppc_sha256") != sha256_file(round_paths(rodada_dir)["ppc"]):
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação ao PPC.md.")
    if status.get("batch_sha256") != sha256_file(round_paths(rodada_dir)["batches_dir"] / f"{batch['batch_id']}.json"):
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação ao batch.")
    if status.get("prompt_sha256") != sha256_text(prompt_text):
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação ao prompt renderizado.")
    anexos_sha256 = [sha256_file(anexo) for anexo in anexos_visuais_paths]
    if status.get("anexos_visuais_sha256", []) != anexos_sha256:
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação aos anexos visuais.")
    if status.get("provider") != manifesto.get("provider_padrao"):
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação ao provider configurado na rodada.")
    if status.get("modelo") != manifesto.get("modelo_padrao"):
        raise RuntimeError(f"O lote {batch['batch_id']} está desatualizado em relação ao modelo configurado na rodada.")


def _carregar_politica() -> dict[str, Any]:
    return read_json(POLITICA_PARECER_PATH)


def _carregar_validacoes_cruzadas(rodada_dir: Path) -> list[dict[str, Any]]:
    caminho = rodada_dir / "validacoes-cruzadas.json"
    if not caminho.exists():
        return []
    payload = read_json(caminho)
    if isinstance(payload, dict):
        if isinstance(payload.get("validacoes"), list):
            return [item for item in payload["validacoes"] if isinstance(item, dict)]
        if isinstance(payload.get("itens"), list):
            return [item for item in payload["itens"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _carregar_indice_sobreposicoes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = read_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("itens"), dict):
        return {str(chave): valor for chave, valor in payload["itens"].items() if isinstance(valor, dict)}
    return {}


def _validar_sobreposicao(
    entrada: dict[str, Any],
    item_catalogo: dict[str, Any],
    ppc_sha256: str,
    item_id: str,
) -> None:
    if entrada.get("status") != "ok":
        raise RuntimeError(f"A sobreposição avulsa de {item_id} não está válida: {entrada.get('status')}")
    if entrada.get("ppc_sha256") != ppc_sha256:
        raise RuntimeError(f"A sobreposição avulsa de {item_id} está desatualizada em relação ao PPC.md.")
    if entrada.get("item_sha256") != sha256_json_payload(item_catalogo):
        raise RuntimeError(f"A sobreposição avulsa de {item_id} está desatualizada em relação ao catálogo.")
    if not isinstance(entrada.get("resultado"), dict):
        raise RuntimeError(f"A sobreposição avulsa de {item_id} não contém resultado normalizado.")
    if not entrada.get("executado_em"):
        raise RuntimeError(f"A sobreposição avulsa de {item_id} não registra data/hora de execução.")


def _parse_iso_datetime(valor: Any) -> datetime | None:
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def _sobreposicao_mais_nova_que_base(entrada: dict[str, Any], base: dict[str, Any] | None) -> bool:
    if not base:
        return True
    executado_avulso = _parse_iso_datetime(entrada.get("executado_em"))
    executado_base = _parse_iso_datetime(base.get("executado_em"))
    if executado_avulso is None or executado_base is None:
        return True
    return executado_avulso >= executado_base


def _aplicar_sobreposicoes_fichas(
    rodada_dir: Path,
    itens: list[dict[str, Any]],
    execucoes_base: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    caminhos = round_paths(rodada_dir)
    sobreposicoes = _carregar_indice_sobreposicoes(caminhos["sobreposicoes_fichas"])
    if not sobreposicoes:
        return itens

    ppc_sha256 = sha256_file(caminhos["ppc"])
    fichas_por_id = {ficha["id"]: ficha for ficha in load_fichas(FICHAS_DIR)}
    itens_por_id = {item["ficha_id"]: item for item in itens}
    for ficha_id, entrada in sobreposicoes.items():
        ficha = fichas_por_id.get(ficha_id)
        if ficha is None:
            raise RuntimeError(f"Sobreposição avulsa referencia ficha inexistente: {ficha_id}")
        if ficha_id not in itens_por_id:
            raise RuntimeError(f"Sobreposição avulsa de {ficha_id} não possui resultado base nos batches.")
        _validar_sobreposicao(entrada, ficha, ppc_sha256, ficha_id)
        if not _sobreposicao_mais_nova_que_base(entrada, execucoes_base.get(ficha_id)):
            continue
        resultado = entrada["resultado"]
        itens_por_id[ficha_id] = {
            **itens_por_id[ficha_id],
            "batch_id": "avulso",
            "estado": resultado["estado"],
            "confianca": resultado["confianca"],
            "justificativa": resultado["justificativa"],
            "evidencias": resultado["evidencias"],
            "lacunas": resultado["lacunas"],
            "revisao_humana_obrigatoria": resultado["revisao_humana_obrigatoria"],
            "secoes_preferenciais": resultado.get("secoes_preferenciais", ficha.get("secoes_preferenciais", [])),
            "execucao_avulsa": {
                "executado_em": entrada.get("executado_em"),
                "provider": entrada.get("provider"),
                "modelo": entrada.get("modelo"),
                "execucao_path": entrada.get("execucao_path"),
            },
        }
    return [itens_por_id[item["ficha_id"]] for item in itens]


def _aplicar_sobreposicoes_validacoes_cruzadas(
    rodada_dir: Path,
    validacoes_cruzadas: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    caminhos = round_paths(rodada_dir)
    sobreposicoes = _carregar_indice_sobreposicoes(caminhos["sobreposicoes_validacoes_cruzadas"])
    if not sobreposicoes:
        return validacoes_cruzadas, False

    ppc_sha256 = sha256_file(caminhos["ppc"])
    catalogo_por_id = {validacao["id"]: validacao for validacao in load_validacoes_cruzadas(VALIDACOES_CRUZADAS_DIR)}
    validacoes_por_id = {
        (item.get("id") or item.get("validacao_id")): item
        for item in validacoes_cruzadas
        if item.get("id") or item.get("validacao_id")
    }
    status_base = read_json(caminhos["validacoes_cruzadas_status"]) if caminhos["validacoes_cruzadas_status"].exists() else {}
    execucao_base = {"executado_em": status_base.get("executado_em")} if status_base.get("executado_em") else None
    alterado = False
    for validacao_id, entrada in sobreposicoes.items():
        validacao = catalogo_por_id.get(validacao_id)
        if validacao is None:
            raise RuntimeError(f"Sobreposição avulsa referencia validação inexistente: {validacao_id}")
        _validar_sobreposicao(entrada, validacao, ppc_sha256, validacao_id)
        base_item = validacoes_por_id.get(validacao_id)
        base_execucao = base_item.get("execucao_avulsa") if isinstance(base_item, dict) else None
        if not _sobreposicao_mais_nova_que_base(entrada, base_execucao or execucao_base):
            continue
        resultado = {
            **entrada["resultado"],
            "execucao_avulsa": {
                "executado_em": entrada.get("executado_em"),
                "provider": entrada.get("provider"),
                "modelo": entrada.get("modelo"),
                "execucao_path": entrada.get("execucao_path"),
            },
        }
        validacoes_por_id[validacao_id] = resultado
        alterado = True
    return list(validacoes_por_id.values()), alterado


def _payload_validacoes_cruzadas_consolidado(validacoes_cruzadas: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "escopo": "validacoes_cruzadas",
        "gerado_em": now_iso(),
        "provider": "consolidado",
        "modelo": "sobreposicoes-avulsas",
        "total_validacoes": len(validacoes_cruzadas),
        "validacoes": validacoes_cruzadas,
    }


def _escrever_validacoes_cruzadas_consolidadas(
    rodada_dir: Path,
    validacoes_cruzadas: list[dict[str, Any]],
) -> None:
    caminhos = round_paths(rodada_dir)
    payload = _payload_validacoes_cruzadas_consolidado(validacoes_cruzadas)
    write_json(caminhos["validacoes_cruzadas"], payload)
    sobreposicoes_sha256 = (
        sha256_file(caminhos["sobreposicoes_validacoes_cruzadas"])
        if caminhos["sobreposicoes_validacoes_cruzadas"].exists()
        else sha256_text("")
    )
    catalogo = _catalogo_validacoes_cruzadas_payload(rodada_dir)
    write_json(
        caminhos["validacoes_cruzadas_status"],
        {
            "escopo": "validacoes_cruzadas_consolidado",
            "status": "ok",
            "provider": "consolidado",
            "modelo": "sobreposicoes-avulsas",
            "ppc_sha256": sha256_file(caminhos["ppc"]),
            "catalogo_sha256": sha256_json_payload(catalogo),
            "sobreposicoes_sha256": sobreposicoes_sha256,
            "resultado_sha256": sha256_file(caminhos["validacoes_cruzadas"]),
            "validacoes_esperadas": len(validacoes_cruzadas),
            "validacoes_recebidas": len(validacoes_cruzadas),
            "executado_em": now_iso(),
        },
    )


def _catalogo_validacoes_cruzadas_payload(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    if caminhos["validacoes_cruzadas_catalogo"].exists():
        return read_json(caminhos["validacoes_cruzadas_catalogo"])
    validacoes = sorted(load_validacoes_cruzadas(), key=lambda item: item["id"])
    return {
        "escopo": "validacoes_cruzadas",
        "total_validacoes": len(validacoes),
        "validacoes": validacoes,
    }


def _validar_validacoes_cruzadas_em_dia(
    rodada_dir: Path,
    metadata: dict[str, Any],
    manifesto: dict[str, Any],
    ppc_markdown: str,
    contexto_estrutural: dict[str, Any],
) -> None:
    caminhos = round_paths(rodada_dir)
    if not caminhos["validacoes_cruzadas"].exists():
        return
    if not caminhos["validacoes_cruzadas_status"].exists():
        raise RuntimeError("As validações cruzadas existem, mas não há status de execução correspondente.")
    status = read_json(caminhos["validacoes_cruzadas_status"])
    if status.get("escopo") == "validacoes_cruzadas_consolidado":
        if status.get("status") != "ok":
            raise RuntimeError(f"As validações cruzadas consolidadas não estão válidas: {status.get('status')}")
        if status.get("ppc_sha256") != sha256_file(caminhos["ppc"]):
            raise RuntimeError("As validações cruzadas consolidadas estão desatualizadas em relação ao PPC.md.")
        if status.get("resultado_sha256") != sha256_file(caminhos["validacoes_cruzadas"]):
            raise RuntimeError("As validações cruzadas consolidadas estão desatualizadas em relação ao resultado final.")
        sobreposicoes_sha256 = (
            sha256_file(caminhos["sobreposicoes_validacoes_cruzadas"])
            if caminhos["sobreposicoes_validacoes_cruzadas"].exists()
            else sha256_text("")
        )
        if status.get("sobreposicoes_sha256") != sobreposicoes_sha256:
            return
        return
    catalogo = _catalogo_validacoes_cruzadas_payload(rodada_dir)
    prompt_text = renderizar_prompt_validacoes_cruzadas(
        metadata,
        ppc_markdown,
        catalogo,
        pre_validacoes=contexto_estrutural.get("pre_validacoes"),
        condicionais_rodada=contexto_estrutural.get("condicionais_rodada"),
        contexto_estrutural=contexto_estrutural.get("contexto_estrutural"),
    )
    if status.get("status") != "ok":
        raise RuntimeError(f"As validações cruzadas não estão válidas: {status.get('status')}")
    if status.get("ppc_sha256") != sha256_file(caminhos["ppc"]):
        raise RuntimeError("As validações cruzadas estão desatualizadas em relação ao PPC.md.")
    if status.get("catalogo_sha256") != sha256_json_payload(catalogo):
        raise RuntimeError("As validações cruzadas estão desatualizadas em relação ao catálogo.")
    if status.get("prompt_sha256") != sha256_text(prompt_text):
        raise RuntimeError("As validações cruzadas estão desatualizadas em relação ao prompt renderizado.")
    if status.get("provider") != manifesto.get("provider_padrao"):
        raise RuntimeError("As validações cruzadas estão desatualizadas em relação ao provider configurado na rodada.")
    if status.get("modelo") != manifesto.get("modelo_padrao"):
        raise RuntimeError("As validações cruzadas estão desatualizadas em relação ao modelo configurado na rodada.")


def _resumo_sinal_item(item: dict[str, Any]) -> str:
    return f"{item['ficha_id']} ({item['criticidade']}) = {item['estado']}"


def _resumo_sinal_pre_validacao(item: dict[str, Any]) -> str:
    return f"{item['id']} = {item['status']}"


def _resumo_sinal_validacao_cruzada(item: dict[str, Any]) -> str:
    identificador = item.get("id") or item.get("codigo") or "VC"
    status = item.get("status") or item.get("estado") or "INCONCLUSIVO"
    return f"{identificador} = {status}"


def _derivar_risco_global(
    itens: list[dict[str, Any]],
    pre_validacoes: dict[str, Any],
    validacoes_cruzadas: list[dict[str, Any]],
) -> dict[str, Any] | None:
    indice_sintese = next((indice for indice, item in enumerate(itens) if item["ficha_id"] == FICHA_RISCO_GLOBAL), None)
    if indice_sintese is None:
        return None

    item_base = itens[indice_sintese]
    pre_obrigatorias = [
        item
        for item in pre_validacoes.get("obrigatorias", [])
        if isinstance(item, dict) and item.get("status") in {"NAO_CONFORME", "INCONCLUSIVO"}
    ]
    checks_criticos = [
        item
        for item in validacoes_cruzadas
        if (item.get("status") or item.get("estado")) in {"NAO_CONFORME", "NAO_ATENDE", "INCONCLUSIVO"}
    ]
    fichas_criticas = [
        item
        for item in itens
        if item["ficha_id"] not in FICHAS_SINTETICAS_EXCLUIDAS
        and (
            item["criticidade"] == "BLOQ"
            or item["estado"] in {"NAO_ATENDE", "INCONCLUSIVO"}
            or item["revisao_humana_obrigatoria"]
        )
    ]

    sinais_duros = [
        *[item for item in pre_obrigatorias if item.get("status") == "NAO_CONFORME" and item.get("bloqueante")],
        *[item for item in checks_criticos if (item.get("status") or item.get("estado")) in {"NAO_CONFORME", "NAO_ATENDE"}],
        *[item for item in fichas_criticas if item["criticidade"] == "BLOQ" and item["estado"] == "NAO_ATENDE"],
    ]
    sinais_incertos = [
        *[item for item in pre_obrigatorias if item.get("status") == "INCONCLUSIVO"],
        *[item for item in checks_criticos if (item.get("status") or item.get("estado")) == "INCONCLUSIVO"],
        *[
            item
            for item in fichas_criticas
            if item["estado"] == "INCONCLUSIVO"
            or item["revisao_humana_obrigatoria"]
            or (item["criticidade"] == "OBRIG" and item["estado"] == "NAO_ATENDE")
        ],
    ]

    if sinais_duros:
        estado = "NAO_ATENDE"
        confianca = 0.95
        justificativa = (
            "Síntese derivada de sinais auditáveis: há bloqueios estruturais ou fichas críticas não atendidas "
            "que sustentam risco global elevado e diligência prioritária."
        )
    elif sinais_incertos:
        estado = "INCONCLUSIVO"
        confianca = 0.88
        justificativa = (
            "Síntese derivada de sinais auditáveis: persistem lacunas relevantes, pontos críticos inconclusivos "
            "ou dependência de revisão humana para fechar o risco global do PPC."
        )
    else:
        estado = "ATENDE"
        confianca = 0.9
        justificativa = (
            "Síntese derivada de sinais auditáveis: não há bloqueios estruturais nem concentração relevante de achados "
            "críticos que justifiquem diligência global adicional."
        )

    evidencias: list[str] = []
    evidencias.extend(_resumo_sinal_pre_validacao(item) for item in pre_obrigatorias[:2])
    evidencias.extend(_resumo_sinal_validacao_cruzada(item) for item in checks_criticos[:2])
    evidencias.extend(_resumo_sinal_item(item) for item in fichas_criticas[:4])

    if not pre_validacoes.get("tem_bloqueios"):
        evidencias.append("Pré-validações sem bloqueios estruturais ativos.")
    if not any(item["criticidade"] == "BLOQ" and item["estado"] == "NAO_ATENDE" for item in fichas_criticas):
        evidencias.append("Nenhuma ficha bloqueante adicional ficou em NAO_ATENDE.")
    if not any(item["revisao_humana_obrigatoria"] for item in fichas_criticas):
        evidencias.append("Não há concentração adicional de itens com revisão humana obrigatória.")

    lacunas: list[str] = []
    lacunas.extend(item.get("detalhe") or _resumo_sinal_pre_validacao(item) for item in pre_obrigatorias[:3])
    lacunas.extend((item.get("titulo") or item.get("descricao") or item.get("id") or "Validação cruzada") for item in checks_criticos[:2])
    lacunas.extend(
        f"{item['ficha_id']} requer diligência complementar."
        for item in fichas_criticas
        if item["estado"] in {"NAO_ATENDE", "INCONCLUSIVO"} or item["revisao_humana_obrigatoria"]
    )

    evidencias_limpa = []
    for evidencia in evidencias:
        texto = str(evidencia).strip()
        if texto and texto not in evidencias_limpa:
            evidencias_limpa.append(texto)
    while len(evidencias_limpa) < 3:
        evidencias_limpa.append("Síntese executiva derivada do conjunto consolidado de sinais auditáveis da rodada.")

    lacunas_limpa = []
    for lacuna in lacunas:
        texto = str(lacuna).strip()
        if texto and texto not in lacunas_limpa:
            lacunas_limpa.append(texto)

    return {
        **item_base,
        "batch_id": "derivado",
        "estado": estado,
        "confianca": confianca,
        "justificativa": justificativa,
        "evidencias": evidencias_limpa[:6],
        "lacunas": lacunas_limpa[:6],
        "revisao_humana_obrigatoria": estado != "ATENDE" or any(item["revisao_humana_obrigatoria"] for item in fichas_criticas),
        "derivado_de": {
            "pre_validacoes": [item["id"] for item in pre_obrigatorias],
            "validacoes_cruzadas": [item.get("id") or item.get("codigo") for item in checks_criticos],
            "fichas_criticas": [item["ficha_id"] for item in fichas_criticas],
        },
    }


def _calcular_parecer(itens: list[dict[str, Any]], modo_situacao: str) -> dict[str, Any]:
    politica = _carregar_politica()
    metricas = {
        "total_fichas": len(itens),
        "bloq_nao_atende": 0,
        "bloq_inconclusivo": 0,
        "obrig_nao_atende": 0,
        "obrig_inconclusivo": 0,
        "rec_nao_atende": 0,
    }
    for item in itens:
        if item["criticidade"] == "BLOQ" and item["estado"] == "NAO_ATENDE":
            metricas["bloq_nao_atende"] += 1
        elif item["criticidade"] == "BLOQ" and item["estado"] == "INCONCLUSIVO":
            metricas["bloq_inconclusivo"] += 1
        elif item["criticidade"] == "OBRIG" and item["estado"] == "NAO_ATENDE":
            metricas["obrig_nao_atende"] += 1
        elif item["criticidade"] == "OBRIG" and item["estado"] == "INCONCLUSIVO":
            metricas["obrig_inconclusivo"] += 1
        elif item["criticidade"] == "REC" and item["estado"] == "NAO_ATENDE":
            metricas["rec_nao_atende"] += 1

    regras = politica["regras"]
    if metricas["bloq_nao_atende"] >= regras["nao_aprovado"]["bloq_nao_atende_min"]:
        situacao_base = "NAO_APROVADO"
    elif (
        metricas["bloq_nao_atende"] >= regras["diligencia"]["bloq_nao_atende_min"]
        or metricas["bloq_inconclusivo"] >= regras["diligencia"]["bloq_inconclusivo_min"]
        or metricas["obrig_nao_atende"] >= regras["diligencia"]["obrig_nao_atende_min"]
        or metricas["obrig_inconclusivo"] >= regras["diligencia"]["obrig_inconclusivo_min"]
    ):
        situacao_base = "DILIGENCIA"
    elif metricas["obrig_nao_atende"] > 0:
        situacao_base = "COM_RESSALVAS"
    else:
        situacao_base = "APROVADO"

    principais_achados = [
        f"{item['ficha_id']} — {item['estado']}"
        for item in itens
        if item["estado"] in {"NAO_ATENDE", "INCONCLUSIVO"} or item["revisao_humana_obrigatoria"]
    ][:10]

    situacao = SITUACAO_LABELS[modo_situacao][situacao_base]
    resumo = (
        f"A rodada analisou {len(itens)} fichas, com {metricas['bloq_nao_atende']} bloqueantes não atendidos, "
        f"{metricas['bloq_inconclusivo']} bloqueantes inconclusivos, "
        f"{metricas['obrig_nao_atende']} obrigatórios não atendidos e "
        f"{metricas['obrig_inconclusivo']} obrigatórios inconclusivos."
    )
    return {
        "situacao": situacao,
        "resumo": resumo,
        "metricas": metricas,
        "principais_achados": principais_achados,
        "encaminhamento": ENCAMINHAMENTOS[situacao],
        "situacao_base": situacao_base,
    }


def consolidar_rodada(rodada_dir: Path, modo_situacao: str = "padrao") -> dict[str, Any]:
    if modo_situacao not in SITUACAO_LABELS:
        raise ValueError("`modo_situacao` deve ser `padrao` ou `sintetico`.")
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    manifesto = read_json(caminhos["manifesto"])
    ppc_markdown = caminhos["ppc"].read_text(encoding="utf-8")
    contexto_estrutural = carregar_contexto_estrutural(rodada_dir)
    _validar_validacoes_cruzadas_em_dia(rodada_dir, metadata, manifesto, ppc_markdown, contexto_estrutural)
    validacoes_cruzadas = _carregar_validacoes_cruzadas(rodada_dir)
    validacoes_cruzadas, validacoes_sobrepostas = _aplicar_sobreposicoes_validacoes_cruzadas(
        rodada_dir,
        validacoes_cruzadas,
    )

    batches = [read_json(path) for path in sorted(caminhos["batches_dir"].glob("batch-*.json"))]
    if not batches:
        raise RuntimeError("Nenhum batch foi encontrado para consolidar.")

    itens: list[dict[str, Any]] = []
    execucoes_base_fichas: dict[str, dict[str, Any]] = {}
    faltantes: list[str] = []
    vistos_globalmente: set[str] = set()
    for batch in batches:
        status_path = caminhos["resultados_dir"] / f"{batch['batch_id']}.status.json"
        resposta_path = caminhos["resultados_dir"] / f"{batch['batch_id']}.resposta.json"
        if not status_path.exists():
            faltantes.extend(ficha["id"] for ficha in batch["fichas"])
            continue
        status = read_json(status_path)
        _validar_status_em_dia(rodada_dir, batch, status, manifesto, metadata, ppc_markdown, contexto_estrutural)
        if not resposta_path.exists():
            faltantes.extend(ficha["id"] for ficha in batch["fichas"])
            continue
        resposta = read_json(resposta_path)
        resultados_por_id = {item["ficha_id"]: item for item in resposta.get("resultados", [])}
        for ficha in batch["fichas"]:
            resultado = resultados_por_id.get(ficha["id"])
            if resultado is None:
                faltantes.append(ficha["id"])
                continue
            if ficha["id"] in vistos_globalmente:
                raise RuntimeError(f"A consolidação encontrou `ficha_id` duplicado entre lotes: {ficha['id']}")
            vistos_globalmente.add(ficha["id"])
            execucoes_base_fichas[ficha["id"]] = {
                "executado_em": status.get("executado_em"),
                "provider": status.get("provider"),
                "modelo": status.get("modelo"),
                "status_path": str(status_path),
                "resposta_path": str(resposta_path),
            }
            itens.append(
                {
                    "ficha_id": ficha["id"],
                    "titulo": ficha["titulo"],
                    "criticidade": ficha["criticidade"],
                    "batch_id": batch["batch_id"],
                    "estado": resultado["estado"],
                    "confianca": resultado["confianca"],
                    "justificativa": resultado["justificativa"],
                    "evidencias": resultado["evidencias"],
                    "lacunas": resultado["lacunas"],
                    "revisao_humana_obrigatoria": resultado["revisao_humana_obrigatoria"],
                    "secoes_preferenciais": ficha.get("secoes_preferenciais", []),
                }
            )

    if faltantes:
        raise RuntimeError(f"A consolidação falhou porque faltam resultados válidos para: {', '.join(sorted(set(faltantes)))}")

    itens = _aplicar_sobreposicoes_fichas(rodada_dir, itens, execucoes_base_fichas)
    item_risco_global = _derivar_risco_global(itens, contexto_estrutural.get("pre_validacoes", {}), validacoes_cruzadas)
    if item_risco_global is not None:
        itens = [item_risco_global if item["ficha_id"] == FICHA_RISCO_GLOBAL else item for item in itens]

    totais = {
        "fichas": len(itens),
        "atende": sum(1 for item in itens if item["estado"] == "ATENDE"),
        "nao_atende": sum(1 for item in itens if item["estado"] == "NAO_ATENDE"),
        "inconclusivo": sum(1 for item in itens if item["estado"] == "INCONCLUSIVO"),
        "nao_aplicavel": sum(1 for item in itens if item["estado"] == "NAO_APLICAVEL"),
    }
    resultados = {
        "metadata": {
            "curso": metadata["curso"],
            "campus": metadata["campus"],
            "modalidade": metadata["modalidade"],
            "data_analise": now_iso(),
        },
        "totais": totais,
        "itens": itens,
    }
    achados = {
        "achados": [
            item
            for item in itens
            if item["estado"] in {"NAO_ATENDE", "INCONCLUSIVO"} or item["revisao_humana_obrigatoria"]
        ]
    }
    parecer = _calcular_parecer(itens, modo_situacao=modo_situacao)

    write_json(caminhos["resultados_fichas"], resultados)
    write_json(caminhos["achados"], achados)
    write_json(caminhos["parecer_final"], parecer)
    if validacoes_sobrepostas:
        _escrever_validacoes_cruzadas_consolidadas(rodada_dir, validacoes_cruzadas)
    return {
        "resultados_fichas": caminhos["resultados_fichas"],
        "achados": caminhos["achados"],
        "parecer_final": caminhos["parecer_final"],
        "parecer": parecer,
    }
