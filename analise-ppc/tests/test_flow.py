from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from avaliar_cruzadas import avaliar_validacoes_cruzadas
from avaliar_lote import avaliar_lote
from cnct_catalogo import CNCT_CAMPOS, buscar_cursos_cnct, comparar_ppc_com_cnct, normalizar_texto_cnct
from consolidar_resultados import consolidar_rodada
from conversao_docx import MarkdownNormalizer
from conversao_docx.identification_extractor import IdentificationExtractor
from conversao_docx.table_extractor import NormalizedTable, TableExtractor
from conversao_docx.markdown_writer import PPCConverter
from gerar_batches import gerar_batches_rodada
from gerar_relatorio_html import gerar_relatorio_html
from pre_validacoes import carregar_contexto_estrutural, gerar_pre_validacoes_rodada
from preparar_documento import preparar_documento
from providers.prompt_builder import renderizar_prompt_lote
from providers.codex_cli import executar_prompt_codex
from providers.gemini_cli import executar_prompt_gemini
from reavaliar import ErroReavaliacao, _execution_id, reavaliar_rodada
from common import (
    BASE_ANALISE_DIR,
    FICHAS_DIR,
    VALIDACOES_CRUZADAS_DIR,
    extract_identificacao_from_conversion_json,
    read_json,
    round_paths,
    write_json,
)


def _markdown_base() -> str:
    return """# Curso Técnico em Informática

Curso: Curso Técnico em Informática
Campus: Assis Chateaubriand
Modalidade: Integrado

## 1. Apresentação

O curso apresenta objetivos, perfil do egresso e justificativa institucional.

## 4. Perfil do egresso

O egresso desenvolve competências analíticas, atuação profissional e integração entre teoria e prática.

## 7. Atendimento ao estudante

O PPC prevê atendimento a estudantes com necessidades educacionais específicas e público-alvo da educação especial.

## 9. Organização do tempo escolar

O intervalo pedagógico é contabilizado na carga horária diária.
"""


