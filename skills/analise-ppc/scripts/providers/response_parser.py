from __future__ import annotations

import json
import re
from typing import Any


def _tentar_json(texto: str) -> Any:
    return json.loads(texto)


def _iterar_blocos_json(texto: str) -> list[str]:
    candidatos: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", texto, flags=re.DOTALL | re.IGNORECASE):
        candidatos.append(match.group(1).strip())

    pilha = 0
    inicio = None
    em_string = False
    escape = False
    for indice, caractere in enumerate(texto):
        if em_string:
            if escape:
                escape = False
                continue
            if caractere == "\\":
                escape = True
                continue
            if caractere == '"':
                em_string = False
            continue
        if caractere == '"':
            em_string = True
            continue
        if caractere == "{":
            if pilha == 0:
                inicio = indice
            pilha += 1
        elif caractere == "}":
            if pilha == 0:
                continue
            pilha -= 1
            if pilha == 0 and inicio is not None:
                candidatos.append(texto[inicio : indice + 1])
                inicio = None
    return candidatos


def extrair_json_de_resposta(texto: str) -> dict[str, Any]:
    texto_limpo = texto.strip()
    if not texto_limpo:
        raise ValueError("A resposta bruta da IA está vazia.")

    candidatos = [texto_limpo]
    candidatos.extend(_iterar_blocos_json(texto_limpo))
    ultimo_erro: Exception | None = None
    for candidato in candidatos:
        try:
            payload = _tentar_json(candidato)
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"Não foi possível extrair um objeto JSON válido da resposta bruta. Último erro: {ultimo_erro}")
