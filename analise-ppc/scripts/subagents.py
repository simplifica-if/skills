from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from common import (
    DEFAULT_GROUP_SIZE,
    FICHAS_DIR,
    ensure_directory,
    load_fichas,
    read_json,
    round_paths,
    sha256_json_payload,
    write_json,
)
from cnct_catalogo import gerar_contexto_cnct_rodada

FICHA_REPRESENTACAO_GRAFICA = "CT-CURR-10"


def carregar_fichas_ordenadas(fichas_dir: Path | None = None) -> list[dict[str, Any]]:
    return sorted(load_fichas(fichas_dir or FICHAS_DIR), key=lambda ficha: str(ficha.get("id", "")))


def agrupar_fichas(
    fichas: list[dict[str, Any]],
    tamanho_grupo: int = DEFAULT_GROUP_SIZE,
) -> list[dict[str, Any]]:
    if tamanho_grupo <= 0:
        raise ValueError("O tamanho do grupo precisa ser maior que zero.")
    grupos: list[dict[str, Any]] = []
    for indice in range(0, len(fichas), tamanho_grupo):
        grupo_fichas = fichas[indice : indice + tamanho_grupo]
        numero = len(grupos) + 1
        inicio = indice + 1
        fim = indice + len(grupo_fichas)
        grupos.append(
            {
                "grupo_id": f"grupo-{numero:03d}",
                "intervalo": f"{inicio}-{fim}",
                "total_fichas": len(grupo_fichas),
                "fichas": grupo_fichas,
            }
        )
    return grupos


def ficha_requer_contexto_cnct(ficha: dict[str, Any]) -> bool:
    texto = " ".join(
        str(ficha.get(campo, ""))
        for campo in (
            "titulo",
            "pergunta",
            "rubrica",
            "boa_evidencia",
            "ma_evidencia",
            "escalonar_quando",
        )
    )
    texto += " " + " ".join(str(item) for item in ficha.get("consultas", []))
    return "cnct" in texto.casefold() or "contexto_estrutural.cnct" in texto.casefold()