def _criar_mock_codex(tmp_path: Path) -> Path:
    script = tmp_path / "mock-codex.sh"
    script.write_text(
        """#!/bin/sh
if [ -n "${MOCK_PROVIDER_ARGS_LOG:-}" ]; then
  printf '%s\n' "$@" > "${MOCK_PROVIDER_ARGS_LOG}"
fi
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-last-message|-o)
      out="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
cat >/dev/null
case "$out" in
  *execucoes-avulsas/fichas*)
    response="${MOCK_PROVIDER_RESPONSE_FICHAS:-${MOCK_PROVIDER_RESPONSE}}"
    ;;
  *execucoes-avulsas/validacoes-cruzadas*)
    response="${MOCK_PROVIDER_RESPONSE_VALIDACOES:-${MOCK_PROVIDER_RESPONSE}}"
    ;;
  *)
    response="${MOCK_PROVIDER_RESPONSE}"
    ;;
esac
printf '%s' "$response" > "$out"
if [ -n "${MOCK_PROVIDER_USAGE:-}" ]; then
  printf '{"type":"thread.started","thread_id":"test"}\n'
  printf '{"type":"turn.completed","usage":%s}\n' "${MOCK_PROVIDER_USAGE}"
fi
exit "${MOCK_PROVIDER_EXIT_CODE:-0}"
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _criar_mock_gemini(tmp_path: Path) -> Path:
    script = tmp_path / "mock-gemini.sh"
    script.write_text(
        """#!/bin/sh
cat >/dev/null
printf '%s' "${MOCK_PROVIDER_RESPONSE}"
exit "${MOCK_PROVIDER_EXIT_CODE:-0}"
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _resultado(
    ficha_id: str,
    estado: str = "ATENDE",
    confianca: float = 0.9,
    evidencias: int = 2,
    revisao_humana: bool = False,
) -> dict[str, object]:
    return {
        "ficha_id": ficha_id,
        "estado": estado,
        "confianca": confianca,
        "justificativa": f"Justificativa da ficha {ficha_id}.",
        "evidencias": [f"Evidência {indice} de {ficha_id}" for indice in range(1, evidencias + 1)],
        "lacunas": [],
        "revisao_humana_obrigatoria": revisao_humana,
    }


def _resultado_cruzada(
    validacao_id: str,
    estado: str = "ATENDE",
    confianca: float = 0.9,
    evidencias: int = 2,
    revisao_humana: bool = False,
) -> dict[str, object]:
    return {
        "validacao_id": validacao_id,
        "estado": estado,
        "confianca": confianca,
        "justificativa": f"Justificativa da validação {validacao_id}.",
        "evidencias": [f"Evidência {indice} de {validacao_id}" for indice in range(1, evidencias + 1)],
        "lacunas": [],
        "revisao_humana_obrigatoria": revisao_humana,
    }


def _copiar_subconjunto_fichas(origem_dir: Path, destino_dir: Path, quantidade: int) -> list[dict[str, object]]:
    destino_dir.mkdir(parents=True, exist_ok=True)
    fichas: list[dict[str, object]] = []
    for caminho in sorted(origem_dir.glob("*.json"))[:quantidade]:
        payload = read_json(caminho)
        write_json(destino_dir / caminho.name, payload)
        fichas.append(payload)
    return fichas


def _copiar_fichas_por_id(destino_dir: Path, ids: list[str]) -> list[dict[str, object]]:
    catalogo_dir = FICHAS_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    fichas: list[dict[str, object]] = []
    for ficha_id in ids:
        caminho = catalogo_dir / f"{ficha_id.lower()}.json"
        payload = read_json(caminho)
        write_json(destino_dir / caminho.name, payload)
        fichas.append(payload)
    return fichas


def _copiar_catalogo_canonico(destino_dir: Path) -> list[dict[str, object]]:
    catalogo_dir = FICHAS_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    fichas: list[dict[str, object]] = []
    for caminho in sorted(catalogo_dir.glob("*.json")):
        payload = read_json(caminho)
        write_json(destino_dir / caminho.name, payload)
        fichas.append(payload)
    return fichas


def _copiar_validacoes_por_id(destino_dir: Path, ids: list[str]) -> list[dict[str, object]]:
    catalogo_dir = VALIDACOES_CRUZADAS_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    validacoes: list[dict[str, object]] = []
    for validacao_id in ids:
        caminho = catalogo_dir / f"{validacao_id.lower()}.json"
        payload = read_json(caminho)
        write_json(destino_dir / caminho.name, payload)
        validacoes.append(payload)
    return validacoes


def _criar_rodada(tmp_path: Path) -> Path:
    arquivo_md = tmp_path / "PPC.md"
    arquivo_md.write_text(_markdown_base(), encoding="utf-8")
    payload = preparar_documento(arquivo_md, output_base=tmp_path / "output")
    return payload["rodada_dir"]


def _criar_catalogo_cnct_teste(tmp_path: Path) -> Path:
    catalogo = tmp_path / "catalogo_cnct.csv"
    catalogo.write_text(
        "\ufeffEixo Tecnológico;Área Tecnológica;Denominação do Curso;Perfil Profissional de Conclusão;"
        "Carga Horária Mínima;Descrição Carga Horária Mínima;Pré-Requisitos para Ingresso;"
        "Itinerários Formativos;Campo de Atuação;Ocupações CBO Associadas;Infraestrutura Mínima;"
        "Legislação Profissional\n"
        "Informação e Comunicação;Desenvolvimento de Sistemas;Técnico em Informática;"
        "Desenvolve sistemas e realiza manutenção;1200 horas;Duração mínima;Ensino fundamental;"
        "Itinerário;Empresas de tecnologia;3171-10 - Programador;Laboratório de informática;"
        "Profissão não regulamentada.\n"
        "Ambiente e Saúde;Gestão e Promoção da Saúde;Técnico em Enfermagem;"
        "Atua em serviços de saúde;1200 horas;Duração mínima;Ensino fundamental;"
        "Itinerário;Hospitais;3222-05 - Técnico de enfermagem;Laboratório multidisciplinar;"
        "Lei profissional.\n",
        encoding="utf-8",
    )
    return catalogo


def test_preparar_documento_markdown_cria_rodada(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    assert caminhos["ppc"].exists()
    assert caminhos["metadata"].exists()
    assert caminhos["pre_validacoes"].exists()
    assert caminhos["condicionais_rodada"].exists()
    assert caminhos["contexto_estrutural"].exists()
    metadata = read_json(caminhos["metadata"])
    pre_validacoes = read_json(caminhos["pre_validacoes"])
    condicionais = read_json(caminhos["condicionais_rodada"])
    contexto_estrutural = read_json(caminhos["contexto_estrutural"])
    assert metadata["curso"] == "Curso Técnico em Informática"
    assert metadata["campus"] == "Assis Chateaubriand"
    assert metadata["modalidade"] == "Integrado"
    assert pre_validacoes["tem_bloqueios"] is False
    assert condicionais["condicionais"]["modalidade_integrado"]["valor"] is True
    assert condicionais["condicionais"]["tem_nee"]["valor"] is True
    assert condicionais["condicionais"]["intervalo_pedagogico_contabilizado"]["valor"] is True
    assert contexto_estrutural["matriz_curricular"]["disponivel"] is False
    assert caminhos["cnct_comparacao"].exists()
    assert contexto_estrutural["cnct"]["comparacao_catalogo"]["correspondencia"]["denominacao"] == "Técnico em Informática"
    assert "Infraestrutura Mínima" in contexto_estrutural["cnct"]["comparacao_catalogo"]["correspondencia"]["campos_csv"]
    assert contexto_estrutural["cnct"]["comparacao_catalogo"]["correspondencia"]["infraestrutura_minima"]


def test_buscar_cursos_cnct_normaliza_denominacao_do_ppc(tmp_path: Path) -> None:
    catalogo = _criar_catalogo_cnct_teste(tmp_path)

    candidatos = buscar_cursos_cnct("Curso Técnico em Informática", catalogo)

    assert candidatos[0]["denominacao"] == "Técnico em Informática"
    assert candidatos[0]["score"] == 1


def test_comparar_ppc_com_cnct_registra_divergencia_de_carga_horaria(tmp_path: Path) -> None:
    catalogo = _criar_catalogo_cnct_teste(tmp_path)

    comparacao = comparar_ppc_com_cnct(
        metadata={"curso": "Curso Técnico em Informática"},
        dados_conversao={"dados_extraidos": {"eixo_tecnologico": "Informação e Comunicação"}},
        matriz_payload={"totais": {"ch_total_hora_relogio": 1000}},
        catalogo_path=catalogo,
    )

    assert comparacao["correspondencia"]["denominacao"] == "Técnico em Informática"
    assert comparacao["correspondencia"]["perfil_profissional"] == "Desenvolve sistemas e realiza manutenção"
    assert comparacao["correspondencia"]["pre_requisitos_ingresso"] == "Ensino fundamental"
    assert comparacao["correspondencia"]["itinerarios_formativos"] == "Itinerário"
    assert comparacao["correspondencia"]["campo_atuacao"] == "Empresas de tecnologia"
    assert comparacao["correspondencia"]["infraestrutura_minima"] == "Laboratório de informática"
    assert comparacao["correspondencia"]["campos_csv"]["Infraestrutura Mínima"] == "Laboratório de informática"
    assert comparacao["comparacoes"]["denominacao"]["status"] == "COMPATIVEL"
    assert comparacao["comparacoes"]["eixo_tecnologico"]["status"] == "COMPATIVEL"
    assert comparacao["comparacoes"]["carga_horaria_minima"]["status"] == "DIVERGENTE"
    assert comparacao["comparacoes"]["carga_horaria_minima"]["valor_cnct_minimo_horas"] == 1200


def test_preparar_documento_docx_usa_conversao_interna(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    documento = docx.Document()
    documento.add_heading("Curso Técnico em Informática", level=1)
    documento.add_paragraph("Curso: Curso Técnico em Informática")
    documento.add_paragraph("Campus: Assis Chateaubriand")
    documento.add_paragraph("Modalidade: Integrado")
    arquivo_docx = tmp_path / "PPC.docx"
    documento.save(arquivo_docx)

    payload = preparar_documento(arquivo_docx, output_base=tmp_path / "output")
    caminhos = round_paths(payload["rodada_dir"])
    assert caminhos["ppc"].exists()
    assert caminhos["ppc_bruto"].exists()
    assert caminhos["preparacao_docx"].exists()
    assert (payload["rodada_dir"] / "artefatos-conversao").is_dir()
    assert (payload["rodada_dir"] / "artefatos-conversao" / "PPC_dados.json").exists()
    assert caminhos["pre_validacoes"].exists()
    assert caminhos["condicionais_rodada"].exists()
    assert caminhos["contexto_estrutural"].exists()
    metadata = read_json(caminhos["metadata"])
    assert "artefatos_conversao_docx" in metadata


def test_identificacao_docx_separa_forma_de_oferta_e_modalidade_de_ensino() -> None:
    identificacao = extract_identificacao_from_conversion_json(
        {
            "dados_extraidos": {
                "nome_curso": "Curso Técnico em Informática",
                "campus": "Assis Chateaubriand",
                "forma_oferta": "Integrado",
                "modalidade_ensino": "Presencial",
            }
        }
    )

    assert identificacao["modalidade"] == "Integrado"
    assert identificacao["forma_oferta"] == "Integrado"
    assert identificacao["modalidade_ensino"] == "Presencial"


def test_identificacao_docx_prefere_denominacao_normalizada_ao_nome_curso_ruidoso() -> None:
    identificacao = extract_identificacao_from_conversion_json(
        {
            "dados_extraidos": {
                "nome_curso": "(CEC) ou Comissão de Ajuste Curricular (CAJ):\t7",
                "denominacao_curso_tecnico_em_informatica": "Denominação: Curso Técnico em Informática",
                "campus": "Assis Chateaubriand",
                "forma_de_oferta_integrado": "Forma de oferta: Integrado",
                "modalidade_presencial": "Modalidade: Presencial",
                "eixo_tecnologico_informacao_e_comunicacao": "Eixo Tecnológico: Informação e Comunicação",
            }
        }
    )

    assert identificacao["curso"] == "Curso Técnico em Informática"
    assert identificacao["campus"] == "Assis Chateaubriand"
    assert identificacao["modalidade"] == "Integrado"
    assert identificacao["forma_oferta"] == "Integrado"
    assert identificacao["modalidade_ensino"] == "Presencial"
    assert identificacao["eixo_tecnologico"] == "Informação e Comunicação"


def test_extrator_identificacao_salva_campos_canonicos_em_tabela_duplicada() -> None:
    tabela = NormalizedTable(
        headers=[],
        rows=[
            ["Denominação: Curso Técnico em Informática", "Denominação: Curso Técnico em Informática"],
            ["Forma de oferta: Integrado", "Forma de oferta: Integrado"],
            ["Modalidade: Presencial", "Modalidade: Presencial"],
            ["Eixo Tecnológico: Informação e Comunicação", "Eixo Tecnológico: Informação e Comunicação"],
        ],
        original_row_count=4,
        original_col_count=2,
    )

    dados = IdentificationExtractor().extract_identification_data(tabela)

    assert dados["nome_curso"] == "Curso Técnico em Informática"
    assert dados["forma_oferta"] == "Integrado"
    assert dados["modalidade_ensino"] == "Presencial"
    assert dados["eixo_tecnologico"] == "Informação e Comunicação"


def test_pre_validacoes_nao_aceitam_placeholder_de_identificacao(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    metadata["modalidade"] = "Modalidade não identificada"
    metadata.pop("forma_oferta", None)
    write_json(caminhos["metadata"], metadata)

    payload = gerar_pre_validacoes_rodada(rodada_dir)
    item = next(item for item in payload["pre_validacoes"]["obrigatorias"] if item["id"] == "PV-002")

    assert item["status"] == "NAO_CONFORME"
    assert payload["pre_validacoes"]["tem_bloqueios"] is True


def test_contexto_estrutural_expoe_representacao_grafica_extraida(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    dados_path = tmp_path / "dados.json"
    write_json(
        dados_path,
        {
            "dados_extraidos": {},
            "representacao_grafica": {
                "encontrada": True,
                "extraida": True,
                "caminho": "imagens/representacao_grafica.png",
                "metodo": "bitmap",
            },
        },
    )
    metadata = read_json(caminhos["metadata"])
    metadata["artefatos_conversao_docx"] = {"dados": str(dados_path)}
    write_json(caminhos["metadata"], metadata)

    payload = gerar_pre_validacoes_rodada(rodada_dir)

    assert payload["contexto_estrutural"]["representacao_grafica"]["extraida"] is True
    assert payload["contexto_estrutural"]["representacao_grafica"]["caminho"] == "imagens/representacao_grafica.png"


def test_preparar_documento_docx_nao_referencia_imagem_nao_extraida(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docx = pytest.importorskip("docx")

    def falhar_extracao_imagem(self: PPCConverter, output_dir: Path) -> dict[str, Path]:
        self._graphic_section["extraction_method"] = "falha_dependencias"
        return {}

    monkeypatch.setattr(PPCConverter, "_save_graphic_image", falhar_extracao_imagem)

    documento = docx.Document()
    documento.add_heading("Curso Técnico em Informática", level=1)
    documento.add_paragraph("Curso: Curso Técnico em Informática")
    documento.add_paragraph("Campus: Assis Chateaubriand")
    documento.add_paragraph("Modalidade: Integrado")
    documento.add_heading("5.12 Representação gráfica do processo formativo", level=2)
    documento.add_paragraph("Fluxo descrito em forma textual, sem imagem embutida.")
    arquivo_docx = tmp_path / "PPC.docx"
    documento.save(arquivo_docx)

    payload = preparar_documento(arquivo_docx, output_base=tmp_path / "output")
    caminhos = round_paths(payload["rodada_dir"])
    dados = read_json(payload["rodada_dir"] / "artefatos-conversao" / "PPC_dados.json")

    assert "imagens/representacao_grafica.png" not in caminhos["ppc"].read_text(encoding="utf-8")
    assert "imagens/representacao_grafica.png" not in caminhos["ppc_bruto"].read_text(encoding="utf-8")
    assert dados["representacao_grafica"]["extraida"] is False
    assert dados["representacao_grafica"]["caminho"] is None


def test_normalizador_markdown_remove_ruido_e_preserva_estrutura_basica() -> None:
    markdown_bruto = "\n".join(
        [
            "12/03/2026 09:10",
            "https://sei.ifpr.edu.br/sei/controlador.php?acao=documento",
            "#",
            "1 APRESENTAÇÃO DO PROJETO",
            "",
            "Este é um parágrafo",
            "quebrado em duas linhas.",
            "",
            "PÁGINA 2 DE 10",
            "Primeiro parágrafo completo.",
            "Segundo parágrafo distinto.",
            "2.1 OBJETIVOS ESPECÍFICOS",
            "- item preservado",
            "| Coluna | Valor |",
            "| --- | --- |",
            "| Campus | Curitiba |",
            "https://ifpr.edu.br/referencia-oficial",
        ]
    )

    resultado = MarkdownNormalizer().normalize(markdown_bruto)

    assert "12/03/2026 09:10" not in resultado.markdown_normalizado
    assert "https://sei.ifpr.edu.br" not in resultado.markdown_normalizado
    assert "# 1 APRESENTAÇÃO DO PROJETO" in resultado.markdown_normalizado
    assert "Este é um parágrafo quebrado em duas linhas." in resultado.markdown_normalizado
    assert "Primeiro parágrafo completo.\nSegundo parágrafo distinto." in resultado.markdown_normalizado
    assert "## 2.1 OBJETIVOS ESPECÍFICOS" in resultado.markdown_normalizado
    assert "- item preservado" in resultado.markdown_normalizado
    assert "| Campus | Curitiba |" in resultado.markdown_normalizado
    assert "https://ifpr.edu.br/referencia-oficial" in resultado.markdown_normalizado


def test_normalizador_markdown_padroniza_tabela_pipe_sem_reconstruir_conteudo() -> None:
    markdown_bruto = "\n".join(
        [
            "Texto antes",
            "| Campo  | Valor | Observações |",
            "| :-- | --: | :---: |",
            "| Campus | Curitiba | Laboratório de Redes |",
            r"| Área | Infraestrutura | Software \| Licenças |",
            "Texto depois",
        ]
    )

    resultado = MarkdownNormalizer().normalize(markdown_bruto)

    assert "Texto antes\n\n| Campo | Valor | Observações |" in resultado.markdown_normalizado
    assert "|:---|---:|:---:|" in resultado.markdown_normalizado
    assert "| Campus | Curitiba | Laboratório de Redes |" in resultado.markdown_normalizado
    assert r"| Área | Infraestrutura | Software \| Licenças |" in resultado.markdown_normalizado
    assert "| Campo  | Valor | Observações |" not in resultado.markdown_normalizado
    assert "|\nTexto depois" not in resultado.markdown_normalizado


def test_extrator_tabela_gera_markdown_compacto_sem_padding_visual() -> None:
    tabela = NormalizedTable(
        headers=["Campo", "Valor"],
        rows=[
            ["Componente curricular", "Química II"],
            [
                "Ementa",
                "Texto longo que não deve alargar todas as demais linhas da tabela no Markdown bruto.",
            ],
        ],
        original_row_count=3,
        original_col_count=2,
    )

    markdown = TableExtractor().to_markdown(tabela)

    assert markdown.splitlines() == [
        "| Campo | Valor |",
        "|---|---|",
        "| Componente curricular | Química II |",
        "| Ementa | Texto longo que não deve alargar todas as demais linhas da tabela no Markdown bruto. |",
    ]
    assert "Componente curricular                                                    " not in markdown


def test_prompt_remove_campos_volateis_para_estabilizar_cache() -> None:
    prompt_a = renderizar_prompt_lote(
        {"curso": "Curso Técnico em Informática", "criado_em": "fixo"},
        "PPC",
        {"batch_id": "batch-001", "fichas": []},
        pre_validacoes={"gerado_em": "2026-04-22T08:00:00-03:00", "bloqueios": []},
        condicionais_rodada={"gerado_em": "2026-04-22T08:00:00-03:00", "condicionais": {}},
        contexto_estrutural={"gerado_em": "2026-04-22T08:00:00-03:00", "x": [{"executado_em": "a"}]},
    )
    prompt_b = renderizar_prompt_lote(
        {"curso": "Curso Técnico em Informática", "criado_em": "fixo"},
        "PPC",
        {"batch_id": "batch-001", "fichas": []},
        pre_validacoes={"gerado_em": "2026-04-22T09:00:00-03:00", "bloqueios": []},
        condicionais_rodada={"gerado_em": "2026-04-22T09:00:00-03:00", "condicionais": {}},
        contexto_estrutural={"gerado_em": "2026-04-22T09:00:00-03:00", "x": [{"executado_em": "b"}]},
    )

    assert prompt_a == prompt_b


def test_codex_provider_usa_workdir_absoluto_com_rodada_relativa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", "{\"ok\": true}")
    monkeypatch.chdir(tmp_path)
    workdir = Path("rodada")
    workdir.mkdir()
    prompt_path = workdir / "prompt.md"
    raw_output_path = workdir / "resposta.md"
    prompt_path.write_text("Responda JSON.", encoding="utf-8")

    payload = executar_prompt_codex(
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        model="codex-default",
        workdir=workdir,
    )

    assert payload["exit_code"] == 0
    assert payload["command"][payload["command"].index("-C") + 1] == str(workdir.resolve())


def test_codex_provider_extrai_uso_tokens_do_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", "OK")
    monkeypatch.setenv(
        "MOCK_PROVIDER_USAGE",
        json.dumps({"input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 6}),
    )
    workdir = tmp_path / "rodada"
    workdir.mkdir()
    prompt_path = workdir / "prompt.md"
    raw_output_path = workdir / "resposta.md"
    prompt_path.write_text("Responda JSON.", encoding="utf-8")

    payload = executar_prompt_codex(
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        model="codex-default",
        workdir=workdir,
    )

    assert "--json" in payload["command"]
    assert raw_output_path.read_text(encoding="utf-8") == "OK"
    assert payload["uso_tokens"]["cli"] == "codex"
    assert payload["uso_tokens"]["provider"] == "codex"
    assert payload["uso_tokens"]["input_tokens"] == 12
    assert payload["uso_tokens"]["cached_input_tokens"] == 4
    assert payload["uso_tokens"]["output_tokens"] == 6
    assert payload["uso_tokens"]["total_tokens"] == 18


def test_gemini_provider_extrai_resposta_e_uso_tokens_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_gemini = _criar_mock_gemini(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_GEMINI_BIN", str(mock_gemini))
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps(
            {
                "response": "OK",
                "stats": {
                    "models": {
                        "gemini-2.5-flash-lite": {
                            "tokens": {
                                "input": 10,
                                "prompt": 10,
                                "candidates": 3,
                                "thoughts": 2,
                                "tool": 1,
                                "total": 16,
                                "cached": 4,
                            }
                        },
                        "gemini-3-flash-preview": {
                            "tokens": {
                                "input": 20,
                                "prompt": 20,
                                "candidates": 5,
                                "thoughts": 0,
                                "tool": 0,
                                "total": 25,
                                "cached": 8,
                            }
                        },
                    }
                },
            }
        ),
    )
    workdir = tmp_path / "rodada"
    workdir.mkdir()
    prompt_path = workdir / "prompt.md"
    raw_output_path = workdir / "resposta.md"
    prompt_path.write_text("Responda JSON.", encoding="utf-8")

    payload = executar_prompt_gemini(
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        model="gemini-default",
        workdir=workdir,
    )

    assert payload["command"][payload["command"].index("--output-format") + 1] == "json"
    assert raw_output_path.read_text(encoding="utf-8") == "OK"
    assert payload["uso_tokens"]["cli"] == "gemini"
    assert payload["uso_tokens"]["provider"] == "gemini"
    assert payload["uso_tokens"]["input_tokens"] == 30
    assert payload["uso_tokens"]["cached_input_tokens"] == 12
    assert payload["uso_tokens"]["output_tokens"] == 11
    assert payload["uso_tokens"]["total_tokens"] == 41
    assert set(payload["uso_tokens"]["modelos"]) == {"gemini-2.5-flash-lite", "gemini-3-flash-preview"}


def test_scripts_nao_dependem_de_outras_skills() -> None:
    scripts_dir = SKILL_DIR / "scripts"
    conteudo = "\n".join(path.read_text(encoding="utf-8") for path in scripts_dir.rglob("*.py"))

    skill_removida = "analise" + "-ppc" + "-skill"
    for proibido in (".agents/skills", skill_removida):
        assert proibido not in conteudo


def test_gerar_batches_estaveis_com_catalogo_canonico(tmp_path: Path) -> None:
    fichas_dir = tmp_path / "fichas"
    fichas = _copiar_catalogo_canonico(fichas_dir)
    assert len(fichas) == 68
    assert {
        "CT-SUP-12",
        "CT-SUP-13",
        "CT-SUP-14",
        "CT-SUP-15",
        "CT-SUP-16",
        "CT-SUP-17",
        "CT-SUP-18",
        "CT-SUP-19",
        "CT-SUP-20",
        "CT-SUP-21",
        "CT-SUP-22",
        "CT-SUP-23",
        "CT-CURR-12",
        "CT-CURR-13",
        "CT-CURR-14",
        "CT-CURR-15",
        "CT-CURR-16",
        "CT-CURR-17",
        "CT-CURR-18",
        "CT-CURR-19",
        "CT-CURR-20",
        "CT-CURR-21",
        "CT-CURR-22",
        "CT-IDENT-10",
        "CT-IDENT-11",
        "CT-IDENT-12",
        "CT-IDENT-13",
        "CT-IDENT-14",
        "CT-IDENT-15",
        "CT-IDENT-16",
        "CT-IDENT-17",
    }.issubset(
        {ficha["id"] for ficha in fichas}
    )

    rodada_dir = _criar_rodada(tmp_path)
    payload = gerar_batches_rodada(rodada_dir, batch_size=20, fichas_dir=fichas_dir)
    total_esperado = (len(fichas) + 19) // 20
    assert payload["total_batches"] == total_esperado
    primeiro = read_json(round_paths(rodada_dir)["batches_dir"] / "batch-001.json")
    assert primeiro["total_fichas"] == 20
    ultimo = read_json(round_paths(rodada_dir)["batches_dir"] / f"batch-{total_esperado:03d}.json")
    assert ultimo["total_fichas"] == len(fichas) - (20 * (total_esperado - 1))


def test_fichas_cobrem_todos_os_campos_do_cnct() -> None:
    catalogo_dir = FICHAS_DIR
    textos = []
    for caminho in sorted(catalogo_dir.glob("*.json")):
        ficha = read_json(caminho)
        partes = [
            str(ficha.get("titulo", "")),
            str(ficha.get("pergunta", "")),
            str(ficha.get("rubrica", "")),
            str(ficha.get("boa_evidencia", "")),
            str(ficha.get("ma_evidencia", "")),
            str(ficha.get("escalonar_quando", "")),
            " ".join(str(item) for item in ficha.get("consultas", [])),
        ]
        textos.append(normalizar_texto_cnct(" ".join(partes)))
    texto_catalogo = "\n".join(textos)

    for campo_csv, campo_normalizado in CNCT_CAMPOS:
        assert normalizar_texto_cnct(campo_csv) in texto_catalogo or normalizar_texto_cnct(campo_normalizado) in texto_catalogo


def test_indice_base_analise_reflete_catalogos() -> None:
    indice = read_json(BASE_ANALISE_DIR / "indice.json")
    fichas = sorted(read_json(caminho)["id"] for caminho in FICHAS_DIR.glob("*.json"))
    validacoes = sorted(read_json(caminho)["id"] for caminho in VALIDACOES_CRUZADAS_DIR.glob("*.json"))
    contratos_dir = BASE_ANALISE_DIR / "contratos"
    contratos = sorted(caminho.stem for caminho in contratos_dir.glob("*.json"))

    assert indice["resumo"] == {
        "total_fichas": len(fichas),
        "total_validacoes_cruzadas": len(validacoes),
        "total_contratos": len(contratos),
        "total_itens": len(fichas) + len(validacoes) + len(contratos),
    }
    assert sorted(item["id"] for item in indice["itens"] if item["categoria"] == "ficha") == fichas
    assert sorted(item["id"] for item in indice["itens"] if item["categoria"] == "validacao_cruzada") == validacoes
    assert sorted(item["id"] for item in indice["itens"] if item["categoria"] == "contrato") == contratos


@pytest.mark.parametrize(
    ("resposta_bruta", "status_esperado"),
    [
        ("texto sem json", "erro_json"),
        ("{}", "erro_validacao"),
        (json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-CURR-01")]}), "erro_incompleto"),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [_resultado("CT-CURR-01"), _resultado("CT-CURR-01")],
                }
            ),
            "erro_incompleto",
        ),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [_resultado("CT-CURR-01"), _resultado("FICHA-ESTRANHA")],
                }
            ),
            "erro_incompleto",
        ),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [
                        _resultado("CT-CURR-01", estado="ATENDE"),
                        _resultado("CT-CURR-02", estado="INVALIDO"),
                    ],
                }
            ),
            "erro_validacao",
        ),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [
                        _resultado("CT-CURR-01", confianca=0.8),
                        _resultado("CT-CURR-02", confianca=1.5),
                    ],
                }
            ),
            "erro_validacao",
        ),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [
                        _resultado("CT-CURR-01", evidencias=2),
                        _resultado("CT-CURR-02", evidencias=1),
                    ],
                }
            ),
            "erro_validacao",
        ),
        (
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [
                        _resultado("CT-CURR-01", evidencias=2),
                        {
                            **_resultado("CT-CURR-02", evidencias=2),
                            "evidencias": ["   ", ""],
                        },
                    ],
                }
            ),
            "erro_validacao",
        ),
        (
            "Antes do JSON\n```json\n"
            + json.dumps(
                {
                    "batch_id": "batch-001",
                    "resultados": [_resultado("CT-CURR-01"), _resultado("CT-CURR-02")],
                }
            )
            + "\n```\nDepois do JSON",
            "ok",
        ),
    ],
)
def test_avaliar_lote_trata_respostas_invalidas_e_cercadas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resposta_bruta: str,
    status_esperado: str,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", resposta_bruta)
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    subconjunto = _copiar_subconjunto_fichas(fichas_dir, tmp_path / "fichas-lote", 2)
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(subconjunto),
        "fichas": subconjunto,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)

    payload = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert payload["status"] == status_esperado


