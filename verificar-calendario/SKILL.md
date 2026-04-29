---
name: verificar-calendario
description: Verificar calendário acadêmico 2026 do IFPR em XLSX ou PDF por análise visual, conforme a Resolução CONSUP/IFPR nº 259/2025
allowed-tools: Read, Write, Glob, Grep, Bash
argument-hint: [caminho-do-arquivo.xlsx|caminho-do-arquivo.pdf]
---

# Verificar Calendário Acadêmico 2026

Analisa calendários acadêmicos do IFPR em formato `xlsx` ou `pdf` e gera relatório de conformidade com a Resolução CONSUP/IFPR nº 259, de 27 de novembro de 2025, sempre com saída em `Markdown` e `PDF`.

## Uso

```text
/verificar-calendario caminho/para/calendario.xlsx
/verificar-calendario caminho/para/calendario.pdf
```

## O que faz

1. Confirma a base normativa na base pública de legislação: `https://raw.githubusercontent.com/simplifica-if/base-conhecimento/main/2025-11-27_RESOLUCAO_CONSUP-IFPR_259-2025_calendario-academico.md`.
2. Identifica o formato de entrada e escolhe o fluxo correto:
   - `xlsx`: leitura estrutural das planilhas.
   - `pdf`: renderização das páginas em imagem e inspeção visual.
3. Verifica os 25 incisos obrigatórios do Art. 7º.
4. Valida os 20 marcos obrigatórios do Art. 2º.
5. Confere dias letivos anuais e semestrais.
6. Detecta inconsistências entre documentos complementares, como:
   - calendário principal x tabela de eventos;
   - resolução citada no documento x resolução vigente;
   - datas do ano corrente x sobras de anos anteriores.
7. Gera relatório em Markdown no formato de **tabela única**, com as colunas `Item`, `Status` e `Observação/Evidência`.
8. Converte o relatório Markdown em PDF em orientação retrato, preservando a tabela completa com cabeçalho repetido e sem quebrar linhas no fim da página.
9. Exige evidência textual mesmo quando o item atende, por exemplo:
   - datas;
   - períodos;
   - contagens de dias;
   - trechos observados no documento;
   - justificativa da insuficiência ou da não conformidade.
10. Usa os seguintes status por item:
   - `ATENDE`
   - `NÃO ATENDE`
   - `ATENDE COM RESSALVAS`
   - `EVIDÊNCIA INSUFICIENTE`

## Regras importantes para PDF

- Em PDF, a fonte primária deve ser a **análise visual das páginas renderizadas**, e não a extração bruta do arquivo.
- Se a página estiver densa, recortar por mês, bloco ou faixa antes de concluir a leitura.
- Se existirem dois PDFs complementares, tratá-los como fontes distintas e fazer validação cruzada entre eles.

## Instruções completas

Antes de executar, leia:

```text
Read .agents/skills/verificar-calendario/instrucoes.md
```

Para gerar o PDF a partir do Markdown final, usar:

```text
python .agents/skills/verificar-calendario/scripts/render_relatorio_pdf.py caminho/relatorio.md caminho/relatorio.pdf
```
