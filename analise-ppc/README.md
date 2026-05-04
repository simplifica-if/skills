# Análise de PPC

Esta skill analisa Projetos Pedagógicos de Curso técnico do IFPR a partir de um arquivo Word (`.docx`) ou Markdown (`.md`). A IA roda por sub-agentes na conversa atual; os scripts Python preparam o `PPC.md`, organizam as fichas e geram o relatório HTML final.

## Formato aceito

Forneça o PPC em Word ou Markdown:

- Aceito: `.docx`
- Aceito: `.md`
- Não aceito diretamente: `.pdf`

Se o PPC estiver em PDF, converta ou solicite a versão original em Word antes de iniciar a análise.

## Como pedir para a IA usar a skill

Depois de instalar a skill no projeto, peça ao agente algo neste formato:

```text
Use a skill analise-ppc para analisar o PPC em /caminho/para/PPC.docx
```

Ou, se estiver usando um caminho relativo ao projeto:

```text
Use a skill analise-ppc para analisar o PPC em documentos/PPC_Curso_Tecnico.docx
```

Ao final, a IA deve informar um link para abrir o relatório:

```text
Relatório pronto: [abrir relatório](file:///.../relatorio-analise.html)
```

## Onde ficam os resultados

Cada análise cria uma rodada em:

```text
analise-ppc/output/<rodada>/
```

Dentro da rodada:

- `relatorio-analise.html` é o relatório final que deve ser aberto.
- `arquivos-suporte/` guarda os arquivos usados para produzir o relatório.

O relatório HTML é autocontido: a pessoa só precisa abrir `relatorio-analise.html` para verificar o resultado.

## Fluxo técnico

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py preparar-documento caminho/PPC.docx
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py montar-grupos-subagents --rodada-dir .agents/skills/analise-ppc/output/<rodada>
```

Depois, o agente principal spawna um sub-agente por grupo em `arquivos-suporte/grupos-subagents.json`. Passe também os blocos `contextos` de cada grupo, incluindo `contextos.cnct`, `contextos.estrutura` e eventuais `contextos.anexos_visuais`. Em seguida, colete as respostas em `arquivos-suporte/resultados-subagents.json`, opcionalmente rode a síntese transversal com `prompts/sintese-transversal.md`, e gere o relatório:

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py gerar-relatorio-html --rodada-dir .agents/skills/analise-ppc/output/<rodada> --resultados resultados-subagents.json
```

Para reavaliar fichas específicas, use `montar-grupo-avulso`, execute um sub-agente com o grupo retornado e depois `mesclar-resultados-avulsos`.
