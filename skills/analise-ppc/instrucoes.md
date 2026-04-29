# Instruções da Skill Análise de PPC

## Resumo

Esta skill executa análise IA-first de PPCs de cursos técnicos do IFPR. Ela trabalha com `PPC.md` completo em cada lote, fichas JSON, validações cruzadas, consolidação determinística e relatório HTML estático em página única.

## Dependências

Instale as dependências Python a partir da raiz do projeto onde a skill está instalada:

```bash
python3 -m pip install -r .agents/skills/analise-ppc/requirements.txt
```

Se a instalação estiver em `.claude/skills`, substitua o prefixo do caminho.

`docx2pdf`, `pdf2image` e `pdfplumber` são opcionais para renderização da representação gráfica. A conversão principal para `PPC.md` não deve falhar se essas dependências opcionais não estiverem disponíveis.

## Fluxo recomendado

Use `.agents/skills/analise-ppc` nos exemplos abaixo. Se a skill estiver instalada em `.claude/skills`, troque apenas o prefixo.

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py preparar-documento caminho/PPC.docx
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py gerar-batches --rodada-dir .agents/skills/analise-ppc/output/<rodada>
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py avaliar-todos --rodada-dir .agents/skills/analise-ppc/output/<rodada>
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py avaliar-cruzadas --rodada-dir .agents/skills/analise-ppc/output/<rodada>
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py contabilizar-tokens --rodada-dir .agents/skills/analise-ppc/output/<rodada>
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py consolidar --rodada-dir .agents/skills/analise-ppc/output/<rodada>
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py gerar-relatorio-html --rodada-dir .agents/skills/analise-ppc/output/<rodada>
```

## Subcomandos

- `preparar-documento`: cria a rodada, converte DOCX quando necessário e gera `PPC.md`, `PPC-bruto.md` e artefatos estruturais.
- `gerar-batches`: gera lotes estáveis a partir de `base-analise/fichas/`.
- `pre-validar`: gera pré-validações determinísticas e contexto estrutural.
- `avaliar-lote`: avalia um lote específico.
- `avaliar-todos`: avalia todos os lotes pendentes ou os lotes indicados por `--batch-id`.
- `avaliar-cruzadas`: executa validações transversais de coerência.
- `reavaliar`: reexecuta fichas ou validações específicas por ID.
- `contabilizar-tokens`: consolida metadados reais de uso das CLIs.
- `consolidar`: consolida achados, resultados e parecer final.
- `gerar-relatorio-html`: gera o relatório final em HTML.

## Estrutura útil

- `base-analise/fichas/`: catálogo canônico de fichas por lote.
- `base-analise/validacoes-cruzadas/`: validações transversais.
- `base-analise/dados/cnct/catalogo_cnct.csv`: catálogo CNCT empacotado com a skill.
- `config/politica_parecer.json`: política interna de situação final.
- `prompts/`: prompts usados nas avaliações por IA.
- `templates/`: HTML, CSS e JavaScript do relatório.
- `output/`: rodadas criadas em tempo de execução.

## Observações operacionais

- A preparação de `DOCX` é autocontida e gera `PPC.md`, `PPC-bruto.md` e `artefatos-conversao/`.
- A comparação com CNCT usa o CSV interno da skill em `base-analise/dados/cnct/catalogo_cnct.csv`
- Quando a representação gráfica é extraída como imagem, o lote que contém a ficha `CT-CURR-10` recebe esse arquivo como anexo visual no provider `codex` (`codex exec --image`).
- Providers sem suporte a anexos visuais neste fluxo não devem ser usados para fechar `CT-CURR-10` por análise visual.
- Para regenerar `base-analise/indice.json`, execute `python3 -B .agents/skills/analise-ppc/scripts/gerar_indice_base_analise.py`.
