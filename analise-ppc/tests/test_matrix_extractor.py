from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conversao_docx import ConversionService
from conversao_docx.matrix_extractor import MatrixExtractor
from conversao_docx.table_extractor import NormalizedTable


def _table(rows: list[list[str]]) -> NormalizedTable:
    return NormalizedTable(
        headers=rows[0],
        rows=rows[1:],
        original_row_count=len(rows),
        original_col_count=len(rows[0]),
    )


def _legacy_rows(ano: str, componentes: list[str], total_ha: str = "1320", total_hr: str = "1100*") -> list[list[str]]:
    return [
        ["", "", "", "", ""],
        *[[ano, nome, "2", "80", "67"] for nome in componentes],
        [ano, "Subtotal (Total do período)", "33", total_ha, total_hr],
    ]


def _nucleos_fixture_rows() -> list[list[str]]:
    componentes = [
        ("1", "Arte, Forma e Função", "2", "80", "", "", "80", "67"),
        ("1", "Biologia I", "3", "", "120", "", "120", "100"),
        ("1", "Computação Aplicada ao Desenho Bidimensional", "3", "120", "", "", "120", "100"),
        ("1", "Desenho Arquitetônico", "3", "120", "", "", "120", "100"),
        ("1", "Educação Física I", "2", "", "80", "", "80", "67"),
        ("1", "Empreendedorismo, Liderança e Educação Financeira", "2", "80", "", "", "80", "67"),
        ("1", "Física I", "2", "", "80", "", "80", "67"),
        ("1", "Geografia I", "2", "", "80", "", "80", "67"),
        ("1", "Língua Espanhola I", "2", "", "80", "", "80", "67"),
        ("1", "Língua Portuguesa I", "3", "", "120", "", "120", "100"),
        ("1", "Matemática I", "3", "", "120", "", "120", "100"),
        ("1", "Materiais de Construção Civil", "2", "80", "", "", "80", "67"),
        ("1", "Química I", "2", "", "80", "", "80", "67"),
        ("1", "Sociologia I", "2", "", "80", "", "80", "67"),
        ("2", "Arte I", "2", "", "80", "", "80", "67"),
        ("2", "Construção Civil", "2", "80", "", "", "80", "67"),
        ("2", "Educação Física II", "2", "", "80", "", "80", "67"),
        ("2", "Filosofia I", "2", "", "80", "", "80", "67"),
        ("2", "Física II", "3", "", "120", "", "120", "100"),
        ("2", "Geografia II", "2", "", "80", "", "80", "67"),
        ("2", "História I", "2", "", "80", "", "80", "67"),
        ("2", "Instalações Prediais", "3", "120", "", "", "120", "100"),
        ("2", "Língua Inglesa I", "1", "", "40", "", "40", "33"),
        ("2", "Língua Portuguesa II", "2", "", "80", "", "80", "67"),
        ("2", "Matemática II", "3", "", "120", "", "120", "100"),
        ("2", "Mecânica das Estruturas", "2", "80", "", "", "80", "67"),
        ("2", "Projeto Arquitetônico e Modelagem Tridimensional", "3", "120", "", "", "120", "100"),
        ("2", "Sociologia II", "2", "", "80", "", "80", "67"),
        ("2", "Topografia", "2", "80", "", "", "80", "67"),
        ("3", "Arte II", "2", "", "80", "", "80", "67"),
        ("3", "Biologia II", "2", "", "80", "", "80", "67"),
        ("3", "Compatibilização de Projetos", "3", "120", "", "", "120", "100"),
        ("3", "Estruturas de Concreto, Aço e Madeira", "4", "160", "", "", "160", "133"),
        ("3", "Filosofia II", "2", "", "80", "", "80", "67"),
        ("3", "Fundações e Mecânica do Solos", "2", "80", "", "", "80", "67"),
        ("3", "Gestão da Construção Civil", "2", "80", "", "", "80", "67"),
        ("3", "História II", "3", "", "120", "", "120", "100"),
        ("3", "Língua Espanhola II", "1", "", "40", "", "40", "33"),
        ("3", "Língua Inglesa II", "2", "", "80", "", "80", "67"),
        ("3", "Língua Portuguesa III", "3", "", "120", "", "120", "100"),
        ("3", "Matemática III", "3", "", "120", "", "120", "100"),
        ("3", "Produção Textual e Pesquisa", "1", "40", "", "", "40", "33"),
        ("3", "Química II", "3", "", "120", "", "120", "100"),
    ]

    rows = [
        ["MATRIZ CURRICULAR CURSO TÉCNICO EM EDIFICAÇÕES INTEGRADO AO ENSINO MÉDIO"] * 8,
        ["LEGENDA"] * 8,
        ["FGB: Formação Geral Básica FTP: Formação Técnico-Profissional (conforme CNCT) NP: Núcleo Politécnico"] * 5
        + ["CH: Carga horária HA: Hora-aula HR: Hora-relógio"] * 3,
        ["Semanas do ano letivo", "Semanas do ano letivo", "40", "", "", "", "", ""],
        ["CH em Hora-aula (min)", "CH em Hora-aula (min)", "50", "", "", "", "", ""],
    ]
    for ano in ("1", "2", "3"):
        rows.append(["Ano", "Componente Curricular", "No. de aulas semanais", "Hora-aula FTP", "Hora-aula FGB", "Hora-aula NP", "Hora-aula TOTAL", "Hora relógio TOTAL"])
        for componente in componentes:
            if componente[0] == ano:
                rows.append(list(componente))
        rows.append(["TOTAL ANO HORA-AULA", "TOTAL ANO HORA-AULA", "TOTAL ANO HORA-AULA", "480", "840", "0", "1320", ""])
        rows.append(["TOTAL ANO HORA-RELÓGIO", "TOTAL ANO HORA-RELÓGIO", "TOTAL ANO HORA-RELÓGIO", "400", "700", "0", "", "1100"])
    rows.extend(
        [
            ["(AC) Atividades Complementares (min. 200 horas-relógio)"] * 6 + ["", ""],
            ["(ES) Estágio Supervisionado (min. 400 horas-relógio)"] * 6 + ["", ""],
            ["", "", "", "FTP", "FGB", "NP", "TOTAL", ""],
            ["C.H. (HORA RELÓGIO) TOTAL DO CURSO"] * 3 + ["1200", "2100", "0", "3300", ""],
        ]
    )
    return rows


