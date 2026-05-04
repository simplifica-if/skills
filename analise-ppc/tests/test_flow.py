from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gerar_relatorio_html import ErroResultadosSubagents, gerar_relatorio_html
from preparar_documento import preparar_documento
from subagents import (
    agrupar_fichas,
    carregar_fichas_ordenadas,
    ficha_requer_contexto_cnct,
    mesclar_resultados_avulsos,
    montar_grupo_avulso,
    montar_grupos_subagents,
)
from common import FICHAS_DIR, read_json, round_paths, write_json


def _markdown_base() -> str:
    return """# Curso Técnico em Informática

Curso: Curso Técnico em Informática
Campus: Assis Chateaubriand
Modalidade: Integrado

## 1. Apresentação

O curso apresenta objetivos, perfil do egresso e justificativa institucional.
"""


def _criar_rodada(tmp_path: Path) -> Path:
    arquivo_md = tmp_path / "PPC.md"
    arquivo_md.write_text(_markdown_base(), encoding="utf-8")
    payload = preparar_documento(arquivo_md, output_base=tmp_path / "output")
    return payload["rodada_dir"]


def _resultado(ficha_id: str, estado: str = "ATENDE", evidencias: int = 3) -> dict[str, object]:
    return {
        "ficha_id": ficha_id,
        "estado": estado,
        "confianca": 0.9,
        "justificativa": f"Justificativa da ficha {ficha_id}.",
        "evidencias": [f"Evidência {indice} de {ficha_id}" for indice in range(1, evidencias + 1)],
        "lacunas": [],
        "revisao_humana_obrigatoria": False,
    }


def _payload_resultados_completos() -> dict[str, object]:
    fichas = carregar_fichas_ordenadas()
    grupos = []
    for grupo in agrupar_fichas(fichas, tamanho_grupo=20):
        grupos.append(
            {
                "grupo_id": grupo["grupo_id"],
                "resultados": [_resultado(ficha["id"]) for ficha in grupo["fichas"]],
            }
        )
    return {
        "metadata": {"origem": "teste"},
        "grupos": grupos,
    }


def test_preparar_documento_cria_rodada_markdown_basica(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)

    assert caminhos["ppc"].exists()
    assert caminhos["metadata"].exists()
    assert caminhos["manifesto"].exists()
    metadata = read_json(caminhos["metadata"])
    manifesto = read_json(caminhos["manifesto"])
    assert metadata["curso"] == "Curso Técnico em Informática"
    assert manifesto["execucao"] == "subagents-na-conversa"
    assert set(caminhos) == {
        "rodada_dir",
        "suporte_dir",
        "artefatos_conversao_dir",
        "ppc",
        "ppc_bruto",
        "metadata",
        "manifesto",
        "preparacao_docx",
        "cnct_contexto",
        "contexto_estrutural_subagents",
        "grupos_avulsos_dir",
        "resultados_subagents",
        "grupos_subagents",
        "relatorio_html",
    }


def test_fichas_sao_agrupadas_em_blocos_estaveis_de_20() -> None:
    fichas = carregar_fichas_ordenadas()
    grupos = agrupar_fichas(fichas, tamanho_grupo=20)

    assert len(fichas) == 68
    assert [grupo["intervalo"] for grupo in grupos] == ["1-20", "21-40", "41-60", "61-68"]
    assert [grupo["total_fichas"] for grupo in grupos] == [20, 20, 20, 8]
    assert grupos[0]["grupo_id"] == "grupo-001"
    assert grupos[-1]["grupo_id"] == "grupo-004"


def test_montar_grupos_subagents_salva_payload_na_rodada(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)

    payload = montar_grupos_subagents(rodada_dir)

    assert caminhos["grupos_subagents"].exists()
    assert payload["ppc_markdown"] == str(caminhos["ppc"])
    assert payload["total_fichas"] == 68
    assert len(payload["grupos"]) == 4
    assert caminhos["cnct_contexto"].exists()
    assert caminhos["contexto_estrutural_subagents"].exists()
    assert payload["cnct_contexto"]["correspondencia"]["denominacao"] == "Técnico em Informática"
    assert payload["sintese_transversal_template"].endswith("sintese-transversal.md")
    grupos_com_cnct = [grupo for grupo in payload["grupos"] if grupo["requer_contexto_cnct"]]
    assert grupos_com_cnct
    assert all("contextos" in grupo and "cnct" in grupo["contextos"] for grupo in grupos_com_cnct)
    assert all("estrutura" in grupo["contextos"] for grupo in payload["grupos"])


def test_montar_grupos_subagents_anexa_representacao_grafica_quando_disponivel(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    artefatos_dir = caminhos["artefatos_conversao_dir"]
    imagem = artefatos_dir / "imagens" / "representacao_grafica.png"
    imagem.parent.mkdir(parents=True)
    imagem.write_bytes(b"imagem")
    dados = artefatos_dir / "dados.json"
    write_json(dados, {"representacao_grafica": {"extraida": True, "caminho": "imagens/representacao_grafica.png"}})
    write_json(caminhos["preparacao_docx"], {"dados": str(dados)})

    payload = montar_grupos_subagents(rodada_dir)
    grupos_com_anexo = [grupo for grupo in payload["grupos"] if grupo["requer_anexos_visuais"]]

    assert grupos_com_anexo
    assert grupos_com_anexo[0]["contextos"]["anexos_visuais"][0]["arquivo"] == str(imagem.resolve())


def test_detector_identifica_fichas_que_dependem_do_cnct() -> None:
    fichas = {ficha["id"]: ficha for ficha in carregar_fichas_ordenadas()}

    assert ficha_requer_contexto_cnct(fichas["CT-IDENT-01"])
    assert not ficha_requer_contexto_cnct(fichas["CT-SUP-01"])


def test_gerar_relatorio_html_aceita_resultados_validos(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    resultados_path = caminhos["suporte_dir"] / "resultados-subagents.json"
    write_json(resultados_path, _payload_resultados_completos())

    payload = gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))

    assert payload["relatorio_html"] == caminhos["relatorio_html"]
    assert payload["total_fichas"] == 68
    assert payload["total_alertas_transversais"] == 0
    html = caminhos["relatorio_html"].read_text(encoding="utf-8")
    assert "Análise de PPC · sub-agentes na conversa" in html
    assert "Curso Técnico em Informática" in html
    assert "CT-IDENT-01" in html
    assert 'id="filtro-busca"' in html