def test_avaliar_lote_anexa_representacao_grafica_para_ct_curr_10(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    args_log = tmp_path / "codex-args.log"
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_ARGS_LOG", str(args_log))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    caminhos = round_paths(rodada_dir)
    artefatos_dir = rodada_dir / "artefatos-conversao"
    imagens_dir = artefatos_dir / "imagens"
    imagens_dir.mkdir(parents=True, exist_ok=True)
    imagem = imagens_dir / "representacao_grafica.png"
    imagem.write_bytes(b"imagem-teste")
    dados = artefatos_dir / "dados.json"
    write_json(dados, {})
    write_json(
        caminhos["contexto_estrutural"],
        {
            "artefatos": {"dados": str(dados)},
            "representacao_grafica": {
                "encontrada": True,
                "extraida": True,
                "metodo": "bitmap",
                "caminho": "imagens/representacao_grafica.png",
            },
        },
    )

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-CURR-10"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": 1,
        "fichas": fichas,
    }
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-CURR-10")]}),
    )

    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )

    assert status["status"] == "ok"
    assert status["anexos_visuais"][0]["ficha_id"] == "CT-CURR-10"
    assert status["anexos_visuais_sha256"] == [hashlib.sha256(imagem.read_bytes()).hexdigest()]
    args = args_log.read_text(encoding="utf-8").splitlines()
    assert "--image" in args
    assert str(imagem.resolve()) in args
    prompt = (caminhos["resultados_dir"] / "batch-001.prompt.md").read_text(encoding="utf-8")
    assert "Anexos visuais disponíveis para este lote" in prompt
    assert str(imagem.resolve()) in prompt


