from __future__ import annotations

from pathlib import Path
from typing import Any

from common import DEFAULT_BATCH_SIZE, load_fichas, round_paths, write_json


def gerar_batches_rodada(
    rodada_dir: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    fichas_dir: Path | None = None,
) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    fichas = sorted(load_fichas(fichas_dir), key=lambda item: item["id"])
    if not fichas:
        raise RuntimeError("Nenhuma ficha JSON foi encontrada para gerar os batches.")

    arquivos_gerados: list[Path] = []
    for indice, inicio in enumerate(range(0, len(fichas), batch_size), start=1):
        lote_fichas = fichas[inicio : inicio + batch_size]
        payload = {
            "batch_id": f"batch-{indice:03d}",
            "ordem": indice,
            "total_fichas": len(lote_fichas),
            "fichas": lote_fichas,
        }
        destino = caminhos["batches_dir"] / f"{payload['batch_id']}.json"
        write_json(destino, payload)
        arquivos_gerados.append(destino)

    return {
        "rodada_dir": rodada_dir.resolve(),
        "total_batches": len(arquivos_gerados),
        "total_fichas": len(fichas),
        "batch_size": batch_size,
        "arquivos": arquivos_gerados,
    }
