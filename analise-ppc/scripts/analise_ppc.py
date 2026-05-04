from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from gerar_relatorio_html import gerar_relatorio_html
from preparar_documento import preparar_documento
from subagents import mesclar_resultados_avulsos, montar_grupo_avulso, montar_grupos_subagents


def _print_payload(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _relatorio_payload(path: Path) -> dict[str, str]:
    relatorio = path.resolve()
    return {
        "relatorio_html": str(relatorio),
        "relatorio_url": relatorio.as_uri(),
        "mensagem": f"Relatório pronto: {relatorio.as_uri()}",
    }


def cmd_preparar_documento(args: argparse.Namespace) -> int:
    payload = preparar_documento(
        arquivo_entrada=Path(args.arquivo),
        output_base=Path(args.saida_base) if args.saida_base else None,
    )
    _print_payload(payload["resumo"])
    return 0


def cmd_montar_grupos_subagents(args: argparse.Namespace) -> int:
    payload = montar_grupos_subagents(
        rodada_dir=Path(args.rodada_dir),
        tamanho_grupo=args.tamanho_grupo,
    )
    _print_payload(payload)
    return 0


def cmd_gerar_relatorio_html(args: argparse.Namespace) -> int:
    payload = gerar_relatorio_html(
        rodada_dir=Path(args.rodada_dir),
        resultados_path=Path(args.resultados),
    )
    _print_payload(_relatorio_payload(payload["relatorio_html"]))
    return 0


def cmd_montar_grupo_avulso(args: argparse.Namespace) -> int:
    payload = montar_grupo_avulso(
        rodada_dir=Path(args.rodada_dir),
        ficha_ids=list(args.ficha_id or []),
    )
    _print_payload(payload)
    return 0


def cmd_mesclar_resultados_avulsos(args: argparse.Namespace) -> int:
    payload = mesclar_resultados_avulsos(
        rodada_dir=Path(args.rodada_dir),
        resultados_base_path=Path(args.resultados_base),
        resultados_avulsos_path=Path(args.resultados_avulsos),
        saida_path=Path(args.saida) if args.saida else None,
    )
    _print_payload(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Análise de PPC por sub-agentes na conversa")
    subparsers = parser.add_subparsers(dest="subcomando", required=True)

    parser_preparar = subparsers.add_parser("preparar-documento", help="Criar a rodada e o PPC.md canônico")
    parser_preparar.add_argument("arquivo", type=str, help="Arquivo .md ou .docx de entrada")
    parser_preparar.add_argument("--saida-base", type=str, help="Diretório base opcional para a rodada")
    parser_preparar.set_defaults(func=cmd_preparar_documento)

    parser_grupos = subparsers.add_parser(
        "montar-grupos-subagents",
        help="Listar grupos de fichas para sub-agentes e salvar grupos-subagents.json",
    )
    parser_grupos.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_grupos.add_argument("--tamanho-grupo", type=int, default=20, help="Quantidade de fichas por grupo")
    parser_grupos.set_defaults(func=cmd_montar_grupos_subagents)

    parser_avulso = subparsers.add_parser(
        "montar-grupo-avulso",
        help="Montar um grupo avulso de fichas para reavaliação por sub-agente",
    )
    parser_avulso.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_avulso.add_argument("--ficha-id", action="append", required=True, help="Ficha a incluir no grupo avulso")
    parser_avulso.set_defaults(func=cmd_montar_grupo_avulso)

    parser_mesclar = subparsers.add_parser(
        "mesclar-resultados-avulsos",
        help="Mesclar respostas avulsas em resultados-subagents.json",
    )
    parser_mesclar.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_mesclar.add_argument(
        "--resultados-base",
        type=str,
        default="resultados-subagents.json",
        help="JSON base de resultados; relativo a arquivos-suporte quando não absoluto",
    )
    parser_mesclar.add_argument(
        "--resultados-avulsos",
        type=str,
        required=True,
        help="JSON retornado pelo sub-agente avulso; relativo a arquivos-suporte quando não absoluto",
    )
    parser_mesclar.add_argument(
        "--saida",
        type=str,
        help="Destino do JSON mesclado; padrão: sobrescreve --resultados-base",
    )
    parser_mesclar.set_defaults(func=cmd_mesclar_resultados_avulsos)

    parser_relatorio = subparsers.add_parser("gerar-relatorio-html", help="Gerar o relatório HTML final")
    parser_relatorio.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_relatorio.add_argument(
        "--resultados",
        type=str,
        default="resultados-subagents.json",
        help="JSON coletado dos sub-agentes; relativo a arquivos-suporte quando não absoluto",
    )
    parser_relatorio.set_defaults(func=cmd_gerar_relatorio_html)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
