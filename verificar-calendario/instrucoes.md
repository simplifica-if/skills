# Instruções para Verificação de Calendário Acadêmico 2026

> Base normativa obrigatória: `https://raw.githubusercontent.com/simplifica-if/base-conhecimento/main/2025-11-27_RESOLUCAO_CONSUP-IFPR_259-2025_calendario-academico.md`

## Objetivo

Verificar calendários acadêmicos do IFPR em `xlsx` ou `pdf`, com foco em conformidade normativa, consistência documental e qualidade da evidência apresentada.

O resultado deve ser sempre um par de arquivos:

- relatório em Markdown;
- relatório em PDF retrato, gerado a partir do Markdown final.

Os dois artefatos devem ser suficientemente claros para subsidiar ajuste do calendário antes da aprovação.

## Princípio central para PDF

Quando a entrada for PDF, a leitura deve ser feita **pela imagem renderizada das páginas**. Não usar a extração embutida do PDF como fonte primária de verdade.

Fluxo esperado:

1. Renderizar as páginas em PNG.
2. Inspecionar visualmente cada página.
3. Se a página estiver densa, recortar por mês, tabela ou faixa.
4. Registrar no relatório quando algum trecho permanecer ilegível.

Se a evidência visual não for suficiente para cravar um item, usar `EVIDÊNCIA INSUFICIENTE`, nunca `OK` por inferência frágil.

## Formatos suportados

### 1. XLSX

Fluxo tradicional com:

- planilha principal com calendário mensal e dias letivos;
- planilha de incisos/eventos;
- validação cruzada entre as duas.

### 2. PDF principal do calendário

Padrão mais comum:

- páginas em retrato;
- grade mensal com cores;
- listas de eventos por mês;
- legenda;
- quadro de dias letivos.

Este PDF substitui, na prática, a leitura visual da planilha principal.

### 3. PDF complementar de eventos/incisos

Padrão mais comum:

- páginas em paisagem;
- tabela corrida de itens obrigatórios;
- colunas de item, descrição, datas previstas e observações.

Este PDF costuma cumprir o papel da antiga “planilha 2”, mas pode estar desatualizado. Nunca assumir equivalência sem conferir:

- número e ano da resolução;
- artigo citado;
- quantidade e redação dos itens;
- datas do ano correto.

## Nomes de arquivos de relatório

Salvar o relatório Markdown como:

```text
relatorio_verificacao_[CAMPUS]_[ANO]_[FONTE]_[AAAAMMDDHHMMSS].md
```

Salvar o PDF com o mesmo nome-base, trocando apenas a extensão:

```text
relatorio_verificacao_[CAMPUS]_[ANO]_[FONTE]_[AAAAMMDDHHMMSS].pdf
```

Exemplos:

```text
relatorio_verificacao_Centro_de_Referencia_Ponta_Grossa_2026_pdf_principal_20260401153000.md
relatorio_verificacao_Centro_de_Referencia_Ponta_Grossa_2026_pdf_eventos_20260401153000.md
relatorio_verificacao_Irati_2026_xlsx_20260401153000.md
relatorio_verificacao_Centro_de_Referencia_Ponta_Grossa_2026_pdf_principal_20260401153000.pdf
```

## Geração obrigatória do PDF

Depois de concluir e revisar o relatório em Markdown, gerar obrigatoriamente a versão em PDF com o script da própria skill:

```bash
python .agents/skills/verificar-calendario/scripts/render_relatorio_pdf.py caminho/relatorio.md caminho/relatorio.pdf
```

### Dependência

O script depende de `reportlab`. Se a biblioteca não estiver disponível no ambiente atual, criar um ambiente virtual local e instalar:

```bash
python3 -m venv tmp/.venv_pdf
tmp/.venv_pdf/bin/pip install -r .agents/skills/verificar-calendario/requirements.txt
tmp/.venv_pdf/bin/python .agents/skills/verificar-calendario/scripts/render_relatorio_pdf.py caminho/relatorio.md caminho/relatorio.pdf
```