def test_consolidar_e_gerar_relatorio_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    subconjunto = _copiar_subconjunto_fichas(fichas_dir, tmp_path / "fichas-lote", 2)
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(subconjunto),
        "fichas": subconjunto,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)

    resposta_ok = {
        "batch_id": "batch-001",
        "resultados": [
            _resultado(subconjunto[0]["id"], estado="ATENDE", revisao_humana=False),
            _resultado(subconjunto[1]["id"], estado="INCONCLUSIVO", revisao_humana=True),
        ],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))
    monkeypatch.setenv(
        "MOCK_PROVIDER_USAGE",
        json.dumps({"input_tokens": 100, "cached_input_tokens": 25, "output_tokens": 40}),
    )

    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert status["status"] == "ok"
    assert status["uso_tokens"]["total_tokens"] == 140
    uso_tokens = read_json(caminhos["uso_tokens"])
    assert uso_tokens["total_execucoes_com_uso"] == 1
    assert uso_tokens["clis"] == ["codex"]
    assert uso_tokens["modelos"] == ["codex-default"]
    assert uso_tokens["modelos_por_cli"] == {"codex": ["codex-default"]}
    assert uso_tokens["totais"]["input_tokens"] == 100
    assert uso_tokens["totais"]["cached_input_tokens"] == 25
    assert uso_tokens["totais"]["output_tokens"] == 40
    assert uso_tokens["totais"]["total_tokens"] == 140

    consolidado = consolidar_rodada(rodada_dir, modo_situacao="padrao")
    assert consolidado["parecer"]["situacao"] in {"APROVADO", "COM_RESSALVAS", "DILIGENCIA", "NAO_APROVADO"}
    assert consolidado["resultados_fichas"].exists()
    assert consolidado["achados"].exists()
    assert consolidado["parecer_final"].exists()

    relatorio = gerar_relatorio_html(rodada_dir)
    html = relatorio["relatorio_html"].read_text(encoding="utf-8")
    assert 'id="filtro-busca"' in html
    assert 'data-quick-filter="bloq-nao-atende"' in html
    assert "Pré-validações estruturais" in html
    assert "Condicionais da rodada" in html
    assert "Validações cruzadas" in html
    assert "Uso de tokens" in html
    assert "Modelos usados" in html
    assert '"total_execucoes_com_uso": 1' in html
    assert '"clis": ["codex"]' in html
    assert '"modelos_por_cli": {"codex": ["codex-default"]}' in html
    assert '"total_tokens": 140' in html
    assert "Revisão transversal não executada" in html
    assert "Curso Técnico em Informática" in html


