from __future__ import annotations

import csv
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from common import APP_DIR, sha256_file

CNCT_CATALOGO_PATH = APP_DIR / "base-analise" / "dados" / "cnct" / "catalogo_cnct.csv"
CNCT_CAMPOS = (
    ("Eixo Tecnológico", "eixo_tecnologico"),
    ("Área Tecnológica", "area_tecnologica"),
    ("Denominação do Curso", "denominacao"),
    ("Perfil Profissional de Conclusão", "perfil_profissional"),
    ("Carga Horária Mínima", "carga_horaria_minima"),
    ("Descrição Carga Horária Mínima", "descricao_carga_horaria_minima"),
    ("Pré-Requisitos para Ingresso", "pre_requisitos_ingresso"),
    ("Itinerários Formativos", "itinerarios_formativos"),
    ("Campo de Atuação", "campo_atuacao"),
    ("Ocupações CBO Associadas", "ocupacoes_cbo"),
    ("Infraestrutura Mínima", "infraestrutura_minima"),
    ("Legislação Profissional", "legislacao_profissional"),
)


def normalizar_texto_cnct(texto: Any) -> str:
    normalizado = unicodedata.normalize("NFD", str(texto or ""))
    normalizado = "".join(char for char in normalizado if unicodedata.category(char) != "Mn")
    normalizado = normalizado.casefold()
    normalizado = re.sub(r"[^a-z0-9]+", " ", normalizado)
    return " ".join(normalizado.split())


def normalizar_denominacao_cnct(texto: Any) -> str:
    normalizado = normalizar_texto_cnct(texto)
    normalizado = re.sub(r"^curso\s+", "", normalizado)
    return normalizado.strip()


def extrair_numero_horas(valor: Any) -> int | None:
    if valor is None:
        return None
    match = re.search(r"\d[\d.]*", str(valor))
    if not match:
        return None
    digitos = re.sub(r"\D", "", match.group(0))
    return int(digitos) if digitos else None


def _normalizar_linha_csv(linha: dict[str, str]) -> dict[str, str]:
    return {str(chave or "").lstrip("\ufeff").strip(): valor for chave, valor in linha.items()}


