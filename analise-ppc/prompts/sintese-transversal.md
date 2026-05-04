# Síntese Transversal da Análise de PPC

Você fará uma revisão transversal depois que todos os sub-agentes concluírem seus grupos de fichas.

## Entrada que você receberá

1. O `PPC.md` completo.
2. O `resultados-subagents.json` coletado dos grupos.
3. O `cnct_contexto`, quando disponível.
4. O `contexto_estrutural`, quando disponível.

## Tarefa

Procure inconsistências que só aparecem ao comparar respostas de fichas diferentes, como divergências entre identificação, perfil do egresso, matriz, ementário, carga horária, AEE, estágio, infraestrutura e CNCT.

Não reescreva as respostas das fichas. Registre apenas alertas transversais úteis para a revisão humana.

## Saída obrigatória

Retorne somente JSON válido:

```json
{
  "alertas_transversais": [
    {
      "id": "ALERTA-001",
      "titulo": "Título curto",
      "criticidade": "BLOQ | OBRIG | REC",
      "descricao": "Descrição objetiva do problema transversal.",
      "fichas_relacionadas": ["CT-IDENT-01"],
      "evidencias": ["Trecho ou referência textual"],
      "revisao_humana_obrigatoria": true
    }
  ]
}
```

Se não houver alerta transversal relevante, retorne `{"alertas_transversais": []}`.
