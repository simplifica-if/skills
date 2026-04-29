from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from avaliar_cruzadas import avaliar_validacoes_cruzadas
from avaliar_lote import avaliar_lote, avaliar_todos
from consolidar_resultados import consolidar_rodada
from gerar_batches import gerar_batches_rodada
from gerar_relatorio_html import gerar_relatorio_html
from pre_validacoes import gerar_pre_validacoes_rodada
from preparar_documento import preparar_documento
from reavaliar import ErroReavaliacao, reavaliar_rodada
from uso_tokens import atualizar_uso_tokens_rodada


def _print_payload(payload: object) -> None:
    import json

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
        provider=args.provider,
        model=args.model,
        batch_size=args.batch_size,
    )
    _print_payload(payload["resumo"])
    return 0


def cmd_gerar_batches(args: argparse.Namespace) -> int:
    payload = gerar_batches_rodada(
        rodada_dir=Path(args.rodada_dir),
        batch_size=args.batch_size,
        fichas_dir=Path(args.fichas_dir) if args.fichas_dir else None,
    )
    _print_payload(
        {
            "rodada_dir": str(payload["rodada_dir"]),
            "total_batches": payload["total_batches"],
            "total_fichas": payload["total_fichas"],
            "batch_size": payload["batch_size"],
        }
    )
    return 0


def cmd_pre_validar(args: argparse.Namespace) -> int:
    payload = gerar_pre_validacoes_rodada(Path(args.rodada_dir))
    _print_payload(
        {
            "pre_validacoes_path": str(payload["pre_validacoes_path"]),
            "condicionais_path": str(payload["condicionais_path"]),
            "contexto_estrutural_path": str(payload["contexto_estrutural_path"]),
            "tem_bloqueios": payload["pre_validacoes"]["tem_bloqueios"],
            "bloqueios": payload["pre_validacoes"]["bloqueios"],
        }
    )
    return 0 if not payload["pre_validacoes"]["tem_bloqueios"] else 1


def cmd_avaliar_lote(args: argparse.Namespace) -> int:
    payload = avaliar_lote(
        rodada_dir=Path(args.rodada_dir),
        batch_id=args.batch_id,
        provider=args.provider,
        model=args.model,
        forcar=args.forcar,
    )
    _print_payload(payload)
    return 0 if payload.get("status") == "ok" else 1


def cmd_avaliar_todos(args: argparse.Namespace) -> int:
    payload = avaliar_todos(
        rodada_dir=Path(args.rodada_dir),
        provider=args.provider,
        model=args.model,
        forcar=args.forcar,
        batch_ids=list(args.batch_id or []),
    )
    _print_payload(payload)
    return 0 if all(item.get("status") == "ok" for item in payload["status"]) else 1


def cmd_avaliar_cruzadas(args: argparse.Namespace) -> int:
    payload = avaliar_validacoes_cruzadas(
        rodada_dir=Path(args.rodada_dir),
        provider=args.provider,
        model=args.model,
        forcar=args.forcar,
        validacoes_dir=Path(args.validacoes_dir) if args.validacoes_dir else None,
    )
    _print_payload(payload)
    return 0 if payload.get("status") == "ok" else 1


def cmd_consolidar(args: argparse.Namespace) -> int:
    payload = consolidar_rodada(
        rodada_dir=Path(args.rodada_dir),
        modo_situacao=args.modo_situacao,
    )
    _print_payload(
        {
            "resultados_fichas": str(payload["resultados_fichas"]),
            "achados": str(payload["achados"]),
            "parecer_final": str(payload["parecer_final"]),
            "situacao": payload["parecer"]["situacao"],
        }
    )
    return 0


def cmd_gerar_relatorio_html(args: argparse.Namespace) -> int:
    payload = gerar_relatorio_html(Path(args.rodada_dir))
    _print_payload(_relatorio_payload(payload["relatorio_html"]))
    return 0


def cmd_contabilizar_tokens(args: argparse.Namespace) -> int:
    payload = atualizar_uso_tokens_rodada(Path(args.rodada_dir))
    _print_payload(
        {
            "uso_tokens": str(Path(args.rodada_dir).resolve() / "uso-tokens.json"),
            "total_execucoes_com_uso": payload["total_execucoes_com_uso"],
            "totais": payload["totais"],
        }
    )
    return 0