### Critérios de qualidade do PDF

- orientação retrato (`A4`);
- tabela integralmente renderizada;
- cabeçalho da tabela repetido na virada de página;
- nenhuma linha da tabela cortada no rodapé;
- conclusão preservada após a tabela, sem sobreposição.

## Procedimento comum a qualquer formato

1. Ler a resolução em `https://raw.githubusercontent.com/simplifica-if/base-conhecimento/main/2025-11-27_RESOLUCAO_CONSUP-IFPR_259-2025_calendario-academico.md`.
2. Identificar no documento:
   - campus;
   - ano;
   - tipo de curso;
   - referência de aprovação;
   - resolução citada pelo próprio documento.
3. Confirmar se o documento está alinhado com a Resolução CONSUP/IFPR nº 259/2025.
4. Verificar se há sinais de material reaproveitado de outro ano:
   - menção a 2025 em calendário de 2026;
   - resolução antiga;
   - artigo/inciso antigo;
   - datas incompatíveis com o próprio cabeçalho.
5. Definir as fontes da validação:
   - fonte A: calendário mensal e quadro de dias letivos;
   - fonte B: tabela de itens/eventos, se existir.

## Fluxo para XLSX

### Estrutura esperada

#### Planilha principal

Contém:

- calendários mensais;
- detalhamento textual por mês;
- legenda de cores;
- quadro consolidado de dias letivos.

#### Planilha de incisos

Contém:

- relação dos incisos obrigatórios;
- datas e períodos previstos;
- eventuais observações.

### Regras de leitura

1. Ler cada seção mensal com contexto de mês.
2. Expandir intervalos:
   - `05 a 09` = 05, 06, 07, 08 e 09.
3. Contar períodos inclusivamente para férias e recessos.
4. Validar todos os intervalos de um inciso, não apenas o primeiro.
5. Se houver divergência entre planilha principal e planilha de incisos, reportar.

## Fluxo para PDF por visão

### Renderização

Preferencialmente usar `pdftoppm`.

Exemplo:

```bash
mkdir -p tmp/pdfs/meu-calendario
pdftoppm -r 170 -png caminho/para/arquivo.pdf tmp/pdfs/meu-calendario/pagina
```

Se a leitura ficar pequena:

- renderizar com resolução maior; ou
- recortar as imagens por faixa/mês.

### Estratégia de inspeção

#### PDF principal

Conferir visualmente:

- cabeçalho do calendário;
- mês a mês;
- listas de eventos;
- legenda;
- quadro “Dias Letivos”.

#### PDF complementar de eventos

Conferir visualmente:

- resolução citada no cabeçalho;
- artigo citado;
- correspondência com a resolução vigente;
- preenchimento das linhas obrigatórias;
- coerência do ano em todas as datas.

### Regra de ouro

No PDF, o agente deve priorizar o que está **legível na imagem**. Se um item não puder ser confirmado com segurança:

- marcar como `EVIDÊNCIA INSUFICIENTE`; e
- explicar o motivo.

## Eixos de validação

### 1. Dias letivos anuais

Verificar se o calendário prevê no mínimo 200 dias letivos anuais.

### 2. Dias letivos semestrais

Verificar se cada semestre atinge no mínimo 100 dias letivos.

Quando existir quadro consolidado, usá-lo como evidência visual. Se houver dúvida relevante, recortar o quadro e registrar os números observados.

### 3. Janela do ano letivo

Confirmar se:

- o ano letivo começa até 28 de fevereiro;
- está compreendido entre 4 de fevereiro e 18 de dezembro.

### 4. Datas obrigatórias do Art. 2º

Conferir a presença dos marcos obrigatórios da Resolução nº 259/2025, especialmente:

- 01/01;
- 02/01;
- 16, 17 e 18/02;
- 03/04;
- 20 e 21/04;
- 01/05;
- 04 e 05/06;
- 07/09;
- 12/10;
- 15/10, salvo remanejamento explícito;
- 28/10;
- 02/11;
- 15/11;
- 20/11;
- 24/12;
- 25/12;
- 31/12.

Se houver data adicional municipal, tratar como acréscimo local, não como substituição das datas obrigatórias.

### 5. Incisos obrigatórios do Art. 7º

Validar os 25 incisos da resolução vigente.

Requisitos críticos:

- Inciso IV: férias docentes com mínimo de 45 dias.
- Inciso XX: fase local da OBR até 31/08.
- Inciso XXI: Mostra de Cursos até 30/09.
- Inciso XXII: formação pedagógica com mínimo de 40 horas anuais.
- Inciso XXIII: planejamento/replanejamento com mínimo de 20 horas anuais.
- Inciso XXIV: evento alusivo à Semana de Valorização de Mulheres em março.
- Inciso XXV: Semana Cultural Interescolar em outubro.

### 6. Consistência entre documentos

Se houver mais de um arquivo para o mesmo calendário, validar:

- coerência entre datas do calendário principal e da tabela de eventos;
- coerência entre resolução citada e resolução vigente;
- coerência do ano civil;
- coerência dos artigos e incisos citados.

Regra adicional:

- se o documento complementar adotar outra resolução, outra quantidade de itens ou outra redação normativa, ele **não pode** ser aceito como substituto automático da tabela correspondente ao Art. 7º da Resolução nº 259/2025, ainda que contenha algumas datas úteis.

## Tipos de inconsistência a reportar

- **Tipo A:** item aparece na tabela de incisos/eventos, mas não aparece no calendário principal.
- **Tipo B:** item aparece no calendário principal, mas não aparece na tabela de incisos/eventos.
- **Tipo C:** as duas fontes tratam o mesmo item com datas diferentes.
- **Tipo D:** documento complementar cita resolução, artigo ou ano incompatível com a base normativa vigente.
- **Tipo E:** evidência quantitativa insuficiente para horas mínimas, apesar de haver datas.

## Armadilhas recorrentes

1. PDF complementar herdado de ano anterior.
2. Cabeçalho com resolução antiga, mesmo quando o calendário mensal já foi atualizado.
3. Linha preenchida com ano incorreto, como `07/03/2025` em material de 2026.
4. Tabela com número de itens diferente do Art. 7º vigente.
5. Inferir horas mínimas de formação ou planejamento sem indicação explícita de carga horária.
6. Considerar item atendido apenas porque há uma linha ou um rótulo correspondente, sem conferir se o campo está efetivamente preenchido, no ano correto e compatível com a exigência normativa.

## Como julgar formação pedagógica e planejamento

Não presumir automaticamente a carga horária apenas pelo intervalo de datas.

Use:

- `ATENDE`, quando houver horas explícitas ou evidência institucional inequívoca;
- `ATENDE COM RESSALVAS`, quando o conjunto sugere atendimento, mas a carga horária não está claramente declarada;
- `NÃO ATENDE`, quando a evidência aponta insuficiência;
- `EVIDÊNCIA INSUFICIENTE`, quando não for possível confirmar.

## Estrutura obrigatória do relatório