def test_avaliar_cruzadas_gera_validacoes_por_agente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    validacoes_dir = tmp_path / "validacoes-cruzadas"
    validacoes = _copiar_validacoes_por_id(validacoes_dir, ["VC-01-05", "VC-04-05"])
    resposta_ok = {
        "escopo": "validacoes_cruzadas",
        "validacoes": [_resultado_cruzada(validacao["id"]) for validacao in validacoes],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))

    status = avaliar_validacoes_cruzadas(
        rodada_dir=rodada_dir,
        provider="codex",
        model="codex-default",
        forcar=True,
        validacoes_dir=validacoes_dir,
    )

    caminhos = round_paths(rodada_dir)
    payload = read_json(caminhos["validacoes_cruzadas"])
    assert status["status"] == "ok"
    assert caminhos["validacoes_cruzadas_prompt"].exists()
    assert caminhos["validacoes_cruzadas_resposta_bruta"].exists()
    assert payload["total_validacoes"] == 2
    assert {item["id"] for item in payload["validacoes"]} == {"VC-01-05", "VC-04-05"}


@pytest.mark.parametrize(
    ("resposta_bruta", "status_esperado"),
    [
        ("texto sem json", "erro_json"),
        ("{}", "erro_validacao"),
        (json.dumps({"validacoes": [_resultado_cruzada("VC-01-05")]}), "erro_incompleto"),
        (
            json.dumps({"validacoes": [_resultado_cruzada("VC-01-05"), _resultado_cruzada("VC-01-05")]}),
            "erro_incompleto",
        ),
        (
            json.dumps({"validacoes": [_resultado_cruzada("VC-01-05"), _resultado_cruzada("VC-XX-99")]}),
            "erro_incompleto",
        ),
        (
            json.dumps(
                {
                    "validacoes": [
                        _resultado_cruzada("VC-01-05"),
                        _resultado_cruzada("VC-04-05", estado="INVALIDO"),
                    ]
                }
            ),
            "erro_validacao",
        ),
    ],
)
def test_avaliar_cruzadas_trata_respostas_invalidas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resposta_bruta: str,
    status_esperado: str,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", resposta_bruta)
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    validacoes_dir = tmp_path / "validacoes-cruzadas"
    _copiar_validacoes_por_id(validacoes_dir, ["VC-01-05", "VC-04-05"])

    status = avaliar_validacoes_cruzadas(
        rodada_dir=rodada_dir,
        provider="codex",
        model="codex-default",
        forcar=True,
        validacoes_dir=validacoes_dir,
    )
    assert status["status"] == status_esperado