def test_gerar_relatorio_html_rejeita_ficha_duplicada(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    payload = _payload_resultados_completos()
    primeiro = payload["grupos"][0]["resultados"][0]
    payload["grupos"][1]["resultados"][0] = dict(primeiro)
    write_json(caminhos["suporte_dir"] / "resultados-subagents.json", payload)

    with pytest.raises(ErroResultadosSubagents, match="duplicadas"):
        gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))


def test_gerar_relatorio_html_rejeita_ficha_desconhecida(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    payload = _payload_resultados_completos()
    payload["grupos"][0]["resultados"][0]["ficha_id"] = "CT-NAO-EXISTE"
    write_json(caminhos["suporte_dir"] / "resultados-subagents.json", payload)

    with pytest.raises(ErroResultadosSubagents, match="desconhecidas"):
        gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))


def test_gerar_relatorio_html_rejeita_ficha_faltante(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    payload = _payload_resultados_completos()
    payload["grupos"][0]["resultados"].pop()
    write_json(caminhos["suporte_dir"] / "resultados-subagents.json", payload)

    with pytest.raises(ErroResultadosSubagents, match="sem resultado"):
        gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))


def test_gerar_relatorio_html_rejeita_evidencias_abaixo_do_minimo(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    payload = _payload_resultados_completos()
    payload["grupos"][0]["resultados"][0]["evidencias"] = []
    write_json(caminhos["suporte_dir"] / "resultados-subagents.json", payload)

    with pytest.raises(ErroResultadosSubagents, match="mínimo exigido"):
        gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))


def test_gerar_relatorio_html_renderiza_alertas_transversais(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    payload = _payload_resultados_completos()
    payload["alertas_transversais"] = [
        {
            "id": "ALERTA-001",
            "titulo": "Inconsistência transversal",
            "criticidade": "OBRIG",
            "descricao": "Perfil e matriz precisam de revisão conjunta.",
            "fichas_relacionadas": ["CT-IDENT-01"],
            "evidencias": ["Evidência transversal"],
            "revisao_humana_obrigatoria": True,
        }
    ]
    write_json(caminhos["suporte_dir"] / "resultados-subagents.json", payload)

    relatorio = gerar_relatorio_html(rodada_dir, Path("resultados-subagents.json"))

    assert relatorio["total_alertas_transversais"] == 1
    html = caminhos["relatorio_html"].read_text(encoding="utf-8")
    assert "Alertas transversais" in html
    assert "ALERTA-001" in html


def test_montar_grupo_avulso_e_mesclar_resultados(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    base = _payload_resultados_completos()
    write_json(caminhos["resultados_subagents"], base)

    grupo = montar_grupo_avulso(rodada_dir, ["CT-IDENT-01"])
    avulso_path = caminhos["suporte_dir"] / "resultado-avulso.json"
    write_json(
        avulso_path,
        {
            "grupo_id": grupo["grupo"]["grupo_id"],
            "resultados": [_resultado("CT-IDENT-01", estado="INCONCLUSIVO")],
        },
    )
    mesclado = mesclar_resultados_avulsos(
        rodada_dir,
        Path("resultados-subagents.json"),
        Path("resultado-avulso.json"),
    )
    payload_mesclado = read_json(caminhos["resultados_subagents"])
    resultados = [
        item
        for grupo_payload in payload_mesclado["grupos"]
        for item in grupo_payload["resultados"]
        if item["ficha_id"] == "CT-IDENT-01"
    ]

    assert Path(grupo["grupo_avulso_path"]).exists()
    assert mesclado["fichas_substituidas"] == ["CT-IDENT-01"]
    assert len(resultados) == 1
    assert resultados[0]["estado"] == "INCONCLUSIVO"


def test_nao_ha_codigo_de_execucao_por_cli_ou_tokens() -> None:
    textos = []
    for caminho in SCRIPTS_DIR.rglob("*.py"):
        textos.append(caminho.read_text(encoding="utf-8"))
    conteudo = "\n".join(textos)

    proibidos = [
        "codex exec",
        "ANALISE_PPC_CODEX",
        "ANALISE_PPC_GEMINI",
        "executar_prompt",
        "uso_tokens",
        "contabilizar-tokens",
    ]
    for proibido in proibidos:
        assert proibido not in conteudo


def test_prompt_subagent_declara_contrato_de_saida() -> None:
    prompt = (SKILL_DIR / "prompts" / "subagent-lote-fichas.md").read_text(encoding="utf-8")
    for campo in (
        "grupo_id",
        "ficha_id",
        "estado",
        "confianca",
        "justificativa",
        "evidencias",
        "lacunas",
        "revisao_humana_obrigatoria",
    ):
        assert campo in prompt


def test_prompt_sintese_transversal_declara_contrato() -> None:
    prompt = (SKILL_DIR / "prompts" / "sintese-transversal.md").read_text(encoding="utf-8")
    assert "alertas_transversais" in prompt
    assert "fichas_relacionadas" in prompt
