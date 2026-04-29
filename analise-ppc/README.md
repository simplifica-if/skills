# Análise de PPC

Esta skill analisa Projetos Pedagógicos de Curso técnico do IFPR a partir de um arquivo Word (`.docx`) e gera um relatório HTML final.

## Formato aceito

No momento, para uso humano da skill, forneça somente PPC em formato Word:

- Aceito: `.docx`
- Não aceito: `.pdf`

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

