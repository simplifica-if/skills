from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cnct_catalogo import comparar_ppc_com_cnct
from common import (
    FICHAS_DIR,
    load_fichas,
    now_iso,
    read_json,
    round_paths,
    sha256_file,
    valor_identificacao_preenchido,
    write_json,
)

STATUS_CONFORME = "CONFORME"
STATUS_NAO_CONFORME = "NAO_CONFORME"
STATUS_INCONCLUSIVO = "INCONCLUSIVO"
STATUS_NAO_APLICAVEL = "NAO_APLICAVEL"
STATUS_DETERMINADO = "DETERMINADO"


def _item_pre_validacao(
    item_id: str,
    descricao: str,
    status: str,
    criticidade: str,
    bloqueante: bool,
    fonte: str,
    detalhe: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "descricao": descricao,
        "status": status,
        "criticidade": criticidade,
        "bloqueante": bloqueante,
        "fonte": fonte,
        "detalhe": detalhe,
    }


def _scan_artefatos_conversao_paths(output_dir: Path) -> dict[str, str | None]:
    encontrados = {
        "dados": None,
        "matriz_curricular": None,
        "ementario": None,
        "markdown": None,
        "markdown_bruto": None,
    }
    if not output_dir.exists():
        return encontrados
    for caminho in output_dir.rglob("*"):
        if not caminho.is_file():
            continue
        nome = caminho.name.lower()
        if nome.endswith("_dados.json"):
            encontrados["dados"] = str(caminho)
        elif nome.endswith("_matriz_curricular.json"):
            encontrados["matriz_curricular"] = str(caminho)
        elif nome.endswith("_ementario.json"):
            encontrados["ementario"] = str(caminho)
        elif nome.endswith("-bruto.md"):
            encontrados["markdown_bruto"] = str(caminho)
        elif nome.endswith(".md"):
            encontrados["markdown"] = str(caminho)
    return encontrados


def localizar_artefatos_conversao_docx(rodada_dir: Path, metadata: dict[str, Any] | None = None) -> dict[str, str | None]:
    metadata = metadata or {}
    artefatos = dict(metadata.get("artefatos_conversao_docx") or {})
    if not artefatos:
        caminho_manifesto = round_paths(rodada_dir)["preparacao_docx"]
        if caminho_manifesto.exists():
            payload = _carregar_json_se_existir(str(caminho_manifesto))
            if payload:
                artefatos = dict(payload)
    output_dir = artefatos.get("output_dir")
    if output_dir:
        encontrados = _scan_artefatos_conversao_paths(Path(output_dir))
        for chave, valor in encontrados.items():
            artefatos.setdefault(chave, valor)
            if artefatos.get(chave) is None and valor is not None:
                artefatos[chave] = valor
    return artefatos


def _carregar_json_se_existir(path_str: str | None) -> dict[str, Any]:
    if not path_str:
        return {}
    path = Path(path_str)
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _origem_docx(metadata: dict[str, Any], artefatos_conversao: dict[str, str | None]) -> bool:
    arquivo_origem = str(metadata.get("arquivo_origem", "")).lower()
    return arquivo_origem.endswith(".docx") or bool(artefatos_conversao.get("output_dir"))


def _arquivo_artefato_disponivel(path_str: str | None) -> bool:
    return bool(path_str and Path(path_str).exists())