def _read_json_if_exists(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def _preparacao_docx(caminhos: dict[str, Path]) -> dict[str, Any]:
    if not caminhos["preparacao_docx"].exists():
        return {}
    payload = read_json(caminhos["preparacao_docx"])
    return payload if isinstance(payload, dict) else {}


def _resolver_path_artefato(valor: Any) -> str | None:
    if not valor:
        return None
    path = Path(str(valor))
    return str(path.resolve()) if path.exists() else None


def _resumo_matriz(matriz: dict[str, Any]) -> dict[str, Any]:
    return {
        "totais": matriz.get("totais", {}),
        "componentes_total": len(matriz.get("componentes", [])) if isinstance(matriz.get("componentes"), list) else None,
        "series_total": len(matriz.get("series", [])) if isinstance(matriz.get("series"), list) else None,
    }


def _resumo_ementario(ementario: dict[str, Any]) -> dict[str, Any]:
    componentes = ementario.get("componentes")
    if not isinstance(componentes, list):
        componentes = ementario.get("ementas") if isinstance(ementario.get("ementas"), list) else []
    nomes = []
    for componente in componentes[:30]:
        if isinstance(componente, dict):
            nome = componente.get("nome") or componente.get("componente") or componente.get("titulo")
            if nome:
                nomes.append(str(nome))
    return {
        "componentes_total": len(componentes),
        "amostra_componentes": nomes,
    }


def gerar_contexto_estrutural_subagents(rodada_dir: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    preparacao = _preparacao_docx(caminhos)
    dados = _read_json_if_exists(preparacao.get("dados"))
    matriz = _read_json_if_exists(preparacao.get("matriz_curricular"))
    ementario = _read_json_if_exists(preparacao.get("ementario"))
    contexto = {
        "artefatos": {
            "dados": _resolver_path_artefato(preparacao.get("dados")),
            "matriz_curricular": _resolver_path_artefato(preparacao.get("matriz_curricular")),
            "ementario": _resolver_path_artefato(preparacao.get("ementario")),
            "markdown_bruto": _resolver_path_artefato(preparacao.get("markdown_bruto")),
        },
        "identificacao_extraida": dados.get("dados_extraidos", dados) if isinstance(dados, dict) else {},
        "matriz_curricular": _resumo_matriz(matriz),
        "ementario": _resumo_ementario(ementario),
    }
    write_json(caminhos["contexto_estrutural_subagents"], contexto)
    return contexto


def _anexos_visuais(caminhos: dict[str, Path]) -> list[dict[str, str]]:
    preparacao = _preparacao_docx(caminhos)
    dados = _read_json_if_exists(preparacao.get("dados"))
    representacao = dados.get("representacao_grafica") if isinstance(dados, dict) else None
    if not isinstance(representacao, dict) or not representacao.get("extraida"):
        return []
    caminho = representacao.get("caminho")
    if not caminho:
        return []
    imagem = Path(str(caminho))
    if not imagem.is_absolute():
        base = Path(str(preparacao.get("dados") or "")).resolve().parent
        imagem = base / imagem
    if not imagem.exists():
        return []
    return [
        {
            "ficha_id": FICHA_REPRESENTACAO_GRAFICA,
            "tipo": "imagem",
            "descricao": "Representação gráfica do processo formativo extraída do PPC.",
            "arquivo": str(imagem.resolve()),
        }
    ]


def _adicionar_contextos_grupo(
    grupo: dict[str, Any],
    *,
    cnct_contexto: dict[str, Any],
    contexto_estrutural: dict[str, Any],
    anexos_visuais: list[dict[str, str]],
) -> None:
    contextos: dict[str, Any] = {}
    requer_cnct = any(ficha_requer_contexto_cnct(ficha) for ficha in grupo["fichas"])
    grupo["requer_contexto_cnct"] = requer_cnct
    if requer_cnct:
        contextos["cnct"] = cnct_contexto
    grupo["requer_contexto_estrutural"] = True
    contextos["estrutura"] = contexto_estrutural
    anexos_grupo = [
        anexo
        for anexo in anexos_visuais
        if any(ficha.get("id") == anexo.get("ficha_id") for ficha in grupo["fichas"])
    ]
    grupo["requer_anexos_visuais"] = bool(anexos_grupo)
    if anexos_grupo:
        contextos["anexos_visuais"] = anexos_grupo
    grupo["contextos"] = contextos


def montar_grupos_subagents(
    rodada_dir: Path,
    tamanho_grupo: int = DEFAULT_GROUP_SIZE,
    fichas_dir: Path | None = None,
) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    if not caminhos["ppc"].exists():
        raise FileNotFoundError(f"PPC.md não encontrado: {caminhos['ppc']}")
    metadata = read_json(caminhos["metadata"]) if caminhos["metadata"].exists() else {}
    fichas = carregar_fichas_ordenadas(fichas_dir)
    grupos = agrupar_fichas(fichas, tamanho_grupo=tamanho_grupo)
    cnct_contexto = gerar_contexto_cnct_rodada(rodada_dir)
    contexto_estrutural = gerar_contexto_estrutural_subagents(rodada_dir)
    anexos_visuais = _anexos_visuais(caminhos)
    for grupo in grupos:
        _adicionar_contextos_grupo(
            grupo,
            cnct_contexto=cnct_contexto,
            contexto_estrutural=contexto_estrutural,
            anexos_visuais=anexos_visuais,
        )
    payload = {
        "rodada_dir": str(caminhos["rodada_dir"]),
        "ppc_markdown": str(caminhos["ppc"]),
        "prompt_template": str((Path(__file__).resolve().parents[1] / "prompts" / "subagent-lote-fichas.md")),
        "sintese_transversal_template": str((Path(__file__).resolve().parents[1] / "prompts" / "sintese-transversal.md")),
        "cnct_contexto_path": str(caminhos["cnct_contexto"]),
        "cnct_contexto": cnct_contexto,
        "contexto_estrutural_path": str(caminhos["contexto_estrutural_subagents"]),
        "contexto_estrutural": contexto_estrutural,
        "anexos_visuais": anexos_visuais,
        "curso": metadata.get("curso", ""),
        "total_fichas": len(fichas),
        "tamanho_grupo": tamanho_grupo,
        "grupos": grupos,
    }
    write_json(caminhos["grupos_subagents"], payload)
    return payload


def montar_grupo_avulso(
    rodada_dir: Path,
    ficha_ids: list[str],
    fichas_dir: Path | None = None,
) -> dict[str, Any]:
    if not ficha_ids:
        raise ValueError("Informe ao menos uma ficha para montar o grupo avulso.")
    caminhos = round_paths(rodada_dir)
    fichas_por_id = {ficha["id"]: ficha for ficha in carregar_fichas_ordenadas(fichas_dir)}
    faltantes = [ficha_id for ficha_id in ficha_ids if ficha_id not in fichas_por_id]
    if faltantes:
        raise ValueError("Fichas não encontradas: " + ", ".join(faltantes))
    selecionadas = [deepcopy(fichas_por_id[ficha_id]) for ficha_id in ficha_ids]
    grupo = {
        "grupo_id": "avulso-" + sha256_json_payload({"ficha_ids": ficha_ids})[:12],
        "intervalo": "avulso",
        "total_fichas": len(selecionadas),
        "fichas": selecionadas,
    }
    cnct_contexto = gerar_contexto_cnct_rodada(rodada_dir)
    contexto_estrutural = gerar_contexto_estrutural_subagents(rodada_dir)
    anexos_visuais = _anexos_visuais(caminhos)
    _adicionar_contextos_grupo(
        grupo,
        cnct_contexto=cnct_contexto,
        contexto_estrutural=contexto_estrutural,
        anexos_visuais=anexos_visuais,
    )
    payload = {
        "rodada_dir": str(caminhos["rodada_dir"]),
        "ppc_markdown": str(caminhos["ppc"]),
        "prompt_template": str((Path(__file__).resolve().parents[1] / "prompts" / "subagent-lote-fichas.md")),
        "grupo": grupo,
    }
    destino = ensure_directory(caminhos["grupos_avulsos_dir"]) / f"{grupo['grupo_id']}.json"
    write_json(destino, payload)
    payload["grupo_avulso_path"] = str(destino)
    return payload


def mesclar_resultados_avulsos(
    rodada_dir: Path,
    resultados_base_path: Path,
    resultados_avulsos_path: Path,
    saida_path: Path | None = None,
) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    base_path = resultados_base_path if resultados_base_path.is_absolute() else caminhos["suporte_dir"] / resultados_base_path
    avulso_path = resultados_avulsos_path if resultados_avulsos_path.is_absolute() else caminhos["suporte_dir"] / resultados_avulsos_path
    saida = saida_path or resultados_base_path
    saida_resolvida = saida if saida.is_absolute() else caminhos["suporte_dir"] / saida
    base = read_json(base_path)
    avulso = read_json(avulso_path)
    grupos_base = list(base.get("grupos", []))
    resultados_avulsos: list[dict[str, Any]] = []
    if isinstance(avulso.get("grupos"), list):
        for grupo in avulso["grupos"]:
            resultados_avulsos.extend(grupo.get("resultados", []))
    elif isinstance(avulso.get("resultados"), list):
        resultados_avulsos.extend(avulso["resultados"])
    else:
        raise ValueError("O resultado avulso precisa conter `grupos[]` ou `resultados[]`.")
    ids_avulsos = {str(item.get("ficha_id")) for item in resultados_avulsos}
    grupos_mesclados = []
    for grupo in grupos_base:
        grupo_copia = dict(grupo)
        grupo_copia["resultados"] = [
            item for item in grupo.get("resultados", []) if str(item.get("ficha_id")) not in ids_avulsos
        ]
        if grupo_copia["resultados"]:
            grupos_mesclados.append(grupo_copia)
    grupos_mesclados.append(
        {
            "grupo_id": str(avulso.get("grupo_id") or "reavaliacao-" + sha256_json_payload(sorted(ids_avulsos))[:12]),
            "tipo": "reavaliacao",
            "resultados": resultados_avulsos,
        }
    )
    payload = dict(base)
    payload["grupos"] = grupos_mesclados
    payload.setdefault("metadata", {})
    payload["metadata"]["reavaliacoes_mescladas"] = sorted(ids_avulsos)
    write_json(saida_resolvida, payload)
    return {
        "resultados_path": str(saida_resolvida),
        "fichas_substituidas": sorted(ids_avulsos),
        "total_grupos": len(grupos_mesclados),
    }