def test_extrai_matriz_legacy_fragmentada_com_tres_anos() -> None:
    extractor = MatrixExtractor()
    partes = [
        _table(
            [
                ["MATRIZ CURRICULAR CURSO TÉCNICO EM EDIFICAÇÕES INTEGRADO AO ENSINO MÉDIO"] * 5,
                ["", "Semanas do ano letivo", "40", "", ""],
                ["", "CH em Hora-aula (min)", "50", "", ""],
                ["Ano", "Componente Curricular", "Número de aulas semanais", "CH hora-aula no período", "CH hora-relógio no período"],
                *_legacy_rows("1º Ano", [f"Componente 1.{i}" for i in range(1, 15)])[1:],
            ]
        ),
        _table(_legacy_rows("2º Ano", [f"Componente 2.{i}" for i in range(1, 16)])),
        _table(
            [
                *_legacy_rows("3º Ano", [f"Componente 3.{i}" for i in range(1, 15)]),
                ["Hora-aula", "Hora-relógio", "", "", ""],
                ["(AC) Atividades Complementares (min. 200 horas-relógio)", "(AC) Atividades Complementares (min. 200 horas-relógio)", "", "0", "0"],
                ["(ES) Estágio Supervisionado (min. 400 horas-relógio)", "(ES) Estágio Supervisionado (min. 400 horas-relógio)", "", "0", "0"],
                ["CARGA HORÁRIA TOTAL DO CURSO", "CARGA HORÁRIA TOTAL DO CURSO", "CARGA HORÁRIA TOTAL DO CURSO", "3960", "3300"],
            ]
        ),
    ]

    matriz = None
    for parte in partes:
        matriz = extractor.merge_matrix_data(matriz, extractor.extract_ppc_matrix_data(parte))

    assert matriz["formato"] == "legacy"
    assert [len(ano["componentes"]) for ano in matriz["anos"]] == [14, 15, 14]
    assert matriz["totais"]["ch_total_hora_aula"] == 3960
    assert matriz["totais"]["ch_total_hora_relogio"] == 3300
    assert len(matriz["linhas_modelo"]) == 2