def test_ct_trans_05_e_recalibrado_a_partir_de_sinais_auditaveis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-SUP-12", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)

    resposta_ok = {
        "batch_id": "batch-001",
        "resultados": [
            _resultado("CT-SUP-12", estado="NAO_ATENDE"),
            _resultado("CT-TRANS-05", estado="ATENDE", evidencias=3),
        ],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))

    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert status["status"] == "ok"

    consolidado = consolidar_rodada(rodada_dir, modo_situacao="padrao")
    resultados = read_json(consolidado["resultados_fichas"])
    ct_trans_05 = next(item for item in resultados["itens"] if item["ficha_id"] == "CT-TRANS-05")

    assert ct_trans_05["batch_id"] == "derivado"
    assert ct_trans_05["estado"] == "NAO_ATENDE"
    assert "Síntese derivada de sinais auditáveis" in ct_trans_05["justificativa"]
    assert len(ct_trans_05["evidencias"]) >= 3


def test_validacoes_cruzadas_influenciam_ct_trans_05_e_relatorio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-SUP-12", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)

    resposta_ok = {
        "batch_id": "batch-001",
        "resultados": [
            _resultado("CT-SUP-12", estado="ATENDE"),
            _resultado("CT-TRANS-05", estado="ATENDE", evidencias=3),
        ],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))
    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert status["status"] == "ok"

    validacoes_dir = tmp_path / "validacoes-cruzadas-subset"
    catalogo_cruzadas = _copiar_validacoes_por_id(validacoes_dir, ["VC-01-05"])
    resposta_cruzadas = {
        "escopo": "validacoes_cruzadas",
        "validacoes": [
            _resultado_cruzada(
                validacao["id"],
                estado="NAO_ATENDE" if validacao["id"] == "VC-01-05" else "ATENDE",
                revisao_humana=validacao["id"] == "VC-01-05",
            )
            for validacao in catalogo_cruzadas
        ],
    }
    pre_validacoes_antes = caminhos["pre_validacoes"].read_text(encoding="utf-8")
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_cruzadas))
    status_cruzadas = avaliar_validacoes_cruzadas(
        rodada_dir=rodada_dir,
        provider="codex",
        model="codex-default",
        forcar=True,
        validacoes_dir=validacoes_dir,
    )
    assert status_cruzadas["status"] == "ok"
    assert caminhos["pre_validacoes"].read_text(encoding="utf-8") == pre_validacoes_antes
    assert read_json(caminhos["validacoes_cruzadas_catalogo"])["total_validacoes"] == 1

    consolidado = consolidar_rodada(rodada_dir, modo_situacao="padrao")
    resultados = read_json(consolidado["resultados_fichas"])
    ct_trans_05 = next(item for item in resultados["itens"] if item["ficha_id"] == "CT-TRANS-05")
    assert ct_trans_05["estado"] == "NAO_ATENDE"
    assert "VC-01-05" in ct_trans_05["derivado_de"]["validacoes_cruzadas"]

    relatorio = gerar_relatorio_html(rodada_dir)
    html = relatorio["relatorio_html"].read_text(encoding="utf-8")
    assert "VC-01-05" in html
    assert "CH total apresentação" in html


def test_reavaliar_fichas_por_id_salva_sobreposicoes_e_regenera_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-CURR-06", "CT-TRANS-03", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)

    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps(
            {
                "batch_id": "batch-001",
                "resultados": [
                    _resultado("CT-CURR-06"),
                    _resultado("CT-TRANS-03", evidencias=3),
                    _resultado("CT-TRANS-05", evidencias=3),
                ],
            }
        ),
    )
    assert avaliar_lote(rodada_dir, "batch-001", "codex", "codex-default", forcar=True)["status"] == "ok"

    payload_ids = ["CT-CURR-06", "CT-TRANS-03"]
    batch_id_avulso = _execution_id("fichas", payload_ids, _copiar_fichas_por_id(tmp_path / "ids-reavaliacao", payload_ids))
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_FICHAS",
        json.dumps(
            {
                "batch_id": batch_id_avulso,
                "resultados": [
                    _resultado("CT-CURR-06", estado="NAO_ATENDE", revisao_humana=True),
                    _resultado("CT-TRANS-03", estado="ATENDE", evidencias=3),
                ],
            }
        ),
    )

    payload = reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=payload_ids,
        validacao_ids=[],
        provider="codex",
        model="codex-default",
        forcar=True,
        gerar_relatorio=True,
    )

    assert all(item["status"] == "ok" for item in payload["status"])
    assert payload["relatorio_html"]
    sobreposicoes = read_json(caminhos["sobreposicoes_fichas"])
    assert set(sobreposicoes["itens"]) == {"CT-CURR-06", "CT-TRANS-03"}
    resultados = read_json(caminhos["resultados_fichas"])
    por_id = {item["ficha_id"]: item for item in resultados["itens"]}
    assert por_id["CT-CURR-06"]["estado"] == "NAO_ATENDE"
    assert por_id["CT-CURR-06"]["batch_id"] == "avulso"
    prompt = next(caminhos["execucoes_avulsas_fichas_dir"].glob("*/prompt.md")).read_text(encoding="utf-8")
    assert "CT-CURR-06" in prompt
    assert "CT-TRANS-03" in prompt
    assert "CT-TRANS-05" not in prompt
    html = caminhos["relatorio_html"].read_text(encoding="utf-8")
    assert "CT-CURR-06" in html
    assert "NAO_ATENDE" in html


