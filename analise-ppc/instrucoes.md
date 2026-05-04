# Instruções da Skill Análise de PPC

## Resumo

Esta skill executa análise de PPC por sub-agentes dentro da conversa. Os scripts Python são deliberadamente pequenos: convertem o documento para `PPC.md`, montam grupos de fichas e renderizam o relatório HTML a partir do JSON coletado dos sub-agentes.

O output padrão fica em `analise-ppc/output/<rodada>/`. O relatório final fica em `relatorio-analise.html`; os artefatos de suporte ficam em `arquivos-suporte/`.

## Dependências

Instale as dependências Python a partir da raiz do projeto onde a skill está instalada:

```bash
python3 -m pip install -r .agents/skills/analise-ppc/requirements.txt
```

Se a instalação estiver em `.claude/skills`, substitua o prefixo do caminho.

## Fluxo recomendado

Use `.agents/skills/analise-ppc` nos exemplos abaixo. Se a skill estiver instalada em `.claude/skills`, troque apenas o prefixo.

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py preparar-documento caminho/PPC.docx
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py montar-grupos-subagents --rodada-dir .agents/skills/analise-ppc/output/<rodada>
```

Depois disso, o agente principal deve:

1. Ler `arquivos-suporte/PPC.md`.
2. Ler `arquivos-suporte/grupos-subagents.json`.
3. Ler `prompts/subagent-lote-fichas.md`.
4. Spawnar um sub-agente por grupo.
5. Passar a cada sub-agente o PPC completo, o prompt de trabalho, as fichas do grupo e os blocos de `contextos` do grupo.
6. Coletar as respostas em `arquivos-suporte/resultados-subagents.json`.
7. Fazer uma síntese transversal opcional usando `prompts/sintese-transversal.md`, o PPC completo, todos os resultados, `cnct_contexto` e `contexto_estrutural`; salvar o retorno em `alertas_transversais` dentro de `resultados-subagents.json`.
8. Gerar o relatório:

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py gerar-relatorio-html --rodada-dir .agents/skills/analise-ppc/output/<rodada> --resultados resultados-subagents.json
```

## Contrato de resultados

`resultados-subagents.json` deve conter:

```json
{
  "metadata": {
    "observacao": "opcional"
  },
  "grupos": [
    {
      "grupo_id": "grupo-001",
      "resultados": [
        {
          "ficha_id": "CT-IDENT-01",
          "estado": "ATENDE",
          "confianca": 0.9,
          "justificativa": "Decisão fundamentada no PPC.",
          "evidencias": ["Trecho ou referência textual do PPC"],
          "lacunas": [],
          "revisao_humana_obrigatoria": false
        }
      ]
    }
  ]
}
```

O renderizador valida campos obrigatórios, fichas duplicadas, fichas ausentes, fichas desconhecidas e quantidade mínima de evidências por ficha antes de gerar o HTML.

## Contexto CNCT

`montar-grupos-subagents` identifica a entrada provável do CNCT para o curso usando o catálogo interno em `base-analise/dados/cnct/catalogo_cnct.csv` e salva o resultado em:

```text
arquivos-suporte/cnct-contexto.json
```

O mesmo contexto aparece no topo de `grupos-subagents.json` como `cnct_contexto`. Grupos com fichas que mencionam CNCT ou `contexto_estrutural.cnct` recebem também `requer_contexto_cnct: true` e `contextos.cnct`. Passe esse bloco ao sub-agente junto com o PPC e as fichas do grupo.

## Contexto estrutural e anexos visuais

`montar-grupos-subagents` também salva:

```text
arquivos-suporte/contexto-estrutural-subagents.json
```

Esse bloco resume artefatos extraídos do DOCX, como identificação, matriz curricular, ementário e caminhos dos JSONs estruturados. Ele é incluído como `contextos.estrutura` em todos os grupos. Quando a representação gráfica do processo formativo é extraída e o grupo contém `CT-CURR-10`, o grupo recebe `contextos.anexos_visuais` com o caminho absoluto da imagem.

## Reavaliação avulsa

Para reavaliar fichas específicas sem refazer todos os grupos:

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py montar-grupo-avulso --rodada-dir .agents/skills/analise-ppc/output/<rodada> --ficha-id CT-IDENT-01
```

Spawnar um sub-agente com o grupo avulso retornado, salvar a resposta em `arquivos-suporte/resultado-avulso.json` e mesclar:

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py mesclar-resultados-avulsos --rodada-dir .agents/skills/analise-ppc/output/<rodada> --resultados-avulsos resultado-avulso.json
```

Depois, rode novamente `gerar-relatorio-html`.

## Entrega do relatório

Ao concluir `gerar-relatorio-html`, use o caminho `relatorio_html` ou a URL `relatorio_url` retornada pelo comando para avisar a pessoa:

```text
Relatório pronto: [abrir relatório](file:///.../relatorio-analise.html)
```

Não peça para a pessoa procurar o arquivo dentro dos artefatos.
