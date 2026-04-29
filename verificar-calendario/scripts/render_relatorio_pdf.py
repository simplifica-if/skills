from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def markdown_inline_para_html(texto: str) -> str:
    texto = html.escape(texto.strip())
    texto = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", texto)
    return texto


def carregar_relatorio(caminho: Path) -> dict:
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    titulo = linhas[0].lstrip("# ").strip()
    subtitulo = linhas[1].lstrip("# ").strip()

    metadados: list[tuple[str, str]] = []
    tabela: list[list[str]] = []
    conclusoes: list[tuple[str, str]] = []

    i = 2
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith("**") and ":**" in linha:
            chave, valor = linha.split(":**", 1)
            metadados.append((chave.strip("*"), valor.strip()))
        elif linha.startswith("| Item |"):
            i += 2
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                partes = [p.strip() for p in linhas[i].strip().strip("|").split("|")]
                if len(partes) == 3:
                    tabela.append(partes)
                i += 1
            continue
        elif re.match(r"^\d+\.\s+\*\*", linha):
            match = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$", linha)
            if match:
                conclusoes.append((match.group(2).strip(), match.group(3).strip()))
        i += 1

    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "metadados": metadados,
        "tabela": tabela,
        "conclusoes": conclusoes,
    }


def construir_pdf(entrada: Path, saida: Path) -> None:
    relatorio = carregar_relatorio(entrada)
    doc = SimpleDocTemplate(
        str(saida),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=relatorio["titulo"],
        author="Codex",
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloRelatorio",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloRelatorio",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1f4fa5"),
        spaceAfter=10,
    )
    estilo_meta = ParagraphStyle(
        "MetaRelatorio",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=10,
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    estilo_celula = ParagraphStyle(
        "CelulaRelatorio",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.2,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    estilo_cabecalho = ParagraphStyle(
        "CabecalhoRelatorio",
        parent=estilos["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7.4,
        leading=8.8,
        alignment=TA_CENTER,
        textColor=colors.white,
    )
    estilo_secao = ParagraphStyle(
        "SecaoRelatorio",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#163a70"),
        spaceBefore=10,
        spaceAfter=5,
    )
    estilo_conclusao = ParagraphStyle(
        "ConclusaoRelatorio",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        leftIndent=10,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    elementos = [
        Paragraph(markdown_inline_para_html(relatorio["titulo"]), estilo_titulo),
        Paragraph(markdown_inline_para_html(relatorio["subtitulo"]), estilo_subtitulo),
    ]

    for chave, valor in relatorio["metadados"]:
        elementos.append(
            Paragraph(
                f"<b>{markdown_inline_para_html(chave)}:</b> {markdown_inline_para_html(valor)}",
                estilo_meta,
            )
        )

    elementos.append(Spacer(1, 6))

    dados_tabela = [
        [
            Paragraph("Item", estilo_cabecalho),
            Paragraph("Status", estilo_cabecalho),
            Paragraph("Observação/Evidência", estilo_cabecalho),
        ]
    ]
    for item, status, observacao in relatorio["tabela"]:
        dados_tabela.append(
            [
                Paragraph(markdown_inline_para_html(item), estilo_celula),
                Paragraph(markdown_inline_para_html(status), estilo_celula),
                Paragraph(markdown_inline_para_html(observacao), estilo_celula),
            ]
        )

    largura_util = A4[0] - doc.leftMargin - doc.rightMargin
    col_widths = [largura_util * 0.34, largura_util * 0.14, largura_util * 0.52]
    tabela = LongTable(
        dados_tabela,
        colWidths=col_widths,
        repeatRows=1,
        splitByRow=1,
    )
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163a70")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8092b3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eef3fa")]),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ]
        )
    )
    elementos.append(tabela)

    if relatorio["conclusoes"]:
        elementos.append(Paragraph("Conclusão", estilo_secao))
        for indice, (pergunta, resposta) in enumerate(relatorio["conclusoes"], start=1):
            elementos.append(
                Paragraph(
                    f"{indice}. <b>{markdown_inline_para_html(pergunta)}</b> {markdown_inline_para_html(resposta)}",
                    estilo_conclusao,
                )
            )

    doc.build(elementos)


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: render_relatorio_pdf.py entrada.md saida.pdf")
        return 1

    entrada = Path(sys.argv[1]).resolve()
    saida = Path(sys.argv[2]).resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)
    construir_pdf(entrada, saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