def test_consolidacao_ignora_sobreposicao_de_ficha_mais_antiga_que_lote_canonico(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-CURR-06", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-CURR-06"), _resultado("CT-TRANS-05", evidencias=3)]}),
    )
    assert avaliar_lote(rodada_dir, "batch-001", "codex", "codex-default", forcar=True)["status"] == "ok"

    batch_id_avulso = _execution_id("fichas", ["CT-CURR-06"], _copiar_fichas_por_id(tmp_path / "ids-stale", ["CT-CURR-06"]))
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_FICHAS",
        json.dumps({"batch_id": batch_id_avulso, "resultados": [_resultado("CT-CURR-06", estado="NAO_ATENDE")]}),
    )
    assert reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=["CT-CURR-06"],
        validacao_ids=[],
        provider="codex",
        model="codex-default",
        forcar=True,
        gerar_relatorio=True,
    )["relatorio_html"]

    status_path = caminhos["resultados_dir"] / "batch-001.status.json"
    status = read_json(status_path)
    status["executado_em"] = "2999-01-01T00:00:00-03:00"
    write_json(status_path, status)

    consolidar_rodada(rodada_dir)
    resultados = read_json(caminhos["resultados_fichas"])
    item = next(item for item in resultados["itens"] if item["ficha_id"] == "CT-CURR-06")
    assert item["estado"] == "ATENDE"
    assert item["batch_id"] == "batch-001"
    assert "execucao_avulsa" not in item


def test_reavaliar_validacao_por_id_recalcula_ct_trans_05(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-SUP-12", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-SUP-12"), _resultado("CT-TRANS-05", evidencias=3)]}),
    )
    assert avaliar_lote(rodada_dir, "batch-001", "codex", "codex-default", forcar=True)["status"] == "ok"

    validacoes = _copiar_validacoes_por_id(tmp_path / "ids-validacoes", ["VC-01-05"])
    validacao_id_avulso = _execution_id("validacoes", ["VC-01-05"], validacoes)
    assert validacao_id_avulso.startswith("avulso-validacoes-")
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_VALIDACOES",
        json.dumps(
            {
                "escopo": "validacoes_cruzadas",
                "validacoes": [_resultado_cruzada("VC-01-05", estado="NAO_ATENDE", revisao_humana=True)],
            }
        ),
    )

    payload = reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=[],
        validacao_ids=["VC-01-05"],
        provider="codex",
        model="codex-default",
        forcar=True,
        gerar_relatorio=True,
    )

    assert all(item["status"] == "ok" for item in payload["status"])
    sobreposicoes = read_json(caminhos["sobreposicoes_validacoes_cruzadas"])
    assert set(sobreposicoes["itens"]) == {"VC-01-05"}
    resultados = read_json(caminhos["resultados_fichas"])
    ct_trans_05 = next(item for item in resultados["itens"] if item["ficha_id"] == "CT-TRANS-05")
    assert ct_trans_05["estado"] == "NAO_ATENDE"
    assert "VC-01-05" in ct_trans_05["derivado_de"]["validacoes_cruzadas"]
    validacoes_payload = read_json(caminhos["validacoes_cruzadas"])
    assert {item["id"] for item in validacoes_payload["validacoes"]} == {"VC-01-05"}
    status_consolidado = read_json(caminhos["validacoes_cruzadas_status"])
    assert status_consolidado["escopo"] == "validacoes_cruzadas_consolidado"
    assert status_consolidado["resultado_sha256"] == hashlib.sha256(caminhos["validacoes_cruzadas"].read_bytes()).hexdigest()
    prompt = next(caminhos["execucoes_avulsas_validacoes_dir"].glob("*/prompt.md")).read_text(encoding="utf-8")
    assert "VC-01-05" in prompt
    assert "VC-04-05" not in prompt


def test_reavaliar_cache_de_resposta_corrompida_reexecuta_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-CURR-06", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-CURR-06"), _resultado("CT-TRANS-05", evidencias=3)]}),
    )
    assert avaliar_lote(rodada_dir, "batch-001", "codex", "codex-default", forcar=True)["status"] == "ok"

    batch_id_avulso = _execution_id("fichas", ["CT-CURR-06"], _copiar_fichas_por_id(tmp_path / "ids-cache", ["CT-CURR-06"]))
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_FICHAS",
        json.dumps({"batch_id": batch_id_avulso, "resultados": [_resultado("CT-CURR-06", estado="NAO_ATENDE")]}),
    )
    assert reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=["CT-CURR-06"],
        validacao_ids=[],
        provider="codex",
        model="codex-default",
        forcar=True,
        gerar_relatorio=False,
    )["status"][0]["status"] == "ok"

    exec_dir = next(caminhos["execucoes_avulsas_fichas_dir"].glob("*"))
    write_json(exec_dir / "resposta.json", {"batch_id": batch_id_avulso, "resultados": []})
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_FICHAS",
        json.dumps({"batch_id": batch_id_avulso, "resultados": [_resultado("CT-CURR-06", estado="ATENDE")]}),
    )

    payload = reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=["CT-CURR-06"],
        validacao_ids=[],
        provider="codex",
        model="codex-default",
        forcar=False,
        gerar_relatorio=False,
    )

    assert payload["status"][0]["status"] == "ok"
    resposta = read_json(exec_dir / "resposta.json")
    assert resposta["resultados"][0]["estado"] == "ATENDE"


def test_reavaliar_rejeita_ids_invalidos_antes_de_chamar_provider(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)

    with pytest.raises(ErroReavaliacao, match="duplicados"):
        reavaliar_rodada(rodada_dir, ficha_ids=["CT-CURR-06", "CT-CURR-06"], validacao_ids=[])

    with pytest.raises(ErroReavaliacao, match="não encontrados"):
        reavaliar_rodada(rodada_dir, ficha_ids=["CT-NAO-EXISTE"], validacao_ids=[])

    with pytest.raises(ErroReavaliacao, match="ao menos"):
        reavaliar_rodada(rodada_dir, ficha_ids=[], validacao_ids=[])


