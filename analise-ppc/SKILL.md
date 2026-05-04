---
name: analise-ppc
description: Analisar Projetos Pedagógicos de Curso técnico do IFPR em Word DOCX ou Markdown, preparando o PPC.md, coordenando sub-agentes na conversa com fichas canônicas e gerando relatório HTML determinístico. Use quando o usuário solicitar análise de PPC, revisão de PPC, conformidade de Projeto Pedagógico de Curso, matriz curricular, ementário, CNCT ou parecer técnico-pedagógico sobre PPC.
allowed-tools: Read, Write, Glob, Grep, Bash
argument-hint: [caminho-do-PPC.docx|ajuda]
---

# Análise de PPC

Skill autocontida para analisar PPCs de cursos técnicos do IFPR em Word (`.docx`) ou Markdown (`.md`). A execução de IA ocorre apenas por sub-agentes na conversa atual. Os scripts Python fazem somente a preparação do documento, a organização dos grupos de fichas e a geração determinística do relatório HTML.

## Uso rápido

Para orientação de uso por uma pessoa, leia também:

```text
Read .agents/skills/analise-ppc/README.md
```

Antes de executar uma análise, leia as instruções completas:

```text
Read .agents/skills/analise-ppc/instrucoes.md
```

Se a skill estiver instalada em `.claude/skills`, use o caminho equivalente:

```text
Read .claude/skills/analise-ppc/instrucoes.md
```

## Fluxo principal

1. Preparar o documento para criar a rodada e o `PPC.md`.
2. Montar os grupos de fichas canônicas para sub-agentes, incluindo contexto CNCT, contexto estrutural e anexos visuais quando disponíveis.
3. Spawnar um sub-agente por grupo na conversa atual.
4. Coletar as respostas em `arquivos-suporte/resultados-subagents.json`.
5. Opcionalmente executar síntese transversal por sub-agente.
6. Gerar o relatório HTML determinístico com busca/filtros.

Ao final, informe explicitamente o link de abertura do relatório retornado pelo comando. O relatório final fica em `output/<rodada>/relatorio-analise.html` e os arquivos de suporte da rodada ficam em `output/<rodada>/arquivos-suporte/`.

## Ponto de entrada

Execute os comandos a partir da raiz do projeto onde a skill está instalada:

```bash
python3 -B .agents/skills/analise-ppc/scripts/analise_ppc.py --help
```

Ou, se instalada para Claude:

```bash
python3 -B .claude/skills/analise-ppc/scripts/analise_ppc.py --help
```