def cmd_reavaliar(args: argparse.Namespace) -> int:
    try:
        payload = reavaliar_rodada(
            rodada_dir=Path(args.rodada_dir),
            ficha_ids=list(args.ficha_id or []),
            validacao_ids=list(args.validacao_id or []),
            provider=args.provider,
            model=args.model,
            forcar=args.forcar,
            gerar_relatorio=not args.sem_relatorio,
        )
    except ErroReavaliacao as exc:
        _print_payload({"status": "erro", "erro": str(exc)})
        return 1
    _print_payload(payload)
    return 0 if all(item.get("status") == "ok" for item in payload["status"]) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Análise de PPC IA-first")
    subparsers = parser.add_subparsers(dest="subcomando", required=True)

    parser_preparar = subparsers.add_parser("preparar-documento", help="Criar a rodada e o PPC.md canônico")
    parser_preparar.add_argument("arquivo", type=str, help="Arquivo .md ou .docx de entrada")
    parser_preparar.add_argument("--saida-base", type=str, help="Diretório base opcional para a rodada")
    parser_preparar.add_argument("--provider", type=str, default="codex", help="Provider padrão da rodada")
    parser_preparar.add_argument("--model", type=str, default="codex-default", help="Modelo padrão da rodada")
    parser_preparar.add_argument("--batch-size", type=int, default=20, help="Tamanho padrão dos lotes")
    parser_preparar.set_defaults(func=cmd_preparar_documento)

    parser_batches = subparsers.add_parser("gerar-batches", help="Gerar lotes estáveis de fichas")
    parser_batches.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_batches.add_argument("--batch-size", type=int, default=20, help="Tamanho dos lotes")
    parser_batches.add_argument("--fichas-dir", type=str, help="Catálogo alternativo de fichas")
    parser_batches.set_defaults(func=cmd_gerar_batches)

    parser_pre_validar = subparsers.add_parser("pre-validar", help="Gerar pré-validações e condicionais da rodada")
    parser_pre_validar.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_pre_validar.set_defaults(func=cmd_pre_validar)

    parser_avaliar_lote = subparsers.add_parser("avaliar-lote", help="Avaliar um lote específico")
    parser_avaliar_lote.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_avaliar_lote.add_argument("--batch-id", type=str, required=True, help="Identificador do lote")
    parser_avaliar_lote.add_argument("--provider", type=str, default="codex", help="Provider a usar")
    parser_avaliar_lote.add_argument("--model", type=str, default="codex-default", help="Modelo do provider")
    parser_avaliar_lote.add_argument("--forcar", action="store_true", help="Reexecutar mesmo com cache válido")
    parser_avaliar_lote.set_defaults(func=cmd_avaliar_lote)

    parser_avaliar_todos = subparsers.add_parser("avaliar-todos", help="Avaliar todos os lotes pendentes")
    parser_avaliar_todos.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_avaliar_todos.add_argument("--provider", type=str, default="codex", help="Provider a usar")
    parser_avaliar_todos.add_argument("--model", type=str, default="codex-default", help="Modelo do provider")
    parser_avaliar_todos.add_argument("--batch-id", action="append", help="Lote específico a incluir")
    parser_avaliar_todos.add_argument("--forcar", action="store_true", help="Reexecutar todos os lotes")
    parser_avaliar_todos.set_defaults(func=cmd_avaliar_todos)

    parser_avaliar_cruzadas = subparsers.add_parser(
        "avaliar-cruzadas",
        help="Avaliar validações cruzadas por agente",
    )
    parser_avaliar_cruzadas.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_avaliar_cruzadas.add_argument("--provider", type=str, default="codex", help="Provider a usar")
    parser_avaliar_cruzadas.add_argument("--model", type=str, default="codex-default", help="Modelo do provider")
    parser_avaliar_cruzadas.add_argument("--validacoes-dir", type=str, help="Catálogo alternativo de validações cruzadas")
    parser_avaliar_cruzadas.add_argument("--forcar", action="store_true", help="Reexecutar mesmo com cache válido")
    parser_avaliar_cruzadas.set_defaults(func=cmd_avaliar_cruzadas)

    parser_reavaliar = subparsers.add_parser(
        "reavaliar",
        help="Reavaliar fichas ou validações cruzadas específicas por ID",
    )
    parser_reavaliar.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_reavaliar.add_argument("--ficha-id", action="append", help="Ficha específica a reavaliar")
    parser_reavaliar.add_argument("--validacao-id", action="append", help="Validação cruzada específica a reavaliar")
    parser_reavaliar.add_argument("--provider", type=str, default="codex", help="Provider a usar")
    parser_reavaliar.add_argument("--model", type=str, default="codex-default", help="Modelo do provider")
    parser_reavaliar.add_argument("--forcar", action="store_true", help="Reexecutar mesmo com cache válido")
    parser_reavaliar.add_argument(
        "--sem-relatorio",
        action="store_true",
        help="Salvar sobreposições avulsas sem consolidar nem regenerar o HTML",
    )
    parser_reavaliar.set_defaults(func=cmd_reavaliar)

    parser_consolidar = subparsers.add_parser("consolidar", help="Consolidar resultados dos lotes válidos")
    parser_consolidar.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_consolidar.add_argument(
        "--modo-situacao",
        type=str,
        choices=["padrao", "sintetico"],
        default="padrao",
        help="Nomenclatura da situação final do parecer",
    )
    parser_consolidar.set_defaults(func=cmd_consolidar)

    parser_relatorio = subparsers.add_parser("gerar-relatorio-html", help="Gerar o relatório HTML final")
    parser_relatorio.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_relatorio.set_defaults(func=cmd_gerar_relatorio_html)

    parser_tokens = subparsers.add_parser(
        "contabilizar-tokens",
        help="Consolidar uso de tokens registrado nas execuções da rodada",
    )
    parser_tokens.add_argument("--rodada-dir", type=str, required=True, help="Diretório da rodada")
    parser_tokens.set_defaults(func=cmd_contabilizar_tokens)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
