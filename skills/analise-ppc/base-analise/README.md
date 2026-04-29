## Resumo

Centro canônico da base de análise do `analise-ppc`. Reúne, em um único lugar, as fontes estruturadas que orientam a leitura do PPC.

## Estrutura

- `fichas/` — verificações analíticas executadas por lote sobre o PPC completo.
- `validacoes-cruzadas/` — verificações transversais de coerência entre seções e achados.
- `contratos/` — exemplos mínimos de payload e formatos de referência.
- `dados/cnct/catalogo_cnct.csv` — catálogo CNCT empacotado com a skill.
- `indice.json` — índice consolidado da base de análise, gerado a partir dos JSONs reais.

## Uso recomendado

1. Consulte `indice.json` quando quiser localizar rapidamente itens por ID, categoria, domínio, criticidade ou seção.
2. Abra `fichas/` quando a pergunta for sobre cobertura analítica por item.
3. Abra `validacoes-cruzadas/` quando a pergunta for sobre coerência transversal.
4. Abra `contratos/` quando a dúvida for sobre formato de entrada ou saída.

## Manutenção

- Para regenerar o índice consolidado:

```bash
python3 -B scripts/gerar_indice_base_analise.py
```