def carregar_catalogo_cnct(catalogo_path: Path | None = None) -> list[dict[str, Any]]:
    caminho = catalogo_path or CNCT_CATALOGO_PATH
    cursos: list[dict[str, Any]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        reader = csv.DictReader(arquivo, delimiter=";")
        for indice, linha_bruta in enumerate(reader, start=1):
            linha = _normalizar_linha_csv(linha_bruta)
            denominacao = str(linha.get("Denominação do Curso") or "").strip()
            if not denominacao:
                continue
            carga_horaria_minima = linha.get("Carga Horária Mínima")
            campos_csv = {campo_csv: str(linha.get(campo_csv) or "").strip() for campo_csv, _ in CNCT_CAMPOS}
            curso = {
                "indice": indice,
                "campos_csv": campos_csv,
            }
            for campo_csv, campo_normalizado in CNCT_CAMPOS:
                curso[campo_normalizado] = campos_csv[campo_csv]
            curso.update(
                {
                    "denominacao_normalizada": normalizar_denominacao_cnct(denominacao),
                    "carga_horaria_minima_horas": extrair_numero_horas(carga_horaria_minima),
                }
            )
            cursos.append(curso)
    return cursos


def _score_denominacao(consulta_normalizada: str, denominacao_normalizada: str) -> float:
    if not consulta_normalizada or not denominacao_normalizada:
        return 0.0
    if consulta_normalizada == denominacao_normalizada:
        return 1.0
    sequence_score = SequenceMatcher(None, consulta_normalizada, denominacao_normalizada).ratio()
    tokens_consulta = set(consulta_normalizada.split())
    tokens_denominacao = set(denominacao_normalizada.split())
    if not tokens_consulta or not tokens_denominacao:
        return sequence_score
    intersecao = tokens_consulta & tokens_denominacao
    token_score = (2 * len(intersecao)) / (len(tokens_consulta) + len(tokens_denominacao))
    if consulta_normalizada in denominacao_normalizada or denominacao_normalizada in consulta_normalizada:
        token_score = max(token_score, 0.9)
    return max(sequence_score, token_score)


def _resumir_curso(curso: dict[str, Any], score: float, incluir_campos_completos: bool = False) -> dict[str, Any]:
    resumo = {
        "indice": curso["indice"],
        "score": round(score, 4),
        "denominacao": curso["denominacao"],
        "eixo_tecnologico": curso["eixo_tecnologico"],
        "area_tecnologica": curso["area_tecnologica"],
        "carga_horaria_minima": curso["carga_horaria_minima"],
        "carga_horaria_minima_horas": curso["carga_horaria_minima_horas"],
        "ocupacoes_cbo": curso["ocupacoes_cbo"],
        "infraestrutura_minima": curso["infraestrutura_minima"],
        "legislacao_profissional": curso["legislacao_profissional"],
    }
    if incluir_campos_completos:
        for _, campo_normalizado in CNCT_CAMPOS:
            resumo[campo_normalizado] = curso[campo_normalizado]
        resumo["campos_csv"] = curso["campos_csv"]
    return resumo


def buscar_cursos_cnct(
    consulta: str,
    catalogo_path: Path | None = None,
    limite: int = 5,
    incluir_campos_completos: bool = False,
) -> list[dict[str, Any]]:
    consulta_normalizada = normalizar_denominacao_cnct(consulta)
    if not consulta_normalizada:
        return []
    candidatos = []
    for curso in carregar_catalogo_cnct(catalogo_path):
        score = _score_denominacao(consulta_normalizada, curso["denominacao_normalizada"])
        if score >= 0.55:
            candidatos.append(_resumir_curso(curso, score, incluir_campos_completos=incluir_campos_completos))
    candidatos.sort(key=lambda item: (-item["score"], item["denominacao"]))
    return candidatos[:limite]


def _tipo_correspondencia(score: float) -> str:
    if score >= 1:
        return "EXATA"
    if score >= 0.86:
        return "ALTA_CONFIANCA"
    if score >= 0.72:
        return "POSSIVEL"
    return "BAIXA_CONFIANCA"


def _dados_extraidos(dados_conversao: dict[str, Any]) -> dict[str, Any]:
    dados = dados_conversao.get("dados_extraidos", {}) if isinstance(dados_conversao, dict) else {}
    return dados if isinstance(dados, dict) else {}


def _primeiro_valor_preenchido(*valores: Any) -> Any:
    for valor in valores:
        if str(valor or "").strip():
            return valor
    return None


def _carga_horaria_ppc(dados: dict[str, Any], matriz_payload: dict[str, Any]) -> dict[str, Any]:
    candidatos = [
        ("dados_extraidos.carga_horaria_total", dados.get("carga_horaria_total")),
        ("dados_extraidos.carga_horaria_total_curso", dados.get("carga_horaria_total_curso")),
        ("dados_extraidos.carga_horaria_minima", dados.get("carga_horaria_minima")),
        ("dados_extraidos.carga_horaria_minima_cnct", dados.get("carga_horaria_minima_cnct")),
    ]
    totais = matriz_payload.get("totais") if isinstance(matriz_payload, dict) else {}
    if isinstance(totais, dict):
        candidatos.extend(
            [
                ("matriz_curricular.totais.ch_total_hora_relogio", totais.get("ch_total_hora_relogio")),
                ("matriz_curricular.totais.ch_total_hora_aula", totais.get("ch_total_hora_aula")),
            ]
        )
    for fonte, valor in candidatos:
        horas = extrair_numero_horas(valor)
        if horas is not None:
            return {"valor_horas": horas, "fonte": fonte, "valor_original": valor}
    return {"valor_horas": None, "fonte": None, "valor_original": None}


def comparar_ppc_com_cnct(
    metadata: dict[str, Any],
    dados_conversao: dict[str, Any],
    matriz_payload: dict[str, Any],
    catalogo_path: Path | None = None,
) -> dict[str, Any]:
    caminho_catalogo = catalogo_path or CNCT_CATALOGO_PATH
    dados = _dados_extraidos(dados_conversao)
    curso_declarado = _primeiro_valor_preenchido(dados.get("curso_cnct"), metadata.get("curso"), dados.get("nome_curso"))
    eixo_declarado = _primeiro_valor_preenchido(dados.get("eixo_tecnologico"), metadata.get("eixo_tecnologico"))
    carga_ppc = _carga_horaria_ppc(dados, matriz_payload)

    if not caminho_catalogo.exists():
        return {
            "disponivel": False,
            "fonte_catalogo": str(caminho_catalogo),
            "motivo": "Catálogo CNCT não encontrado.",
            "curso_declarado": curso_declarado,
            "eixo_declarado": eixo_declarado,
            "carga_horaria_ppc": carga_ppc,
            "candidatos": [],
            "correspondencia": None,
            "comparacoes": {},
        }

    candidatos = buscar_cursos_cnct(str(curso_declarado or ""), caminho_catalogo)
    candidatos_completos = buscar_cursos_cnct(
        str(curso_declarado or ""),
        caminho_catalogo,
        limite=5,
        incluir_campos_completos=True,
    )
    correspondencia = candidatos[0] if candidatos and candidatos[0]["score"] >= 0.72 else None
    correspondencia_completa = candidatos_completos[0] if candidatos_completos and candidatos_completos[0]["score"] >= 0.72 else None
    comparacoes: dict[str, Any] = {}
    if correspondencia:
        tipo = _tipo_correspondencia(float(correspondencia["score"]))
        comparacoes["denominacao"] = {
            "status": "COMPATIVEL" if tipo in {"EXATA", "ALTA_CONFIANCA"} else "INCONCLUSIVO",
            "tipo_correspondencia": tipo,
            "valor_ppc": curso_declarado,
            "valor_cnct": correspondencia["denominacao"],
            "score": correspondencia["score"],
        }
        eixo_cnct = correspondencia.get("eixo_tecnologico")
        if eixo_declarado:
            comparacoes["eixo_tecnologico"] = {
                "status": "COMPATIVEL"
                if normalizar_texto_cnct(eixo_declarado) == normalizar_texto_cnct(eixo_cnct)
                else "DIVERGENTE",
                "valor_ppc": eixo_declarado,
                "valor_cnct": eixo_cnct,
            }
        carga_minima = correspondencia.get("carga_horaria_minima_horas")
        if carga_minima is not None and carga_ppc["valor_horas"] is not None:
            comparacoes["carga_horaria_minima"] = {
                "status": "COMPATIVEL" if carga_ppc["valor_horas"] >= carga_minima else "DIVERGENTE",
                "valor_ppc_horas": carga_ppc["valor_horas"],
                "valor_cnct_minimo_horas": carga_minima,
                "fonte_ppc": carga_ppc["fonte"],
            }
    elif curso_declarado:
        comparacoes["denominacao"] = {
            "status": "INCONCLUSIVO",
            "valor_ppc": curso_declarado,
            "valor_cnct": None,
            "detalhe": "Nenhuma correspondência CNCT atingiu o limiar mínimo de confiança.",
        }

    return {
        "disponivel": True,
        "fonte_catalogo": str(caminho_catalogo),
        "catalogo_sha256": sha256_file(caminho_catalogo),
        "curso_declarado": curso_declarado,
        "eixo_declarado": eixo_declarado,
        "carga_horaria_ppc": carga_ppc,
        "candidatos": candidatos,
        "correspondencia": {
            **correspondencia_completa,
            "tipo_correspondencia": _tipo_correspondencia(float(correspondencia_completa["score"])),
        }
        if correspondencia_completa
        else None,
        "comparacoes": comparacoes,
    }