```markdown
# Relatório de Verificação do Calendário Acadêmico [ANO]
## [Campus] - [Tipo/Fonte]

**Documento analisado:** [nome-do-arquivo]
**Formato:** [xlsx|pdf principal|pdf eventos]
**Método de leitura:** [estrutura do arquivo | análise visual das páginas renderizadas]
**Base normativa:** Resolução CONSUP/IFPR nº 259/2025
**Data da análise:** [DD/MM/AAAA]

| Item | Status | Observação/Evidência |
|:---|:---:|:---|
| Prevê, no mínimo, 200 (duzentos) dias letivos anuais, para cumprimento da carga horária estabelecida no projeto pedagógico de cada curso. | [STATUS] | [Informar o total encontrado e a evidência visual ou estrutural usada.] |
| Prevê o cumprimento de 100 (cem) dias letivos semestrais para os campi que possuem cursos em regime de oferta semestral. | [STATUS] | [Informar os totais por semestre e a evidência.] |
| Cumpre as atividades acadêmicas e administrativas do art. 2º da Resolução Consup/IFPR nº 259, de 27 de novembro de 2025 | [STATUS] | [Listar as datas confirmadas, ausentes, divergentes ou inconclusivas.] |
| O ano letivo de 2026 deverá estar compreendido entre 4 de fevereiro e 18 de dezembro, devendo iniciar suas atividades até 28 de fevereiro. | [STATUS] | [Informar a data de início, a data de término e a evidência.] |
| I - o início e o término de cada período letivo (bimestre/ trimestre, semestre, ano); | [STATUS] | [Informar as datas ou explicar a ausência delas.] |
| II - os dias de feriados e os recessos acadêmicos e administrativos; | [STATUS] | [Listar os feriados e recessos identificados, ou as ausências.] |
| III - os períodos de férias escolares; | [STATUS] | [Informar os períodos de férias escolares encontrados.] |
| IV - os períodos de férias docentes, garantindo 45 (quarenta e cinco) dias previstos em lei, preferencialmente coincidentes com as férias escolares; | [STATUS] | [Informar os períodos, a soma dos dias e a coincidência ou não com as férias escolares.] |
| V - os períodos destinados à matrícula e ao ajuste de matrícula dos estudantes veteranos dos cursos subsequentes e de graduação; | [STATUS] | [Informar os períodos de matrícula e de ajuste, ou apontar o que faltou.] |
| VI - os períodos destinados para solicitação de aproveitamento de estudos, certificação de conhecimentos anteriores e equivalência de estágio, no mínimo uma vez ao ano para os cursos em regime anual, e duas vezes ao ano para os cursos em regime semestral; | [STATUS] | [Informar os períodos encontrados e a aderência ao regime do curso.] |
| VII - os períodos destinados para solicitação de trancamento de curso e de cancelamento de matrícula de componente curricular para os cursos subsequentes e de graduação; | [STATUS] | [Informar os períodos ou a insuficiência de evidência.] |
| VIII - as datas de publicação dos editais de ingresso por transferência interna e externa, para reingresso e para portadores de diploma, uma vez ao ano para os cursos em regime anual, e duas vezes ao ano para os cursos em regime semestral, devendo ser definida antes do início do período letivo; | [STATUS] | [Informar as datas encontradas e verificar a antecedência.] |
| IX - o prazo para os docentes lançarem resultados (rendimento e frequência) de cada etapa no sistema acadêmico; | [STATUS] | [Informar os prazos ou explicar por que não foi possível confirmá-los.] |
| X - o prazo de lançamento, pelos docentes, do resultado final (rendimento e frequência) no sistema acadêmico; | [STATUS] | [Informar o prazo final encontrado.] |
| XI - as datas para fechamento e entrega dos diários de classe no sistema acadêmico; | [STATUS] | [Informar as datas encontradas.] |
| XII - os prazos para submissão do Plano Individual de Trabalho (PIT) e do Plano de Ensino à Direção de Ensino, Pesquisa e Extensão, ou correlato, pelos docentes; | [STATUS] | [Informar os prazos de PIT e Plano de Ensino.] |
| XIII - as datas destinadas aos conselhos de classe/coletivos pedagógicos e reuniões pedagógicas, após resultados parciais; | [STATUS] | [Informar as datas e a relação com os resultados parciais.] |
| XIV - o prazo para a solicitação de revisão de resultados finais pelos estudantes; | [STATUS] | [Informar o prazo encontrado.] |
| XV - as datas destinadas aos conselhos de classe/coletivos pedagógicos extraordinários para análise das solicitações de revisão dos resultados dos conselhos de classe mencionados no inciso XIV; | [STATUS] | [Informar as datas ou apontar ausência.] |
| XVI - as datas destinadas a reuniões com familiares/responsáveis/comunidade; | [STATUS] | [Informar as datas e o público indicado.] |
| XVII - os eventos de ensino, pesquisa, extensão e inovação a serem realizados no campus; | [STATUS] | [Informar os eventos e suas datas.] |
| XVIII - data de encontro dos egressos; | [STATUS] | [Informar a data identificada.] |
| XIX - data de evento sobre a temática de estágios; | [STATUS] | [Informar a data identificada ou a ausência dela.] |
| XX - a data da fase local da Olimpíada Brasileira de Robótica no campus, até 31 de agosto de 2026; | [STATUS] | [Informar a data e verificar se está até 31/08/2026.] |
| XXI - os dias destinados à Mostra de Cursos do campus, até 30 de setembro de 2026. | [STATUS] | [Informar a data ou os dias e verificar se estão até 30/09/2026.] |
| XXII - dias destinados à formação pedagógica que perfazem, no mínimo, 40 horas anuais; | [STATUS] | [Informar datas, carga horária explícita ou a razão da ressalva.] |
| XXIII - os dias destinados aos encontros de planejamento/replanejamento coletivo, perfazendo, no mínimo, 20 horas anuais; | [STATUS] | [Informar datas, carga horária explícita ou a razão da ressalva.] |
| XXIV - o evento alusivo à Semana de Valoriação de Mulheres que Fizeram História, que deverá ser realizada em março (obrigatória nos calendários dos cursos técnicos e facultativa nos cursos de graduação) | [STATUS] | [Informar o evento, a data e se o curso é técnico ou graduação.] |
| XXV - o evento alusivo à Semana Cultural Interescolar, que deverá ser realizada em outubro, aberta à participação de estudantes, famílias e comunidade (obrigatória nos calendários dos cursos técnicos e facultativa nos cursos de graduação). | [STATUS] | [Informar o evento, a data e o público-alvo indicado.] |
```