def _matriz_curricular_valida(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    anos = payload.get("anos")
    periodos = payload.get("periodos")
    total_componentes = payload.get("total_componentes")
    totais = payload.get("totais")
    return bool(anos or periodos or total_componentes or totais)


def _ementario_valido(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    componentes = payload.get("componentes")
    total_componentes = payload.get("total_componentes")
    return bool(componentes or total_componentes)


def _componentes_resumo(componentes: Any, limite: int = 20) -> list[str]:
    if not isinstance(componentes, list):
        return []
    nomes: list[str] = []
    for componente in componentes:
        if isinstance(componente, dict):
            nome = componente.get("nome") or componente.get("componente") or componente.get("unidade_curricular")
        else:
            nome = str(componente)
        nome_limpo = str(nome or "").strip()
        if nome_limpo and nome_limpo not in nomes:
            nomes.append(nome_limpo)
        if len(nomes) >= limite:
            break
    return nomes


def _resumir_matriz_curricular(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"disponivel": False}
    componentes = payload.get("componentes")
    if not isinstance(componentes, list):
        componentes = []
        for chave in ("anos", "periodos"):
            grupos = payload.get(chave)
            if isinstance(grupos, list):
                for grupo in grupos:
                    if isinstance(grupo, dict) and isinstance(grupo.get("componentes"), list):
                        componentes.extend(grupo["componentes"])
    return {
        "disponivel": True,
        "chaves": sorted(payload.keys()),
        "total_componentes": payload.get("total_componentes") or len(componentes) or None,
        "totais": payload.get("totais") if isinstance(payload.get("totais"), dict) else {},
        "componentes_amostra": _componentes_resumo(componentes),
    }


def _resumir_ementario(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"disponivel": False}
    componentes = payload.get("componentes") if isinstance(payload.get("componentes"), list) else []
    return {
        "disponivel": True,
        "chaves": sorted(payload.keys()),
        "total_componentes": payload.get("total_componentes") or len(componentes) or None,
        "componentes_amostra": _componentes_resumo(componentes),
    }


def _extrair_referencias_candidatas(texto: str, limite: int = 80) -> dict[str, Any]:
    linhas = [linha.strip() for linha in texto.splitlines()]
    em_referencias = False
    referencias: list[str] = []
    for linha in linhas:
        if re.match(r"^#{1,4}\s*(refer[eê]ncias|bibliografia)\b", linha, flags=re.IGNORECASE):
            em_referencias = True
            continue
        if em_referencias and re.match(r"^#{1,4}\s+\S", linha):
            break
        if em_referencias and linha:
            referencias.append(linha)
        if len(referencias) >= limite:
            break

    mencoes_normativas: list[str] = []
    padrao_normativo = re.compile(
        r"\b(lei|decreto|resolu[çc][ãa]o|parecer|portaria|instru[çc][ãa]o normativa|cnct|ifpr|cne|consup)\b",
        flags=re.IGNORECASE,
    )
    for linha in linhas:
        if linha and padrao_normativo.search(linha) and linha not in mencoes_normativas:
            mencoes_normativas.append(linha)
        if len(mencoes_normativas) >= limite:
            break

    return {
        "secao_referencias_detectada": bool(referencias),
        "referencias_amostra": referencias,
        "mencoes_normativas_amostra": mencoes_normativas,
    }


def _extrair_sinais_cnct(dados_conversao: dict[str, Any]) -> dict[str, Any]:
    dados_extraidos = dados_conversao.get("dados_extraidos", {}) if isinstance(dados_conversao.get("dados_extraidos"), dict) else {}
    candidatos = {}
    for chave in (
        "nome_curso",
        "curso_cnct",
        "eixo_tecnologico",
        "perfil_profissional",
        "carga_horaria_minima",
        "carga_horaria_minima_cnct",
        "profissao_regulamentada",
    ):
        if chave in dados_extraidos:
            candidatos[chave] = dados_extraidos[chave]
    return {
        "disponivel": bool(candidatos),
        "sinais": candidatos,
    }


def _resolver_texto(rodada_dir: Path) -> str:
    return (round_paths(rodada_dir)["ppc"]).read_text(encoding="utf-8")


def _extrair_modalidade(metadata: dict[str, Any], texto: str, dados_conversao: dict[str, Any]) -> dict[str, Any]:
    dados_extraidos = dados_conversao.get("dados_extraidos", {}) if isinstance(dados_conversao.get("dados_extraidos"), dict) else {}
    fontes = [
        ("dados_extraidos.forma_oferta", str(dados_extraidos.get("forma_oferta", "")).strip()),
        ("metadata.forma_oferta", str(metadata.get("forma_oferta", "")).strip()),
        ("dados_extraidos.modalidade", str(dados_extraidos.get("modalidade", "")).strip()),
        ("metadata.modalidade", str(metadata.get("modalidade", "")).strip()),
    ]
    for fonte, valor in fontes:
        valor_normalizado = valor.lower()
        if "integrado" in valor_normalizado:
            return {"valor": True, "status": STATUS_DETERMINADO, "fonte": fonte, "evidencia": valor}
        if "subsequente" in valor_normalizado or "concomitante" in valor_normalizado:
            return {"valor": False, "status": STATUS_DETERMINADO, "fonte": fonte, "evidencia": valor}

    texto_normalizado = texto.lower()
    if re.search(r"modalidade\s*[:\-]\s*integrado", texto_normalizado) or re.search(r"técnico integrado|tecnico integrado", texto_normalizado):
        return {"valor": True, "status": STATUS_DETERMINADO, "fonte": "PPC.md", "evidencia": "menção textual à modalidade integrada"}
    if re.search(r"modalidade\s*[:\-]\s*(subsequente|concomitante)", texto_normalizado):
        return {"valor": False, "status": STATUS_DETERMINADO, "fonte": "PPC.md", "evidencia": "menção textual à modalidade não integrada"}
    contagens = {
        "integrado": texto_normalizado.count("integrado"),
        "subsequente": texto_normalizado.count("subsequente"),
        "concomitante": texto_normalizado.count("concomitante"),
    }
    if contagens["integrado"] >= 3 and contagens["integrado"] > (contagens["subsequente"] + contagens["concomitante"]):
        return {"valor": True, "status": STATUS_DETERMINADO, "fonte": "PPC.md", "evidencia": f"{contagens['integrado']} ocorrências de 'integrado'"}
    return {"valor": None, "status": STATUS_INCONCLUSIVO, "fonte": "PPC.md", "evidencia": "modalidade não determinada com segurança"}


def _inferir_booleano_por_padrao(
    texto: str,
    *,
    patterns_true: list[str],
    patterns_false: list[str] | None = None,
    fonte: str,
) -> dict[str, Any]:
    texto_normalizado = texto.lower()
    for pattern in patterns_false or []:
        match = re.search(pattern, texto_normalizado)
        if match:
            return {"valor": False, "status": STATUS_DETERMINADO, "fonte": fonte, "evidencia": match.group(0)}
    for pattern in patterns_true:
        match = re.search(pattern, texto_normalizado)
        if match:
            return {"valor": True, "status": STATUS_DETERMINADO, "fonte": fonte, "evidencia": match.group(0)}
    return {"valor": None, "status": STATUS_INCONCLUSIVO, "fonte": fonte, "evidencia": "não determinado com segurança"}


def inferir_condicionais_rodada(rodada_dir: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or read_json(round_paths(rodada_dir)["metadata"])
    texto = _resolver_texto(rodada_dir)
    artefatos_conversao = localizar_artefatos_conversao_docx(rodada_dir, metadata)
    dados_conversao = _carregar_json_se_existir(artefatos_conversao.get("dados"))

    curso_regulamentado = None
    dados_extraidos = dados_conversao.get("dados_extraidos", {}) if isinstance(dados_conversao.get("dados_extraidos"), dict) else {}
    if isinstance(dados_extraidos.get("profissao_regulamentada"), bool):
        curso_regulamentado = {
            "valor": bool(dados_extraidos["profissao_regulamentada"]),
            "status": STATUS_DETERMINADO,
            "fonte": "dados_extraidos.profissao_regulamentada",
            "evidencia": str(dados_extraidos["profissao_regulamentada"]),
        }
    else:
        texto_normalizado = texto.lower()
        if re.search(r"não regulamentad[ao]", texto_normalizado):
            curso_regulamentado = {"valor": False, "status": STATUS_DETERMINADO, "fonte": "PPC.md", "evidencia": "menção a curso/profissão não regulamentada"}
        elif re.search(r"registro profissional|conselho profissional|profissão regulamentad[ao]|legislação que regulamente a profissão", texto_normalizado):
            curso_regulamentado = {"valor": True, "status": STATUS_DETERMINADO, "fonte": "PPC.md", "evidencia": "menção a conselho/registro profissional ou profissão regulamentada"}
        else:
            curso_regulamentado = {"valor": None, "status": STATUS_INCONCLUSIVO, "fonte": "PPC.md", "evidencia": "situação regulatória não determinada"}

    condicionais = {
        "modalidade_integrado": _extrair_modalidade(metadata, texto, dados_conversao),
        "tem_estagio": _inferir_booleano_por_padrao(
            texto,
            patterns_true=[
                r"##?\s*[\d\.]*\s*est[áa]gio",
                r"est[áa]gio curricular",
                r"est[áa]gio supervisionado",
                r"realiza[çc][ãa]o de est[áa]gio",
            ],
            patterns_false=[
                r"n[aã]o prev[eê]\s+est[áa]gio",
                r"sem est[áa]gio",
                r"curso n[aã]o exige est[áa]gio",
            ],
            fonte="PPC.md",
        ),
        "tem_tfc": _inferir_booleano_por_padrao(
            texto,
            patterns_true=[
                r"\btfc\b",
                r"trabalho de conclus[aã]o",
                r"##?\s*[\d\.]*\s*tfc",
            ],
            patterns_false=[r"n[aã]o prev[eê]\s+tfc", r"sem trabalho de conclus[aã]o"],
            fonte="PPC.md",
        ),
        "tem_aee": _inferir_booleano_por_padrao(
            texto,
            patterns_true=[
                r"\baee\b",
                r"atendimento educacional especializado",
                r"adapta[çc][ãa]o curricular",
                r"flexibiliza[çc][ãa]o curricular",
            ],
            patterns_false=[],
            fonte="PPC.md",
        ),
        "tem_nee": _inferir_booleano_por_padrao(
            texto,
            patterns_true=[
                r"\bnee\b",
                r"necessidades educacionais espec[íi]ficas",
                r"necessidades educacionais especiais",
                r"estudantes? com defici[eê]ncia",
                r"p[úu]blico[- ]alvo da educa[çc][ãa]o especial",
            ],
            patterns_false=[],
            fonte="PPC.md",
        ),
        "intervalo_pedagogico_contabilizado": _inferir_booleano_por_padrao(
            texto,
            patterns_true=[
                r"intervalo pedag[óo]gico.{0,80}(contabilizad|computad|carga hor[áa]ria)",
                r"(contabilizad|computad).{0,80}intervalo pedag[óo]gico",
            ],
            patterns_false=[
                r"intervalo pedag[óo]gico.{0,80}n[aã]o.{0,30}(contabilizad|computad)",
                r"n[aã]o.{0,30}(contabilizad|computad).{0,80}intervalo pedag[óo]gico",
            ],
            fonte="PPC.md",
        ),
        "curso_regulamentado": curso_regulamentado,
    }
    return {
        "rodada_dir": str(Path(rodada_dir).resolve()),
        "gerado_em": now_iso(),
        "condicionais": condicionais,
    }


def gerar_contexto_estrutural_rodada(
    rodada_dir: Path,
    metadata: dict[str, Any] | None = None,
    artefatos_conversao: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    metadata = metadata or read_json(round_paths(rodada_dir)["metadata"])
    artefatos_conversao = artefatos_conversao or localizar_artefatos_conversao_docx(rodada_dir, metadata)
    texto = _resolver_texto(rodada_dir)
    matriz_payload = _carregar_json_se_existir(artefatos_conversao.get("matriz_curricular"))
    ementario_payload = _carregar_json_se_existir(artefatos_conversao.get("ementario"))
    dados_conversao = _carregar_json_se_existir(artefatos_conversao.get("dados"))
    sinais_cnct = _extrair_sinais_cnct(dados_conversao)
    comparacao_cnct = comparar_ppc_com_cnct(metadata, dados_conversao, matriz_payload)
    cnct_payload = {
        **sinais_cnct,
        "comparacao_catalogo": comparacao_cnct,
    }
    write_json(round_paths(rodada_dir)["cnct_comparacao"], comparacao_cnct)
    payload = {
        "rodada_dir": str(Path(rodada_dir).resolve()),
        "gerado_em": now_iso(),
        "observacao": (
            "Contexto estrutural organizado para apoiar a revisão por agente. "
            "Os dados abaixo não fecham mérito de conformidade por código."
        ),
        "artefatos": {
            "dados": artefatos_conversao.get("dados"),
            "matriz_curricular": artefatos_conversao.get("matriz_curricular"),
            "ementario": artefatos_conversao.get("ementario"),
            "cnct_comparacao": str(round_paths(rodada_dir)["cnct_comparacao"]),
            "markdown": artefatos_conversao.get("markdown"),
            "markdown_bruto": artefatos_conversao.get("markdown_bruto"),
        },
        "representacao_grafica": dados_conversao.get("representacao_grafica", {"encontrada": False}),
        "matriz_curricular": _resumir_matriz_curricular(matriz_payload),
        "ementario": _resumir_ementario(ementario_payload),
        "referencias": _extrair_referencias_candidatas(texto),
        "cnct": cnct_payload,
    }
    write_json(round_paths(rodada_dir)["contexto_estrutural"], payload)
    return payload


def gerar_pre_validacoes_rodada(rodada_dir: Path, fichas_dir: Path | None = None) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    manifesto = read_json(caminhos["manifesto"])
    artefatos_conversao = localizar_artefatos_conversao_docx(rodada_dir, metadata)
    condicionais_payload = inferir_condicionais_rodada(rodada_dir, metadata)
    contexto_estrutural = gerar_contexto_estrutural_rodada(rodada_dir, metadata, artefatos_conversao)
    rodada_docx = _origem_docx(metadata, artefatos_conversao)
    matriz_payload = _carregar_json_se_existir(artefatos_conversao.get("matriz_curricular"))
    ementario_payload = _carregar_json_se_existir(artefatos_conversao.get("ementario"))
    matriz_disponivel = _arquivo_artefato_disponivel(artefatos_conversao.get("matriz_curricular"))
    ementario_disponivel = _arquivo_artefato_disponivel(artefatos_conversao.get("ementario"))
    texto = caminhos["ppc"].read_text(encoding="utf-8") if caminhos["ppc"].exists() else ""
    fichas = load_fichas(fichas_dir or FICHAS_DIR)
    metadata_curso_campus_ok = caminhos["metadata"].exists() and all(
        valor_identificacao_preenchido(metadata.get(chave))
        for chave in ("curso", "campus")
    )
    metadata_modalidade_ok = valor_identificacao_preenchido(metadata.get("modalidade")) or valor_identificacao_preenchido(
        metadata.get("forma_oferta")
    )
    metadata_minimos_ok = metadata_curso_campus_ok and metadata_modalidade_ok

    obrigatorias = [
        _item_pre_validacao(
            "PV-001",
            "PPC.md existe e contém texto utilizável",
            STATUS_CONFORME if caminhos["ppc"].exists() and texto.strip() else STATUS_NAO_CONFORME,
            "BLOQ",
            True,
            "PPC.md",
            "Arquivo presente e não vazio." if caminhos["ppc"].exists() and texto.strip() else "Arquivo ausente ou vazio.",
        ),
        _item_pre_validacao(
            "PV-002",
            "metadata.json existe com campos mínimos",
            STATUS_CONFORME if metadata_minimos_ok else STATUS_NAO_CONFORME,
            "BLOQ",
            True,
            "metadata.json",
            "Curso, campus e forma de oferta/modalidade informados."
            if metadata_minimos_ok
            else "Metadados mínimos ausentes ou não identificados.",
        ),
        _item_pre_validacao(
            "PV-003",
            "manifesto-rodada.json existe e o hash do PPC coincide",
            STATUS_CONFORME
            if caminhos["manifesto"].exists() and caminhos["ppc"].exists() and manifesto.get("ppc_sha256") == sha256_file(caminhos["ppc"])
            else STATUS_NAO_CONFORME,
            "BLOQ",
            True,
            "manifesto-rodada.json",
            "Hash do PPC consistente com o manifesto." if caminhos["manifesto"].exists() and caminhos["ppc"].exists() and manifesto.get("ppc_sha256") == sha256_file(caminhos["ppc"]) else "Manifesto ausente ou divergente do PPC atual.",
        ),
        _item_pre_validacao(
            "PV-004",
            "Catálogo de fichas canônicas disponível",
            STATUS_CONFORME if fichas else STATUS_NAO_CONFORME,
            "BLOQ",
            True,
            str((fichas_dir or FICHAS_DIR).resolve()),
            f"{len(fichas)} fichas disponíveis." if fichas else "Nenhuma ficha JSON foi encontrada.",
        ),
    ]

    batch_files = sorted(caminhos["batches_dir"].glob("batch-*.json"))
    if batch_files:
        ids_catalogo = {ficha["id"] for ficha in fichas}
        ids_batches: list[str] = []
        for batch_path in batch_files:
            payload = read_json(batch_path)
            ids_batches.extend(ficha["id"] for ficha in payload.get("fichas", []))
        ids_unicos = set(ids_batches)
        duplicados = sorted({ficha_id for ficha_id in ids_batches if ids_batches.count(ficha_id) > 1})
        faltantes = sorted(ids_catalogo - ids_unicos)
        extras = sorted(ids_unicos - ids_catalogo)
        status_batches = STATUS_CONFORME if not duplicados and not faltantes and not extras else STATUS_NAO_CONFORME
        detalhe_batches = "Batches cobrem o catálogo sem duplicidade." if status_batches == STATUS_CONFORME else (
            f"Duplicados: {duplicados or 'nenhum'}; faltantes: {faltantes or 'nenhum'}; extras: {extras or 'nenhum'}."
        )
    else:
        status_batches = STATUS_INCONCLUSIVO
        detalhe_batches = "Batches ainda não foram gerados para a rodada."
    obrigatorias.append(
        _item_pre_validacao(
            "PV-005",
            "Batches gerados cobrem integralmente o catálogo de fichas",
            status_batches,
            "BLOQ",
            True,
            str(caminhos["batches_dir"]),
            detalhe_batches,
        )
    )
    opcionais = [
        _item_pre_validacao(
            "PV-101",
            "Conversão DOCX registrada para a rodada",
            STATUS_CONFORME if artefatos_conversao.get("output_dir") else STATUS_NAO_APLICAVEL,
            "OBRIG",
            False,
            "preparacao-docx.json",
            "Artefatos da conversão DOCX localizados." if artefatos_conversao.get("output_dir") else "Rodada Markdown-first sem conversão DOCX.",
        ),
        _item_pre_validacao(
            "PV-102",
            "Matriz curricular estrutural disponível quando a rodada vem de DOCX",
            STATUS_CONFORME if matriz_disponivel else STATUS_NAO_CONFORME if rodada_docx else STATUS_NAO_APLICAVEL,
            "OBRIG",
            False,
            artefatos_conversao.get("matriz_curricular") or "artefatos da conversão DOCX",
            "Matriz curricular em JSON localizada."
            if matriz_disponivel
            else "Rodada DOCX sem matriz curricular estrutural disponível; tratar como lacuna para revisão por agente."
            if rodada_docx
            else "Rodada Markdown-first sem exigência de matriz curricular estruturada.",
        ),
        _item_pre_validacao(
            "PV-103",
            "Ementário estrutural disponível quando a rodada vem de DOCX",
            STATUS_CONFORME if ementario_disponivel else STATUS_NAO_CONFORME if rodada_docx else STATUS_NAO_APLICAVEL,
            "OBRIG",
            False,
            artefatos_conversao.get("ementario") or "artefatos da conversão DOCX",
            "Ementário em JSON localizado."
            if ementario_disponivel
            else "Rodada DOCX sem ementário estrutural disponível; tratar como lacuna para revisão por agente."
            if rodada_docx
            else "Rodada Markdown-first sem exigência de ementário estruturado.",
        ),
        _item_pre_validacao(
            "PV-104",
            "Matriz curricular contém anos, períodos ou totais válidos",
            STATUS_CONFORME if _matriz_curricular_valida(matriz_payload) else STATUS_NAO_CONFORME if rodada_docx else STATUS_NAO_APLICAVEL,
            "OBRIG",
            False,
            artefatos_conversao.get("matriz_curricular") or "artefatos da conversão DOCX",
            "Estrutura mínima da matriz curricular confirmada."
            if _matriz_curricular_valida(matriz_payload)
            else "Matriz curricular ausente ou sem estrutura mínima utilizável; tratar como lacuna para revisão por agente."
            if rodada_docx
            else "Rodada Markdown-first sem validação estrutural de matriz.",
        ),
        _item_pre_validacao(
            "PV-105",
            "Ementário contém componentes com estrutura utilizável",
            STATUS_CONFORME if _ementario_valido(ementario_payload) else STATUS_NAO_CONFORME if rodada_docx else STATUS_NAO_APLICAVEL,
            "OBRIG",
            False,
            artefatos_conversao.get("ementario") or "artefatos da conversão DOCX",
            "Estrutura mínima do ementário confirmada."
            if _ementario_valido(ementario_payload)
            else "Ementário ausente ou sem componentes utilizáveis; tratar como lacuna para revisão por agente."
            if rodada_docx
            else "Rodada Markdown-first sem validação estrutural de ementário.",
        ),
        _item_pre_validacao(
            "PV-106",
            "Situação regulatória do curso determinada",
            STATUS_DETERMINADO
            if condicionais_payload["condicionais"]["curso_regulamentado"]["status"] == STATUS_DETERMINADO
            else STATUS_INCONCLUSIVO,
            "OBRIG",
            False,
            condicionais_payload["condicionais"]["curso_regulamentado"]["fonte"],
            condicionais_payload["condicionais"]["curso_regulamentado"]["evidencia"],
        ),
    ]

    bloqueios = [item["id"] for item in obrigatorias if item["bloqueante"] and item["status"] == STATUS_NAO_CONFORME]
    payload = {
        "rodada_dir": str(Path(rodada_dir).resolve()),
        "gerado_em": now_iso(),
        "obrigatorias": obrigatorias,
        "estruturais_opcionais": opcionais,
        "bloqueios": bloqueios,
        "tem_bloqueios": bool(bloqueios),
    }
    write_json(caminhos["pre_validacoes"], payload)
    write_json(caminhos["condicionais_rodada"], condicionais_payload)
    return {
        "pre_validacoes_path": caminhos["pre_validacoes"],
        "condicionais_path": caminhos["condicionais_rodada"],
        "contexto_estrutural_path": caminhos["contexto_estrutural"],
        "pre_validacoes": payload,
        "condicionais": condicionais_payload,
        "contexto_estrutural": contexto_estrutural,
    }


def carregar_contexto_estrutural(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    pre_validacoes = read_json(caminhos["pre_validacoes"]) if caminhos["pre_validacoes"].exists() else {}
    condicionais = read_json(caminhos["condicionais_rodada"]) if caminhos["condicionais_rodada"].exists() else {}
    contexto_estrutural = read_json(caminhos["contexto_estrutural"]) if caminhos["contexto_estrutural"].exists() else {}
    return {
        "pre_validacoes": pre_validacoes,
        "condicionais_rodada": condicionais,
        "contexto_estrutural": contexto_estrutural,
    }


def verificar_bloqueios_pre_validacao(rodada_dir: Path, fichas_dir: Path | None = None) -> dict[str, Any]:
    payload = gerar_pre_validacoes_rodada(rodada_dir, fichas_dir=fichas_dir)
    if payload["pre_validacoes"]["tem_bloqueios"]:
        raise RuntimeError(
            "A rodada possui bloqueios estruturais e não pode seguir para `avaliar-todos`: "
            + ", ".join(payload["pre_validacoes"]["bloqueios"])
        )
    return payload