def test_extrai_matriz_nova_com_nucleos_ftp_fgb_np() -> None:
    matriz = MatrixExtractor().extract_ppc_matrix_data(_table(_nucleos_fixture_rows()))

    assert matriz["formato"] == "nucleos_ftp_fgb_np"
    assert [len(ano["componentes"]) for ano in matriz["anos"]] == [14, 15, 14]
    assert matriz["totais"]["ch_ftp"] == 1200
    assert matriz["totais"]["ch_fgb"] == 2100
    assert matriz["totais"]["ch_np"] == 0
    assert matriz["totais"]["ch_total_hora_relogio"] == 3300
    assert matriz["totais"]["ch_total_hora_aula"] == 3960
    assert all(linha["ch_hora_relogio"] is None for linha in matriz["linhas_modelo"])


def test_quadro_docente_nao_e_classificado_como_matriz() -> None:
    quadro_docente = _table(
        [
            ["Nome", "Área de formação", "Perfil de Formação", "Componente Curricular"],
            ["Docente A", "Engenharia", "Mestre", "Estruturas"],
            ["Docente B", "Matemática", "Doutora", "Matemática I"],
        ]
    )

    assert MatrixExtractor().extract_ppc_matrix_data(quadro_docente) is None
    assert MatrixExtractor().extract_matrix_data(quadro_docente) is None


def test_markdown_normalizado_recebe_matriz_canonica_sem_ruido_de_merge() -> None:
    extractor = MatrixExtractor()
    matriz = extractor.extract_ppc_matrix_data(_table(_nucleos_fixture_rows()))
    markdown = """## Sumário

## 5.6 MATRIZ CURRICULAR 29

## 5.6 MATRIZ CURRICULAR

No Quadro 1, é apresentada a matriz curricular.

| MATRIZ CURRICULAR CURSO TÉCNICO EM EDIFICAÇÕES INTEGRADO AO ENSINO MÉDIO | MATRIZ CURRICULAR CURSO TÉCNICO EM EDIFICAÇÕES INTEGRADO AO ENSINO MÉDIO |
|---|---|
| FGB: Formação Geral Básica FTP: Formação Técnico-Profissional (conforme CNCT) NP: Núcleo Politécnico | CH: Carga horária HA: Hora-aula HR: Hora-relógio |
| Ano | Componente Curricular |
| 1 | Arte, Forma e Função |

- **Nota sobre o somatório da Carga Horária**: texto.

## 5.7 EMENTÁRIO
"""

    normalizado = extractor.replace_matrix_markdown(markdown, matriz)

    secao_matriz = normalizado.split("## 5.6 MATRIZ CURRICULAR", 2)[2].split("## 5.7 EMENTÁRIO", 1)[0]
    assert "MATRIZ CURRICULAR CURSO" not in secao_matriz
    assert "FGB: Formação Geral Básica FTP" not in secao_matriz
    assert "| Ano | Componente Curricular | No. de aulas semanais | Hora-aula FTP" in secao_matriz
    assert "| 3 | Química II |" in secao_matriz


def test_conversao_docx_v2_extrai_matriz_nova_quando_amostra_local_existe(tmp_path: Path) -> None:
    source = Path("/Users/gustavo/Desktop/PPCs/Umuarama - PPC - Técnico em Edificações - 2026-v2.docx")
    if not source.exists():
        pytest.skip("Amostra local do PPC v2 não está disponível neste ambiente.")

    artefatos = ConversionService().convert(source, output_dir=tmp_path)
    matriz_path = artefatos.matriz_curricular
    markdown_path = artefatos.markdown

    import json

    matriz = json.loads(matriz_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert matriz["formato"] == "nucleos_ftp_fgb_np"
    assert [len(ano["componentes"]) for ano in matriz["anos"]] == [14, 15, 14]
    assert matriz["totais"]["ch_ftp"] == 1200
    assert matriz["totais"]["ch_fgb"] == 2100
    assert matriz["totais"]["ch_np"] == 0
    assert matriz["totais"]["ch_total_hora_relogio"] == 3300
    assert "MATRIZ CURRICULAR CURSO TÉCNICO" not in markdown.split("## 5.7 EMENTÁRIO", 1)[0]
    assert '"Nome", "Área de formação"' not in matriz_path.read_text(encoding="utf-8")
