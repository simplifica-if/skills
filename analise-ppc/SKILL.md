---
name: analise-ppc
description: Analisar Projetos Pedagógicos de Curso técnico do IFPR em Word DOCX, preparando rodadas, gerando lotes de fichas, executando avaliações por IA, validações cruzadas, consolidação, uso de tokens e relatório HTML final. Use quando o usuário solicitar análise de PPC, revisão de PPC, conformidade de Projeto Pedagógico de Curso, matriz curricular, ementário, CNCT ou parecer técnico-pedagógico sobre PPC.
allowed-tools: Read, Write, Glob, Grep, Bash
argument-hint: [caminho-do-PPC.docx|ajuda]
---

# Análise de PPC

Skill autocontida para analisar PPCs de cursos técnicos do IFPR em Word (`.docx`). A skill contém scripts Python, fichas de análise, validações cruzadas, política de parecer, templates de relatório e o catálogo CNCT em `base-analise/dados/cnct/catalogo_cnct.csv`.

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
2. Gerar os batches a partir das fichas canônicas.
3. Avaliar todos os lotes.
4. Avaliar validações cruzadas.
5. Contabilizar tokens.
6. Consolidar resultados.
7. Gerar o relatório HTML.

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