## Regras de preenchimento da tabela

1. A tabela acima é obrigatória e deve aparecer no relatório exatamente nessa ordem.
2. A coluna `Item` deve reproduzir integralmente os textos acima.
3. A coluna `Status` deve usar apenas:
   - `ATENDE`
   - `NÃO ATENDE`
   - `ATENDE COM RESSALVAS`
   - `EVIDÊNCIA INSUFICIENTE`
4. A coluna `Observação/Evidência` nunca pode ficar vazia.
5. Mesmo quando o item `ATENDE`, a observação deve registrar a evidência concreta, por exemplo:
   - datas;
   - intervalos;
   - total de dias;
   - carga horária;
   - menção textual encontrada no documento;
   - comparação entre documentos.
6. Nunca marcar item como `ATENDE` apenas porque existe um título, uma linha na tabela ou um campo reservado. É obrigatório verificar se o conteúdo está preenchido, no ano correto e aderente à exigência normativa.
7. Quando o item `NÃO ATENDE`, a observação deve explicar objetivamente o motivo e apontar a ausência, divergência ou insuficiência.
8. Quando o item for `ATENDE COM RESSALVAS`, a observação deve separar o que foi encontrado do que permaneceu incompleto.
9. Quando o item for `EVIDÊNCIA INSUFICIENTE`, a observação deve dizer por que a comprovação não pôde ser feita, por exemplo:
   - imagem ilegível;
   - campo em branco;
   - documento complementar desatualizado;
   - falta de carga horária explícita.

## Critério final de julgamento

Ao concluir, responder às quatro perguntas abaixo:

1. O calendário está alinhado com a Resolução nº 259/2025?
2. As datas do ano letivo e os dias letivos atendem aos mínimos?
3. Os 25 incisos obrigatórios aparecem com evidência suficiente?
4. Existe coerência entre todos os documentos apresentados?

Se qualquer uma dessas respostas for “não”, isso deve ficar refletido nos status da tabela e nas respectivas observações/evidências.
