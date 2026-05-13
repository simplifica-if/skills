from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conversao_docx.docx_reader import TableCell, TableElement
from conversao_docx.ementario_extractor import EmentarioExtractor
from conversao_docx.table_extractor import NormalizedTable, TableExtractor


def test_markdown_de_tabela_preserva_quebras_internas_da_celula() -> None:
    tabela = TableElement(
        rows=[
            [TableCell("Campo")],
            [
                TableCell(
                    "BIBLIOGRAFIA BÁSICA:\n"
                    "SILVA, Ana. Livro um. São Paulo: Atlas, 2020.\n"
                    "SOUZA, Bruno. Livro dois. Curitiba: InterSaberes, 2021."
                )
            ],
        ]
    )

    normalizada = TableExtractor().normalize(tabela)
    markdown = TableExtractor().to_markdown(normalizada)

    assert (
        "BIBLIOGRAFIA BÁSICA:<br>"
        "SILVA, Ana. Livro um. São Paulo: Atlas, 2020.<br>"
        "SOUZA, Bruno. Livro dois. Curitiba: InterSaberes, 2021."
    ) in markdown


def test_ementario_trata_br_markdown_como_quebra_de_referencia() -> None:
    tabela = NormalizedTable(
        headers=["COMPONENTE CURRICULAR: Química I"],
        rows=[
            ["Período letivo: 1º Ano"],
            ["Carga horária total do componente: 80 horas-aula / 67 horas-relógio"],
            ["EMENTA: Introdução à Química."],
            [
                "BIBLIOGRAFIA BÁSICA: "
                "SILVA, Ana. Livro um. São Paulo: Atlas, 2020.<br>"
                "SOUZA, Bruno. Livro dois. Curitiba: InterSaberes, 2021."
            ],
            [
                "BIBLIOGRAFIA COMPLEMENTAR: "
                "BRASIL. Catálogo Nacional de Cursos Técnicos. Brasília: MEC, 2024."
            ],
        ],
        original_row_count=5,
        original_col_count=1,
    )

    ementa = EmentarioExtractor().extract_ementario_data(tabela)

    assert ementa is not None
    assert ementa["bibliografia_basica"] == [
        "SILVA, Ana. Livro um. São Paulo: Atlas, 2020.",
        "SOUZA, Bruno. Livro dois. Curitiba: InterSaberes, 2021.",
    ]
