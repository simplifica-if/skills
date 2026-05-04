from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from common import FICHAS_DIR, load_fichas, read_json, round_paths

ESTADOS_PERMITIDOS = {"ATENDE", "NAO_ATENDE", "INCONCLUSIVO", "NAO_APLICAVEL"}


class ErroResultadosSubagents(ValueError):
    pass


def _resolver_resultados_path(rodada_dir: Path, resultados_path: Path) -> Path:
    if resultados_path.is_absolute():
        return resultados_path
    caminhos = round_paths(rodada_dir)
    candidato_suporte = caminhos["suporte_dir"] / resultados_path
    if candidato_suporte.exists():
        return candidato_suporte
    return rodada_dir / resultados_path


def _catalogo_fichas(fichas_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    fichas = sorted(load_fichas(fichas_dir or FICHAS_DIR), key=lambda ficha: str(ficha.get("id", "")))
    return {str(ficha["id"]): ficha for ficha in fichas}


def _blocos_resultados(payload: dict[str, Any]) -> list[dict[str, Any]]:
    grupos = payload.get("grupos")
    if isinstance(grupos, list):
        return grupos
    resultados = payload.get("resultados")
    if isinstance(resultados, list):
        return [{"grupo_id": str(payload.get("grupo_id") or "grupo-unico"), "resultados": resultados}]
    raise ErroResultadosSubagents("O JSON precisa conter `grupos[]` ou `resultados[]`.")


def validar_resultados_subagents(
    payload: dict[str, Any],
    fichas_por_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    vistos: set[str] = set()
    normalizados: list[dict[str, Any]] = []
    duplicados: list[str] = []
    desconhecidos: list[str] = []

    for bloco in _blocos_resultados(payload):
        grupo_id = str(bloco.get("grupo_id") or "").strip()
        resultados = bloco.get("resultados")
        if not grupo_id:
            raise ErroResultadosSubagents("Um bloco de resultados não contém `grupo_id`.")
        if not isinstance(resultados, list):
            raise ErroResultadosSubagents(f"O bloco {grupo_id} não contém `resultados[]`.")
        for item in resultados:
            if not isinstance(item, dict):
                raise ErroResultadosSubagents(f"O bloco {grupo_id} contém item que não é objeto JSON.")
            ficha_id = str(item.get("ficha_id") or "").strip()
            if not ficha_id:
                raise ErroResultadosSubagents(f"O bloco {grupo_id} contém item sem `ficha_id`.")
            if ficha_id in vistos:
                duplicados.append(ficha_id)
                continue
            vistos.add(ficha_id)
            if ficha_id not in fichas_por_id:
                desconhecidos.append(ficha_id)
                continue
            estado = str(item.get("estado") or "").strip()
            if estado not in ESTADOS_PERMITIDOS:
                raise ErroResultadosSubagents(f"Estado inválido para {ficha_id}: {estado}")
            confianca = item.get("confianca")
            if not isinstance(confianca, (int, float)) or not (0 <= float(confianca) <= 1):
                raise ErroResultadosSubagents(f"Confiança inválida para {ficha_id}: {confianca}")
            justificativa = str(item.get("justificativa") or "").strip()
            if not justificativa:
                raise ErroResultadosSubagents(f"`justificativa` ausente para {ficha_id}.")
            evidencias = item.get("evidencias")
            lacunas = item.get("lacunas")
            revisao = item.get("revisao_humana_obrigatoria")
            if not isinstance(evidencias, list):
                raise ErroResultadosSubagents(f"`evidencias` precisa ser lista para {ficha_id}.")
            evidencias_normalizadas = [str(valor).strip() for valor in evidencias if str(valor).strip()]
            evidencia_minima = int(fichas_por_id[ficha_id].get("evidencia_minima", 1))
            if len(evidencias_normalizadas) < evidencia_minima:
                raise ErroResultadosSubagents(
                    f"{ficha_id} trouxe {len(evidencias_normalizadas)} evidências; mínimo exigido: {evidencia_minima}."
                )
            if not isinstance(lacunas, list):
                raise ErroResultadosSubagents(f"`lacunas` precisa ser lista para {ficha_id}.")
            if not isinstance(revisao, bool):
                raise ErroResultadosSubagents(f"`revisao_humana_obrigatoria` precisa ser booleano para {ficha_id}.")
            ficha = fichas_por_id[ficha_id]
            normalizados.append(
                {
                    "grupo_id": grupo_id,
                    "ficha_id": ficha_id,
                    "titulo": str(ficha.get("titulo") or ficha_id),
                    "dominio": str(ficha.get("dominio") or ""),
                    "criticidade": str(ficha.get("criticidade") or ""),
                    "secoes_preferenciais": list(ficha.get("secoes_preferenciais") or []),
                    "estado": estado,
                    "confianca": float(confianca),
                    "justificativa": justificativa,
                    "evidencias": evidencias_normalizadas,
                    "lacunas": [str(valor).strip() for valor in lacunas if str(valor).strip()],
                    "revisao_humana_obrigatoria": revisao,
                }
            )

    if duplicados:
        raise ErroResultadosSubagents("Fichas duplicadas: " + ", ".join(sorted(set(duplicados))))
    if desconhecidos:
        raise ErroResultadosSubagents("Fichas desconhecidas: " + ", ".join(sorted(set(desconhecidos))))
    faltantes = sorted(set(fichas_por_id) - vistos)
    if faltantes:
        raise ErroResultadosSubagents("Fichas sem resultado: " + ", ".join(faltantes))
    return sorted(normalizados, key=lambda item: item["ficha_id"])


def validar_alertas_transversais(payload: dict[str, Any], fichas_por_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    bruto = payload.get("alertas_transversais")
    if bruto is None and isinstance(payload.get("sintese_transversal"), dict):
        bruto = payload["sintese_transversal"].get("alertas_transversais")
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise ErroResultadosSubagents("`alertas_transversais` precisa ser uma lista.")
    alertas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for indice, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            raise ErroResultadosSubagents("Cada alerta transversal precisa ser objeto JSON.")
        alerta_id = str(item.get("id") or f"ALERTA-{indice:03d}").strip()
        if alerta_id in vistos:
            raise ErroResultadosSubagents(f"Alerta transversal duplicado: {alerta_id}")
        vistos.add(alerta_id)
        titulo = str(item.get("titulo") or "").strip()
        descricao = str(item.get("descricao") or "").strip()
        criticidade = str(item.get("criticidade") or "OBRIG").strip()
        fichas_relacionadas = item.get("fichas_relacionadas") or []
        evidencias = item.get("evidencias") or []
        revisao = item.get("revisao_humana_obrigatoria")
        if not titulo or not descricao:
            raise ErroResultadosSubagents(f"Alerta transversal {alerta_id} precisa de título e descrição.")
        if criticidade not in {"BLOQ", "OBRIG", "REC"}:
            raise ErroResultadosSubagents(f"Criticidade inválida para {alerta_id}: {criticidade}")
        if not isinstance(fichas_relacionadas, list):
            raise ErroResultadosSubagents(f"`fichas_relacionadas` precisa ser lista para {alerta_id}.")
        desconhecidas = [ficha_id for ficha_id in fichas_relacionadas if str(ficha_id) not in fichas_por_id]
        if desconhecidas:
            raise ErroResultadosSubagents(
                f"Alerta {alerta_id} referencia fichas desconhecidas: " + ", ".join(map(str, desconhecidas))
            )
        if not isinstance(evidencias, list):
            raise ErroResultadosSubagents(f"`evidencias` precisa ser lista para {alerta_id}.")
        if not isinstance(revisao, bool):
            raise ErroResultadosSubagents(f"`revisao_humana_obrigatoria` precisa ser booleano para {alerta_id}.")
        alertas.append(
            {
                "id": alerta_id,
                "titulo": titulo,
                "criticidade": criticidade,
                "descricao": descricao,
                "fichas_relacionadas": [str(ficha_id) for ficha_id in fichas_relacionadas],
                "evidencias": [str(valor).strip() for valor in evidencias if str(valor).strip()],
                "revisao_humana_obrigatoria": revisao,
            }
        )
    return alertas


def _situacao(resultados: list[dict[str, Any]]) -> str:
    bloqueantes = [item for item in resultados if item["criticidade"] == "BLOQ" and item["estado"] == "NAO_ATENDE"]
    obrigatorios = [item for item in resultados if item["criticidade"] == "OBRIG" and item["estado"] == "NAO_ATENDE"]
    inconclusivos = [item for item in resultados if item["estado"] == "INCONCLUSIVO"]
    revisoes = [item for item in resultados if item["revisao_humana_obrigatoria"]]
    if bloqueantes:
        return "NAO_APROVADO"
    if obrigatorios:
        return "DILIGENCIA"
    if inconclusivos or revisoes:
        return "COM_RESSALVAS"
    return "APROVADO"


def _render_lista(valores: list[str]) -> str:
    if not valores:
        return "<span class=\"muted\">Não informado</span>"
    itens = "".join(f"<li>{escape(valor)}</li>" for valor in valores)
    return f"<ul>{itens}</ul>"


def _render_alertas(alertas: list[dict[str, Any]]) -> str:
    if not alertas:
        return "<p class=\"muted\">Nenhum alerta transversal registrado.</p>"
    cards = []
    for alerta in alertas:
        fichas = ", ".join(alerta["fichas_relacionadas"]) or "Sem fichas específicas"
        cards.append(
            "<article class=\"alert-card\">"
            f"<div class=\"finding-heading\"><h3>{escape(alerta['id'])} · {escape(alerta['titulo'])}</h3>"
            f"<span class=\"badge criticidade-{escape(alerta['criticidade'].lower())}\">{escape(alerta['criticidade'])}</span></div>"
            f"<p>{escape(alerta['descricao'])}</p>"
            f"<p><strong>Fichas relacionadas:</strong> {escape(fichas)}</p>"
            f"<section><h4>Evidências</h4>{_render_lista(alerta['evidencias'])}</section>"
            f"<p><strong>Revisão humana obrigatória:</strong> {'Sim' if alerta['revisao_humana_obrigatoria'] else 'Não'}</p>"
            "</article>"
        )
    return "".join(cards)


def _render_html(
    metadata: dict[str, Any],
    resultados: list[dict[str, Any]],
    alertas: list[dict[str, Any]],
    resultados_path: Path,
) -> str:
    contagem_estado = Counter(item["estado"] for item in resultados)
    contagem_criticidade = Counter(item["criticidade"] for item in resultados)
    situacao = _situacao(resultados)
    revisao_humana = sum(1 for item in resultados if item["revisao_humana_obrigatoria"])
    nao_atende = sum(1 for item in resultados if item["estado"] == "NAO_ATENDE")
    inconclusivos = sum(1 for item in resultados if item["estado"] == "INCONCLUSIVO")
    linhas = []
    for item in resultados:
        linhas.append(
            "<article class=\"finding\" "
            f"data-estado=\"{escape(item['estado'])}\" "
            f"data-criticidade=\"{escape(item['criticidade'])}\" "
            f"data-revisao=\"{'sim' if item['revisao_humana_obrigatoria'] else 'nao'}\" "
            f"data-texto=\"{escape(' '.join([item['ficha_id'], item['titulo'], item['justificativa'], ' '.join(item['evidencias']), ' '.join(item['lacunas'])]).casefold())}\">"
            f"<div class=\"finding-heading\"><h3>{escape(item['ficha_id'])} · {escape(item['titulo'])}</h3>"
            f"<span class=\"badge estado-{escape(item['estado'].lower().replace('_', '-'))}\">{escape(item['estado'])}</span></div>"
            f"<p><strong>Criticidade:</strong> {escape(item['criticidade'])} · "
            f"<strong>Confiança:</strong> {item['confianca']:.2f} · "
            f"<strong>Grupo:</strong> {escape(item['grupo_id'])}</p>"
            f"<p>{escape(item['justificativa'])}</p>"
            "<div class=\"finding-grid\">"
            f"<section><h4>Evidências</h4>{_render_lista(item['evidencias'])}</section>"
            f"<section><h4>Lacunas</h4>{_render_lista(item['lacunas'])}</section>"
            "</div>"
            f"<p><strong>Revisão humana obrigatória:</strong> {'Sim' if item['revisao_humana_obrigatoria'] else 'Não'}</p>"
            "</article>"
        )

    estados_html = "".join(
        f"<tr><th scope=\"row\">{escape(estado)}</th><td>{quantidade}</td></tr>"
        for estado, quantidade in sorted(contagem_estado.items())
    )
    criticidade_html = "".join(
        f"<tr><th scope=\"row\">{escape(criticidade)}</th><td>{quantidade}</td></tr>"
        for criticidade, quantidade in sorted(contagem_criticidade.items())
    )
    resumo = (
        f"A análise revisou {len(resultados)} fichas por sub-agentes na conversa. "
        f"Foram identificados {nao_atende} itens não atendidos, {inconclusivos} inconclusivos "
        f"e {revisao_humana} itens com revisão humana obrigatória."
    )
    css = """
body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f5f7fa; }
.page { max-width: 1120px; margin: 0 auto; padding: 32px 20px 48px; }
.report-header, .section, .finding { background: #fff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.eyebrow { color: #52606d; text-transform: uppercase; font-size: 12px; letter-spacing: .08em; }
h1, h2, h3, h4 { color: #102a43; }
.lead { font-size: 18px; line-height: 1.5; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.metric { border: 1px solid #d9e2ec; border-radius: 8px; padding: 14px; background: #f8fafc; }
.metric strong { display: block; font-size: 24px; color: #102a43; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #d9e2ec; padding: 10px; text-align: left; vertical-align: top; }
.badge { display: inline-block; border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 700; background: #d9e2ec; }
.estado-atende { background: #d1fae5; color: #065f46; }
.estado-nao-atende { background: #fee2e2; color: #991b1b; }
.estado-inconclusivo { background: #fef3c7; color: #92400e; }
.estado-nao-aplicavel { background: #e0e8f9; color: #334e68; }
.criticidade-bloq { background: #fee2e2; color: #991b1b; }
.criticidade-obrig { background: #fef3c7; color: #92400e; }
.criticidade-rec { background: #dbeafe; color: #1e40af; }
.finding-heading { display: flex; gap: 12px; align-items: start; justify-content: space-between; }
.finding-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: end; }
.filters label { display: grid; gap: 6px; font-weight: 700; }
.filters input, .filters select { min-height: 38px; border: 1px solid #bcccdc; border-radius: 6px; padding: 8px; font: inherit; }
.alert-card { border-left: 4px solid #d97706; padding: 14px 16px; background: #fffbeb; margin-bottom: 12px; }
.muted { color: #627d98; }
"""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório de análise · {escape(str(metadata.get('curso') or 'PPC'))}</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <header class="report-header">
      <p class="eyebrow">Análise de PPC · sub-agentes na conversa</p>
      <h1>{escape(str(metadata.get('curso') or 'Curso não identificado'))}</h1>
      <p class="lead">{escape(resumo)}</p>
      <p><strong>Situação:</strong> <span class="badge estado-{escape(situacao.lower().replace('_', '-'))}">{escape(situacao)}</span></p>
    </header>
    <section class="section">
      <h2>Metadados</h2>
      <table>
        <tbody>
          <tr><th scope="row">Campus</th><td>{escape(str(metadata.get('campus') or ''))}</td></tr>
          <tr><th scope="row">Modalidade</th><td>{escape(str(metadata.get('modalidade') or ''))}</td></tr>
          <tr><th scope="row">Arquivo de resultados</th><td>{escape(str(resultados_path))}</td></tr>
          <tr><th scope="row">Rodada</th><td>{escape(str(metadata.get('rodada_dir') or ''))}</td></tr>
        </tbody>
      </table>
    </section>
    <section class="section">
      <h2>Resumo executivo</h2>
      <div class="metrics">
        <div class="metric"><span>Total de fichas</span><strong>{len(resultados)}</strong></div>
        <div class="metric"><span>Não atendidas</span><strong>{nao_atende}</strong></div>
        <div class="metric"><span>Inconclusivas</span><strong>{inconclusivos}</strong></div>
        <div class="metric"><span>Revisão humana</span><strong>{revisao_humana}</strong></div>
        <div class="metric"><span>Alertas transversais</span><strong>{len(alertas)}</strong></div>
      </div>
    </section>
    <section class="section">
      <h2>Filtros</h2>
      <div class="filters">
        <label>Busca
          <input id="filtro-busca" type="search" placeholder="Ficha, justificativa, evidência ou lacuna">
        </label>
        <label>Estado
          <select id="filtro-estado">
            <option value="">Todos</option>
            <option value="ATENDE">ATENDE</option>
            <option value="NAO_ATENDE">NAO_ATENDE</option>
            <option value="INCONCLUSIVO">INCONCLUSIVO</option>
            <option value="NAO_APLICAVEL">NAO_APLICAVEL</option>
          </select>
        </label>
        <label>Criticidade
          <select id="filtro-criticidade">
            <option value="">Todas</option>
            <option value="BLOQ">BLOQ</option>
            <option value="OBRIG">OBRIG</option>
            <option value="REC">REC</option>
          </select>
        </label>
        <label>Revisão humana
          <select id="filtro-revisao">
            <option value="">Todas</option>
            <option value="sim">Sim</option>
            <option value="nao">Não</option>
          </select>
        </label>
      </div>
      <p class="muted">Itens visíveis: <strong id="contador-visivel">{len(resultados)}</strong></p>
    </section>
    <section class="section">
      <h2>Alertas transversais</h2>
      {_render_alertas(alertas)}
    </section>
    <section class="section">
      <h2>Contagens</h2>
      <div class="finding-grid">
        <section><h3>Por estado</h3><table><tbody>{estados_html}</tbody></table></section>
        <section><h3>Por criticidade</h3><table><tbody>{criticidade_html}</tbody></table></section>
      </div>
    </section>
    <section class="section">
      <h2>Achados por ficha</h2>
      {''.join(linhas)}
    </section>
  </main>
  <script>
    const busca = document.getElementById("filtro-busca");
    const estado = document.getElementById("filtro-estado");
    const criticidade = document.getElementById("filtro-criticidade");
    const revisao = document.getElementById("filtro-revisao");
    const contador = document.getElementById("contador-visivel");
    const itens = Array.from(document.querySelectorAll(".finding"));

    function aplicarFiltros() {{
      const termo = (busca.value || "").toLocaleLowerCase("pt-BR");
      let visiveis = 0;
      for (const item of itens) {{
        const okBusca = !termo || item.dataset.texto.includes(termo);
        const okEstado = !estado.value || item.dataset.estado === estado.value;
        const okCriticidade = !criticidade.value || item.dataset.criticidade === criticidade.value;
        const okRevisao = !revisao.value || item.dataset.revisao === revisao.value;
        const visivel = okBusca && okEstado && okCriticidade && okRevisao;
        item.hidden = !visivel;
        if (visivel) visiveis += 1;
      }}
      contador.textContent = String(visiveis);
    }}

    [busca, estado, criticidade, revisao].forEach((elemento) => {{
      elemento.addEventListener("input", aplicarFiltros);
      elemento.addEventListener("change", aplicarFiltros);
    }});
  </script>
</body>
</html>
"""


def gerar_relatorio_html(rodada_dir: Path, resultados_path: Path) -> dict[str, Any]:
    caminhos = round_paths(rodada_dir)
    metadata = read_json(caminhos["metadata"])
    caminho_resultados = _resolver_resultados_path(caminhos["rodada_dir"], resultados_path)
    payload = read_json(caminho_resultados)
    fichas_por_id = _catalogo_fichas()
    resultados = validar_resultados_subagents(payload, fichas_por_id)
    alertas = validar_alertas_transversais(payload, fichas_por_id)
    html = _render_html(metadata, resultados, alertas, caminho_resultados)
    destino = caminhos["relatorio_html"]
    destino.write_text(html, encoding="utf-8")
    return {
        "relatorio_html": destino,
        "total_fichas": len(resultados),
        "total_alertas_transversais": len(alertas),
        "situacao": _situacao(resultados),
    }
