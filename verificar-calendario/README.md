# Verificar Calendário

Esta skill verifica calendários acadêmicos do IFPR, com foco na conformidade com a Resolução CONSUP/IFPR nº 259/2025, e gera relatório em Markdown e PDF.

## Formatos aceitos

A skill aceita calendários nos seguintes formatos:

- `.xlsx`
- `.pdf`

Use `.xlsx` quando houver planilha estruturada do calendário. Use `.pdf` quando o calendário estiver publicado ou recebido como documento visual.

## Como pedir para a IA usar a skill

Depois de instalar a skill no projeto, peça ao agente algo neste formato:

```text
Use a skill verificar-calendario para verificar o calendário em /caminho/para/calendario.xlsx
```

Ou, para PDF:

```text
Use a skill verificar-calendario para verificar o calendário em /caminho/para/calendario.pdf
```

Se houver dois arquivos complementares, como calendário principal e tabela de eventos/incisos, informe os dois caminhos:

```text
Use a skill verificar-calendario para verificar o calendário principal em /caminho/calendario.pdf e a tabela de eventos em /caminho/eventos.pdf
```

## O que a skill verifica

A análise confere, entre outros pontos:

- mínimo de 200 dias letivos anuais;
- mínimo de 100 dias letivos semestrais, quando aplicável;
- janela do ano letivo de 2026;
- datas obrigatórias do Art. 2º da Resolução CONSUP/IFPR nº 259/2025;
- 25 incisos obrigatórios do Art. 7º;
- coerência entre calendário principal e documentos complementares;
- sinais de documento reaproveitado de outro ano ou com resolução antiga.

## Saídas esperadas

Ao final, a IA deve entregar dois arquivos:

- relatório em Markdown (`.md`);
- relatório em PDF (`.pdf`) gerado a partir do Markdown.

O nome recomendado é:

```text
relatorio_verificacao_[CAMPUS]_[ANO]_[FONTE]_[AAAAMMDDHHMMSS].md
relatorio_verificacao_[CAMPUS]_[ANO]_[FONTE]_[AAAAMMDDHHMMSS].pdf
```

Exemplo:

```text
relatorio_verificacao_Irati_2026_xlsx_20260401153000.md
relatorio_verificacao_Irati_2026_xlsx_20260401153000.pdf
```