def test_reavaliar_sem_relatorio_nao_altera_consolidacao_existente(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas = _copiar_fichas_por_id(tmp_path / "fichas-lote", ["CT-CURR-06", "CT-TRANS-05"])
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(fichas),
        "fichas": fichas,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)
    gerar_pre_validacoes_rodada(rodada_dir)
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE",
        json.dumps({"batch_id": "batch-001", "resultados": [_resultado("CT-CURR-06"), _resultado("CT-TRANS-05", evidencias=3)]}),
    )
    assert avaliar_lote(rodada_dir, "batch-001", "codex", "codex-default", forcar=True)["status"] == "ok"
    consolidar_rodada(rodada_dir)
    gerar_relatorio_html(rodada_dir)
    resultados_antes = caminhos["resultados_fichas"].read_text(encoding="utf-8")
    parecer_antes = caminhos["parecer_final"].read_text(encoding="utf-8")
    html_antes = caminhos["relatorio_html"].read_text(encoding="utf-8")

    batch_id_avulso = _execution_id("fichas", ["CT-CURR-06"], _copiar_fichas_por_id(tmp_path / "ids-sem-relatorio", ["CT-CURR-06"]))
    monkeypatch.setenv(
        "MOCK_PROVIDER_RESPONSE_FICHAS",
        json.dumps({"batch_id": batch_id_avulso, "resultados": [_resultado("CT-CURR-06", estado="NAO_ATENDE")]}),
    )
    payload = reavaliar_rodada(
        rodada_dir=rodada_dir,
        ficha_ids=["CT-CURR-06"],
        validacao_ids=[],
        provider="codex",
        model="codex-default",
        forcar=True,
        gerar_relatorio=False,
    )

    assert all(item["status"] == "ok" for item in payload["status"])
    assert caminhos["sobreposicoes_fichas"].exists()
    assert caminhos["resultados_fichas"].read_text(encoding="utf-8") == resultados_antes
    assert caminhos["parecer_final"].read_text(encoding="utf-8") == parecer_antes
    assert caminhos["relatorio_html"].read_text(encoding="utf-8") == html_antes


def test_avaliar_todos_bloqueia_quando_ppc_da_rodada_fica_vazio(tmp_path: Path) -> None:
    from avaliar_lote import avaliar_todos

    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    gerar_batches_rodada(rodada_dir, batch_size=20, fichas_dir=fichas_dir)
    caminhos["ppc"].write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="bloqueios estruturais"):
        avaliar_todos(rodada_dir=rodada_dir, provider="codex", model="codex-default")


def test_avaliar_todos_bloqueia_quando_batches_nao_foram_gerados(tmp_path: Path) -> None:
    from avaliar_lote import avaliar_todos

    rodada_dir = _criar_rodada(tmp_path)

    with pytest.raises(RuntimeError, match="Nenhum batch"):
        avaliar_todos(rodada_dir=rodada_dir, provider="codex", model="codex-default")


def test_avaliar_todos_bloqueia_batch_id_inexistente(tmp_path: Path) -> None:
    from avaliar_lote import avaliar_todos

    rodada_dir = _criar_rodada(tmp_path)
    gerar_batches_rodada(rodada_dir, batch_size=20)

    with pytest.raises(RuntimeError, match="batch-999"):
        avaliar_todos(
            rodada_dir=rodada_dir,
            provider="codex",
            model="codex-default",
            batch_ids=["batch-999"],
        )


def test_gerar_pre_validacoes_detecta_batches_nao_gerados(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    payload = gerar_pre_validacoes_rodada(rodada_dir)
    item = next(item for item in payload["pre_validacoes"]["obrigatorias"] if item["id"] == "PV-005")
    assert item["status"] == "INCONCLUSIVO"


def test_consolidacao_falha_quando_lote_fica_desatualizado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    subconjunto = _copiar_subconjunto_fichas(fichas_dir, tmp_path / "fichas-lote", 2)
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(subconjunto),
        "fichas": subconjunto,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)

    resposta_ok = {
        "batch_id": "batch-001",
        "resultados": [_resultado(subconjunto[0]["id"]), _resultado(subconjunto[1]["id"])],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))

    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert status["status"] == "ok"

    caminhos["ppc"].write_text(_markdown_base() + "\n## 9. Alteração posterior\n\nTexto novo.\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="desatualizado"):
        consolidar_rodada(rodada_dir, modo_situacao="padrao")


def test_consolidacao_falha_quando_provider_ou_modelo_divergem_da_rodada(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    mock_codex = _criar_mock_codex(tmp_path)
    monkeypatch.setenv("ANALISE_PPC_CODEX_BIN", str(mock_codex))
    monkeypatch.setenv("MOCK_PROVIDER_EXIT_CODE", "0")

    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    subconjunto = _copiar_subconjunto_fichas(fichas_dir, tmp_path / "fichas-lote", 2)
    batch = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": len(subconjunto),
        "fichas": subconjunto,
    }
    caminhos = round_paths(rodada_dir)
    write_json(caminhos["batches_dir"] / "batch-001.json", batch)

    resposta_ok = {
        "batch_id": "batch-001",
        "resultados": [_resultado(subconjunto[0]["id"]), _resultado(subconjunto[1]["id"])],
    }
    monkeypatch.setenv("MOCK_PROVIDER_RESPONSE", json.dumps(resposta_ok))

    status = avaliar_lote(
        rodada_dir=rodada_dir,
        batch_id="batch-001",
        provider="codex",
        model="codex-default",
        forcar=True,
    )
    assert status["status"] == "ok"

    manifesto = read_json(caminhos["manifesto"])
    manifesto["provider_padrao"] = "gemini"
    manifesto["modelo_padrao"] = "gemini-2.5-pro"
    write_json(caminhos["manifesto"], manifesto)

    with pytest.raises(RuntimeError, match="desatualizado"):
        consolidar_rodada(rodada_dir, modo_situacao="padrao")


def test_consolidacao_falha_com_ficha_duplicada_entre_batches(tmp_path: Path) -> None:
    rodada_dir = _criar_rodada(tmp_path)
    caminhos = round_paths(rodada_dir)
    contexto_estrutural = carregar_contexto_estrutural(rodada_dir)
    fichas_dir = tmp_path / "fichas"
    _copiar_catalogo_canonico(fichas_dir)
    subconjunto = _copiar_subconjunto_fichas(fichas_dir, tmp_path / "fichas-lote", 2)

    batch_1 = {
        "batch_id": "batch-001",
        "ordem": 1,
        "total_fichas": 1,
        "fichas": [subconjunto[0]],
    }
    batch_2 = {
        "batch_id": "batch-002",
        "ordem": 2,
        "total_fichas": 1,
        "fichas": [subconjunto[0]],
    }
    write_json(caminhos["batches_dir"] / "batch-001.json", batch_1)
    write_json(caminhos["batches_dir"] / "batch-002.json", batch_2)

    for batch in (batch_1, batch_2):
        write_json(
            caminhos["resultados_dir"] / f"{batch['batch_id']}.status.json",
            {
                "batch_id": batch["batch_id"],
                "status": "ok",
                "provider": "codex",
                "modelo": "codex-default",
                "ppc_sha256": read_json(caminhos["manifesto"])["ppc_sha256"],
                "batch_sha256": hashlib.sha256((caminhos["batches_dir"] / f"{batch['batch_id']}.json").read_bytes()).hexdigest(),
                "prompt_sha256": hashlib.sha256(
                    renderizar_prompt_lote(
                        read_json(caminhos["metadata"]),
                        caminhos["ppc"].read_text(encoding="utf-8"),
                        batch,
                        pre_validacoes=contexto_estrutural["pre_validacoes"],
                        condicionais_rodada=contexto_estrutural["condicionais_rodada"],
                        contexto_estrutural=contexto_estrutural["contexto_estrutural"],
                    ).encode("utf-8")
                ).hexdigest(),
                "fichas_esperadas": 1,
                "fichas_recebidas": 1,
                "executado_em": "2026-04-18T12:00:00-03:00",
            },
        )
        write_json(
            caminhos["resultados_dir"] / f"{batch['batch_id']}.resposta.json",
            {
                "batch_id": batch["batch_id"],
                "resultados": [_resultado(subconjunto[0]["id"])],
            },
        )

    with pytest.raises(RuntimeError, match="duplicado"):
        consolidar_rodada(rodada_dir, modo_situacao="padrao")
