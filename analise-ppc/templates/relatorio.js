(() => {
  const payload = JSON.parse(document.getElementById("report-data").textContent);
  const itens = payload.resultados.itens || [];
  const preValidacoes = payload.pre_validacoes || {};
  const condicionaisRodada = payload.condicionais_rodada?.condicionais || {};
  const validacoesCruzadas = payload.validacoes_cruzadas?.validacoes || [];
  const usoTokens = payload.uso_tokens || {};

  const elementos = {
    busca: document.getElementById("filtro-busca"),
    estado: document.getElementById("filtro-estado"),
    criticidade: document.getElementById("filtro-criticidade"),
    secao: document.getElementById("filtro-secao"),
    revisao: document.getElementById("filtro-revisao"),
    batch: document.getElementById("filtro-batch"),
    tabelaItens: document.getElementById("tabela-itens"),
    lista: document.getElementById("lista-itens"),
    contador: document.getElementById("resultados-contagem"),
    vazio: document.getElementById("estado-vazio"),
    tabelaValidacoesCruzadas: document.getElementById("tabela-validacoes-cruzadas"),
    tabelaUsoTokensResumo: document.getElementById("tabela-uso-tokens-resumo"),
    tabelaUsoTokensEscopos: document.getElementById("tabela-uso-tokens-escopos"),
    preValidacoes: document.getElementById("lista-pre-validacoes"),
    condicionais: document.getElementById("lista-condicionais"),
    validacoesCruzadas: document.getElementById("lista-validacoes-cruzadas"),
    validacoesCruzadasVazio: document.getElementById("validacoes-cruzadas-vazio"),
    resumoUsoTokens: document.getElementById("resumo-uso-tokens"),
    usoTokensEscopos: document.getElementById("lista-uso-tokens-escopos"),
    usoTokensVazio: document.getElementById("uso-tokens-vazio"),
  };

  function popularSelect(select, valores, rotuloTodos) {
    const opcoes = [`<option value="">${rotuloTodos}</option>`];
    valores.forEach((valor) => {
      opcoes.push(`<option value="${escapeHtml(valor)}">${escapeHtml(valor)}</option>`);
    });
    select.innerHTML = opcoes.join("");
  }

  popularSelect(elementos.estado, [...new Set(itens.map((item) => item.estado))].sort(), "Todos");
  popularSelect(elementos.criticidade, [...new Set(itens.map((item) => item.criticidade))].sort(), "Todas");
  popularSelect(
    elementos.secao,
    [...new Set(itens.flatMap((item) => item.secoes_preferenciais || []))].sort(),
    "Todas"
  );
  popularSelect(elementos.batch, [...new Set(itens.map((item) => item.batch_id))].sort(), "Todos");
  elementos.revisao.innerHTML = `
    <option value="">Todos</option>
    <option value="true">Sim</option>
    <option value="false">Não</option>
  `;

  function itemTexto(item) {
    return [
      item.ficha_id,
      item.titulo,
      item.justificativa,
      ...(item.evidencias || []),
      ...(item.lacunas || []),
      ...(item.secoes_preferenciais || []),
      item.batch_id,
    ]
      .join(" ")
      .toLowerCase();
  }

  function escapeHtml(valor) {
    return String(valor ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function filtrar() {
    const busca = elementos.busca.value.trim().toLowerCase();
    const estado = elementos.estado.value;
    const criticidade = elementos.criticidade.value;
    const secao = elementos.secao.value;
    const revisao = elementos.revisao.value;
    const batch = elementos.batch.value;

    return itens.filter((item) => {
      if (busca && !itemTexto(item).includes(busca)) return false;
      if (estado && item.estado !== estado) return false;
      if (criticidade && item.criticidade !== criticidade) return false;
      if (secao && !(item.secoes_preferenciais || []).includes(secao)) return false;
      if (revisao && String(item.revisao_humana_obrigatoria) !== revisao) return false;
      if (batch && item.batch_id !== batch) return false;
      return true;
    });
  }

  function classeValor(prefixo, valor) {
    return `${prefixo}-${String(valor || "indeterminado").toLowerCase().replaceAll("_", "-")}`;
  }

  function statusBadge(valor, prefixo = "estado") {
    const texto = valor || "INCONCLUSIVO";
    return `<span class="status-badge ${classeValor(prefixo, texto)}">${escapeHtml(texto)}</span>`;
  }

  function formatarValor(valor) {
    if (valor === true) return "Sim";
    if (valor === false) return "Não";
    if (valor === null || valor === undefined || valor === "") return "indeterminado";
    return String(valor);
  }

  function formatarNumero(valor) {
    return Number(valor || 0).toLocaleString("pt-BR");
  }

  function formatarLista(valores, vazio = "Não informado") {
    if (!Array.isArray(valores) || valores.length === 0) {
      return vazio;
    }
    return valores.join(", ");
  }

  function formatarModelosPorCli(modelosPorCli) {
    if (!modelosPorCli || Object.keys(modelosPorCli).length === 0) {
      return formatarLista(usoTokens.modelos);
    }
    return Object.entries(modelosPorCli)
      .map(([cli, modelos]) => `${cli}: ${formatarLista(modelos)}`)
      .join(" | ");
  }

  function rotuloEscopo(escopo) {
    const rotulos = {
      lote: "Lotes",
      validacoes_cruzadas: "Validações cruzadas",
      reavaliacao_fichas: "Reavaliações de fichas",
      reavaliacao_validacoes_cruzadas: "Reavaliações de validações cruzadas",
    };
    return rotulos[escopo] || escopo;
  }

  function listaOuTexto(entradas, vazio) {
    if (!entradas || entradas.length === 0) {
      return escapeHtml(vazio);
    }

    return `<ul>${entradas.map((entrada) => `<li>${escapeHtml(entrada)}</li>`).join("")}</ul>`;
  }

  function renderizarItens() {
    const visiveis = filtrar();
    elementos.contador.textContent = String(visiveis.length);
    elementos.vazio.hidden = visiveis.length > 0;
    elementos.tabelaItens.hidden = visiveis.length === 0;
    elementos.lista.innerHTML = visiveis
      .map(
        (item, indice) => `
          <tr class="evidence-main-row ${classeValor("grupo", item.estado)}">
            <th scope="row">${escapeHtml(item.ficha_id)}</th>
            <td class="item-title">${escapeHtml(item.titulo)}</td>
            <td>${statusBadge(item.estado)}</td>
            <td>${statusBadge(item.criticidade, "criticidade")}</td>
            <td>${escapeHtml(item.confianca)}</td>
            <td>${escapeHtml((item.secoes_preferenciais || []).join(", ") || "Sem indicação")}</td>
            <td>${item.revisao_humana_obrigatoria ? "Sim" : "Não"}</td>
            <td>${escapeHtml(item.batch_id)}</td>
          </tr>
          <tr class="detail-row evidence-detail-row ${classeValor("grupo", item.estado)}">
            <td colspan="8">
              <details class="item-details" id="detalhes-item-${indice}">
                <summary>Justificativa, evidências e lacunas</summary>
                <table class="data-table nested-table">
                  <tbody>
                    <tr>
                      <th scope="row">Justificativa</th>
                      <td class="long-text">${escapeHtml(item.justificativa || "Sem justificativa registrada")}</td>
                    </tr>
                    <tr>
                      <th scope="row">Evidências</th>
                      <td class="long-text">${listaOuTexto(item.evidencias, "Sem evidências registradas")}</td>
                    </tr>
                    <tr>
                      <th scope="row">Lacunas</th>
                      <td class="long-text">${listaOuTexto(item.lacunas, "Sem lacunas registradas")}</td>
                    </tr>
                  </tbody>
                </table>
              </details>
            </td>
          </tr>
        `
      )
      .join("");
  }

  function renderizarPreValidacoes() {
    const obrigatorias = preValidacoes.obrigatorias || [];
    const opcionais = preValidacoes.estruturais_opcionais || [];
    const linhas = [...obrigatorias, ...opcionais].map(
      (item) => `
        <tr>
          <th scope="row">${escapeHtml(item.id)}</th>
          <td>${escapeHtml(item.descricao)}</td>
          <td>${statusBadge(item.status)}</td>
          <td>${statusBadge(item.criticidade, "criticidade")}</td>
          <td>${escapeHtml(item.fonte || "-")}</td>
          <td class="long-text">${escapeHtml(item.detalhe || "")}</td>
        </tr>
      `
    );
    elementos.preValidacoes.innerHTML =
      linhas.join("") || '<tr><td colspan="6">Nenhuma pré-validação registrada.</td></tr>';
  }

  function renderizarCondicionais() {
    const linhas = Object.entries(condicionaisRodada).map(
      ([chave, valor]) => `
        <tr>
          <th scope="row">${escapeHtml(chave)}</th>
          <td>${escapeHtml(formatarValor(valor.valor))}</td>
          <td>${statusBadge(valor.status || "INCONCLUSIVO")}</td>
          <td>${escapeHtml(valor.fonte || "-")}</td>
          <td class="long-text">${escapeHtml(valor.evidencia || "")}</td>
        </tr>
      `
    );
    elementos.condicionais.innerHTML =
      linhas.join("") || '<tr><td colspan="5">Nenhuma condicional registrada.</td></tr>';
  }

  function renderizarValidacoesCruzadas() {
    const existemValidacoes = validacoesCruzadas.length > 0;
    elementos.validacoesCruzadasVazio.hidden = existemValidacoes;
    elementos.tabelaValidacoesCruzadas.hidden = !existemValidacoes;
    elementos.validacoesCruzadas.innerHTML = validacoesCruzadas
      .map(
        (item, indice) => `
          <tr class="evidence-main-row ${classeValor("grupo", item.estado || item.status)}">
            <th scope="row">${escapeHtml(item.id || item.validacao_id)}</th>
            <td class="item-title">${escapeHtml(item.titulo || "")}</td>
            <td>${statusBadge(item.estado || item.status)}</td>
            <td>${statusBadge(item.criticidade || "-", "criticidade")}</td>
            <td>${escapeHtml((item.secoes_relacionadas || []).join(" / ") || "-")}</td>
          </tr>
          <tr class="detail-row evidence-detail-row ${classeValor("grupo", item.estado || item.status)}">
            <td colspan="5">
              <details class="item-details" id="detalhes-validacao-${indice}">
                <summary>Analisar justificativa, evidências e lacunas</summary>
                <table class="data-table nested-table">
                  <tbody>
                    <tr>
                      <th scope="row">Justificativa</th>
                      <td class="long-text">${escapeHtml(item.justificativa || "Sem justificativa registrada")}</td>
                    </tr>
                    <tr>
                      <th scope="row">Evidências</th>
                      <td class="long-text">${listaOuTexto(item.evidencias, "Sem evidências registradas")}</td>
                    </tr>
                    <tr>
                      <th scope="row">Lacunas</th>
                      <td class="long-text">${listaOuTexto(item.lacunas, "Sem lacunas registradas")}</td>
                    </tr>
                  </tbody>
                </table>
              </details>
            </td>
          </tr>
        `
      )
      .join("");
  }

  function renderizarUsoTokens() {
    const totais = usoTokens.totais || {};
    const escopos = usoTokens.totais_por_escopo || {};
    const existeUso = Number(usoTokens.total_execucoes_com_uso || 0) > 0;

    elementos.usoTokensVazio.hidden = existeUso;
    elementos.tabelaUsoTokensResumo.hidden = !existeUso;
    elementos.tabelaUsoTokensEscopos.hidden = !existeUso;

    if (!existeUso) {
      elementos.resumoUsoTokens.innerHTML = "";
      elementos.usoTokensEscopos.innerHTML = "";
      return;
    }

    elementos.resumoUsoTokens.innerHTML = `
      <tr>
        <th scope="row">Execuções contabilizadas</th>
        <td>${formatarNumero(usoTokens.total_execucoes_com_uso)}</td>
      </tr>
      <tr>
        <th scope="row">CLI</th>
        <td>${escapeHtml(formatarLista(usoTokens.clis))}</td>
      </tr>
      <tr>
        <th scope="row">Modelos usados</th>
        <td>${escapeHtml(formatarModelosPorCli(usoTokens.modelos_por_cli))}</td>
      </tr>
      <tr>
        <th scope="row">Tokens de entrada</th>
        <td>${formatarNumero(totais.input_tokens)}</td>
      </tr>
      <tr>
        <th scope="row">Cache de entrada</th>
        <td>${formatarNumero(totais.cached_input_tokens)}</td>
      </tr>
      <tr>
        <th scope="row">Tokens de saída</th>
        <td>${formatarNumero(totais.output_tokens)}</td>
      </tr>
      <tr>
        <th scope="row">Total de tokens</th>
        <td>${formatarNumero(totais.total_tokens)}</td>
      </tr>
    `;

    elementos.usoTokensEscopos.innerHTML = Object.entries(escopos)
      .map(
        ([escopo, valores]) => `
          <tr>
            <th scope="row">${escapeHtml(rotuloEscopo(escopo))}</th>
            <td>${formatarNumero(valores.input_tokens)}</td>
            <td>${formatarNumero(valores.cached_input_tokens)}</td>
            <td>${formatarNumero(valores.output_tokens)}</td>
            <td>${formatarNumero(valores.total_tokens)}</td>
          </tr>
        `
      )
      .join("");
  }

  [elementos.busca, elementos.estado, elementos.criticidade, elementos.secao, elementos.revisao, elementos.batch].forEach((elemento) => {
    elemento.addEventListener("input", renderizarItens);
    elemento.addEventListener("change", renderizarItens);
  });

  document.querySelectorAll("[data-quick-filter]").forEach((botao) => {
    botao.addEventListener("click", () => {
      elementos.estado.value = "";
      elementos.criticidade.value = "";
      elementos.secao.value = "";
      elementos.revisao.value = "";
      elementos.batch.value = "";
      elementos.busca.value = "";

      switch (botao.dataset.quickFilter) {
        case "bloq-nao-atende":
          elementos.estado.value = "NAO_ATENDE";
          elementos.criticidade.value = "BLOQ";
          break;
        case "obrig-nao-atende":
          elementos.estado.value = "NAO_ATENDE";
          elementos.criticidade.value = "OBRIG";
          break;
        case "inconclusivos":
          elementos.estado.value = "INCONCLUSIVO";
          break;
        case "revisao-humana":
          elementos.revisao.value = "true";
          break;
        default:
          break;
      }
      renderizarItens();
    });
  });

  renderizarPreValidacoes();
  renderizarCondicionais();
  renderizarValidacoesCruzadas();
  renderizarUsoTokens();
  renderizarItens();
})();
