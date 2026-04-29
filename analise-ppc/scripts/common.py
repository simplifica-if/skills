from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

APP_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = APP_DIR / "config"
PROMPTS_DIR = APP_DIR / "prompts"
BASE_ANALISE_DIR = APP_DIR / "base-analise"
FICHAS_DIR = BASE_ANALISE_DIR / "fichas"
VALIDACOES_CRUZADAS_DIR = BASE_ANALISE_DIR / "validacoes-cruzadas"
CONTRATOS_DIR = BASE_ANALISE_DIR / "contratos"
BASE_ANALISE_INDICE_PATH = BASE_ANALISE_DIR / "indice.json"
TEMPLATES_DIR = APP_DIR / "templates"
OUTPUT_DIR = APP_DIR / "output"
POLITICA_PARECER_PATH = CONFIG_DIR / "politica_parecer.json"

DEFAULT_BATCH_SIZE = 20
DEFAULT_PROVIDER = "codex"
DEFAULT_MODEL = "codex-default"
IDENTIFICACAO_PLACEHOLDERS = {
    "curso não identificado",
    "campus não identificado",
    "modalidade não identificada",
    "forma de oferta não identificada",
    "modalidade de ensino não identificada",
}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_directory(path.parent)
    path.write_text(text, encoding="utf-8")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dt%H-%M-%S")


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-") or "arquivo"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json_payload(payload: Any) -> str:
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_paths(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(item) for item in paths), key=lambda item: str(item)):
        digest.update(str(path.relative_to(path.anchor if path.is_absolute() else Path("."))).encode("utf-8", errors="ignore"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_catalogo_fichas(fichas_dir: Path | None = None) -> str:
    diretorio = fichas_dir or FICHAS_DIR
    arquivos = list(sorted(diretorio.glob("*.json")))
    if not arquivos:
        return sha256_text("[]")
    digest = hashlib.sha256()
    for arquivo in arquivos:
        digest.update(arquivo.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(arquivo.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def copy_file(src: Path, dst: Path) -> Path:
    ensure_directory(dst.parent)
    shutil.copy2(src, dst)
    return dst


def load_fichas(fichas_dir: Path | None = None) -> list[dict[str, Any]]:
    diretorio = fichas_dir or FICHAS_DIR
    fichas: list[dict[str, Any]] = []
    for caminho in sorted(diretorio.glob("*.json")):
        fichas.append(read_json(caminho))
    return fichas


def load_validacoes_cruzadas(validacoes_dir: Path | None = None) -> list[dict[str, Any]]:
    diretorio = validacoes_dir or VALIDACOES_CRUZADAS_DIR
    validacoes: list[dict[str, Any]] = []
    for caminho in sorted(diretorio.glob("*.json")):
        validacoes.append(read_json(caminho))
    return validacoes


def valor_identificacao_preenchido(valor: Any) -> bool:
    texto = str(valor or "").strip()
    return bool(texto) and texto.casefold() not in IDENTIFICACAO_PLACEHOLDERS


def round_paths(rodada_dir: Path) -> dict[str, Path]:
    rodada_dir = rodada_dir.resolve()
    legacy_root_files = (
        rodada_dir / "PPC.md",
        rodada_dir / "metadata.json",
        rodada_dir / "manifesto-rodada.json",
    )
    suporte_dir = rodada_dir / "arquivos-suporte"
    base_dir = rodada_dir if not suporte_dir.exists() and any(path.exists() for path in legacy_root_files) else suporte_dir
    return {
        "rodada_dir": rodada_dir,
        "suporte_dir": base_dir,
        "artefatos_conversao_dir": base_dir / "artefatos-conversao",
        "ppc": base_dir / "PPC.md",
        "ppc_bruto": base_dir / "PPC-bruto.md",
        "metadata": base_dir / "metadata.json",
        "manifesto": base_dir / "manifesto-rodada.json",
        "preparacao_docx": base_dir / "preparacao-docx.json",
        "pre_validacoes": base_dir / "pre-validacoes.json",
        "condicionais_rodada": base_dir / "condicionais-rodada.json",
        "contexto_estrutural": base_dir / "contexto-estrutural.json",
        "cnct_comparacao": base_dir / "cnct-comparacao.json",
        "validacoes_cruzadas": base_dir / "validacoes-cruzadas.json",
        "validacoes_cruzadas_status": base_dir / "validacoes-cruzadas.status.json",
        "validacoes_cruzadas_prompt": base_dir / "validacoes-cruzadas.prompt.md",
        "validacoes_cruzadas_resposta_bruta": base_dir / "validacoes-cruzadas.resposta-bruta.md",
        "validacoes_cruzadas_catalogo": base_dir / "validacoes-cruzadas.catalogo.json",
        "execucoes_avulsas_dir": base_dir / "execucoes-avulsas",
        "execucoes_avulsas_fichas_dir": base_dir / "execucoes-avulsas" / "fichas",
        "execucoes_avulsas_validacoes_dir": base_dir / "execucoes-avulsas" / "validacoes-cruzadas",
        "sobreposicoes_fichas": base_dir / "execucoes-avulsas" / "sobreposicoes-fichas.json",
        "sobreposicoes_validacoes_cruzadas": base_dir / "execucoes-avulsas" / "sobreposicoes-validacoes-cruzadas.json",
        "uso_tokens": base_dir / "uso-tokens.json",
        "batches_dir": base_dir / "batches",
        "resultados_dir": base_dir / "resultados-lotes",
        "resultados_fichas": base_dir / "resultados-fichas.json",
        "achados": base_dir / "achados.json",
        "parecer_final": base_dir / "parecer-final.json",
        "relatorio_html": rodada_dir / "relatorio-analise.html",
    }


def infer_identificacao_from_markdown(texto: str, fallback_nome: str = "") -> dict[str, str]:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    texto_unico = "\n".join(linhas)

    def _match(patterns: list[str], default: str = "") -> str:
        for pattern in patterns:
            match = re.search(pattern, texto_unico, flags=re.IGNORECASE)
            if match:
                return " ".join(match.group(1).split())
        return default

    curso = _match(
        [
            r"curso\s*:\s*(.+)",
            r"nome do curso\s*:\s*(.+)",
            r"^#\s*(curso\s+t[ée]cnico.+)$",
            r"^#\s*(.+curso.+)$",
        ],
        default=fallback_nome,
    )
    campus = _match([r"campus\s*:\s*(.+)", r"unidade\s*:\s*(.+)"])
    forma_oferta = _match([r"forma\s+de\s+oferta\s*:\s*(.+)"])
    modalidade_ensino = _match([r"modalidade\s*:\s*(.+)"])
    modalidade = forma_oferta
    if not modalidade:
        texto_maiusculo = texto_unico.upper()
        if "INTEGRADO" in texto_maiusculo:
            modalidade = "Integrado"
        elif "SUBSEQUENTE" in texto_maiusculo:
            modalidade = "Subsequente"
        elif "CONCOMITANTE" in texto_maiusculo:
            modalidade = "Concomitante"

    return {
        "curso": curso or fallback_nome or "Curso não identificado",
        "campus": campus or "Campus não identificado",
        "modalidade": modalidade or "Modalidade não identificada",
        "forma_oferta": forma_oferta or modalidade or "Forma de oferta não identificada",
        "modalidade_ensino": modalidade_ensino or "Modalidade de ensino não identificada",
    }


def extract_identificacao_from_conversion_json(payload: dict[str, Any], fallback_nome: str = "") -> dict[str, str]:
    dados = payload.get("dados_extraidos") if isinstance(payload, dict) else {}
    if not isinstance(dados, dict):
        dados = payload
    curso = (
        _valor_por_chaves_ou_prefixos(
            dados,
            chaves=("curso_cnct", "denominacao", "denominacao_curso", "nome_do_curso", "Curso", "curso"),
            prefixos=("denominacao_", "nome_do_curso_", "curso_"),
            exige_padrao=r"\bcurso\s+t[ée]cnico\b",
        )
        or _valor_por_chaves_ou_prefixos(dados, chaves=("nome_curso",))
        or fallback_nome
        or "Curso não identificado"
    )
    campus = _valor_por_chaves_ou_prefixos(
        dados,
        chaves=("campus", "Campus", "unidade"),
        prefixos=("campus_", "unidade_"),
    ) or "Campus não identificado"
    forma_oferta = _valor_por_chaves_ou_prefixos(
        dados,
        chaves=("forma_oferta", "Forma de oferta", "Forma de Oferta"),
        prefixos=("forma_de_oferta_",),
    )
    modalidade_ensino = (
        _valor_por_chaves_ou_prefixos(
            dados,
            chaves=("modalidade_ensino", "Modalidade de ensino", "Modalidade de Ensino", "modalidade", "Modalidade"),
            prefixos=("modalidade_", "modalidade_de_ensino_"),
        )
    )
    modalidade_raw = _valor_por_chaves_ou_prefixos(dados, chaves=("modalidade", "Modalidade"), prefixos=("modalidade_",))
    eixo_tecnologico = _valor_por_chaves_ou_prefixos(
        dados,
        chaves=("eixo_tecnologico", "Eixo Tecnológico", "Eixo tecnologico"),
        prefixos=("eixo_tecnologico_",),
    )
    modalidade = forma_oferta or modalidade_raw or "Modalidade não identificada"
    return {
        "curso": str(curso),
        "campus": str(campus),
        "modalidade": str(modalidade),
        "forma_oferta": str(forma_oferta or modalidade),
        "modalidade_ensino": str(modalidade_ensino or "Modalidade de ensino não identificada"),
        "eixo_tecnologico": str(eixo_tecnologico) if eixo_tecnologico else "",
    }


def _valor_por_chaves_ou_prefixos(
    dados: dict[str, Any],
    chaves: tuple[str, ...] = (),
    prefixos: tuple[str, ...] = (),
    exige_padrao: str | None = None,
) -> str:
    for chave in chaves:
        valor = _limpar_valor_identificacao(dados.get(chave))
        if valor and (exige_padrao is None or re.search(exige_padrao, valor, flags=re.IGNORECASE)):
            return valor
    for chave, valor_bruto in dados.items():
        if not any(str(chave).startswith(prefixo) for prefixo in prefixos):
            continue
        valor = _limpar_valor_identificacao(valor_bruto)
        if valor and (exige_padrao is None or re.search(exige_padrao, valor, flags=re.IGNORECASE)):
            return valor
    return ""


def _limpar_valor_identificacao(valor: Any) -> str:
    texto = str(valor or "").strip()
    texto = re.sub(
        r"^(?:denomina[çc][ãa]o|nome\s+do\s+curso|curso|campus|unidade|forma\s+de\s+oferta|modalidade(?:\s+de\s+ensino)?|eixo\s+tecnol[óo]gico)\s*:\s*",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    return " ".join(texto.split())


def safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def update_manifesto_base(
    rodada_dir: Path,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    fichas_dir: Path | None = None,
) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    manifesto = {
        "rodada_id": rodada_dir.name,
        "rodada_dir": str(rodada_dir.resolve()),
        "ppc_sha256": sha256_file(caminhos["ppc"]),
        "fichas_sha256": sha256_catalogo_fichas(fichas_dir),
        "prompt_base_sha256": sha256_file(PROMPTS_DIR / "lote_fichas.md"),
        "batch_size": batch_size,
        "provider_padrao": provider,
        "modelo_padrao": model,
        "criado_em": now_iso(),
    }
    write_json(caminhos["manifesto"], manifesto)
    return manifesto
