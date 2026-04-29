# Paleta de Cores IFPR - Referência Detalhada

## Cores Primárias

### Verde IFPR (Principal)
- **Hexadecimal**: #1F8A42
- **RGB**: rgb(31, 138, 66)
- **HSL**: hsl(135, 47%, 38%)
- **Pantone**: 7738 C (aproximado)
- **Uso**: Fundo de slides, headers, elementos principais
- **Contraste**: 4.4:1 com branco (AA apenas para texto grande 18pt+/14pt bold)

### Vermelho IFPR (Destaque)
- **Hexadecimal**: #C72E2E
- **RGB**: rgb(199, 46, 46)
- **HSL**: hsl(0, 62%, 48%)
- **Pantone**: 200 C (aproximado)
- **Uso**: Alertas, destaques, chamadas à ação
- **Contraste**: 5.4:1 com branco (AA)

### Cinza Escuro (Texto)
- **Hexadecimal**: #2D2D2D
- **RGB**: rgb(45, 45, 45)
- **HSL**: hsl(0, 0%, 18%)
- **Uso**: Texto principal, corpo de conteúdo
- **Contraste**: 13.8:1 com branco (AAA)

### Branco
- **Hexadecimal**: #FFFFFF
- **Uso**: Texto sobre fundos verdes, fundos de cards

## Tons Complementares

### Verdes
- **Verde Escuro**: #1B5E20 - Gradientes, hover states, elementos profundos
- **Verde Médio**: #4CAF50 - Elementos secundários, decorações
- **Verde Claro**: #81C784 - Fundos de destaques leves
- **Verde Muito Claro**: #E8F5E9 - Fundos de cards, áreas destacadas

### Vermelhos
- **Vermelho Claro**: #EF5350 - Alertas menos críticos, hover states
- **Vermelho Muito Claro**: #FFEBEE - Fundos de alertas suaves

### Cinzas
- **Cinza Médio**: #757575 - Texto secundário, labels
- **Cinza Claro**: #BDBDBD - Borders, divisores
- **Cinza Muito Claro**: #F5F5F5 - Fundos secundários, rodapés

## Cores Semânticas

- **Sucesso**: #1F8A42 (Verde IFPR) sobre fundo #E8F5E9
- **Alerta**: #FFA726 sobre fundo #FFF3E0
- **Erro**: #C72E2E (Vermelho IFPR) sobre fundo #FFEBEE
- **Informação**: #0288D1 sobre fundo #E1F5FE

## Paleta para Gráficos e Dados

Sequência recomendada para múltiplas séries:
1. #1F8A42 (Verde IFPR - primário)
2. #1B5E20 (Verde escuro)
3. #4CAF50 (Verde médio)
4. #81C784 (Verde claro)
5. #C72E2E (Vermelho IFPR - alertas)
6. #2D2D2D (Cinza escuro - contexto)

## Gradientes Recomendados

### Gradiente Principal (slides título)
```css
linear-gradient(135deg, #1F8A42 0%, #1B5E20 100%)
```

### Gradiente Verde Suave
```css
linear-gradient(135deg, #E8F5E9 0%, #FFFFFF 100%)
```

### Gradiente Profundo (fundos)
```css
linear-gradient(to right, #1B5E20 0%, #1F8A42 50%, #4CAF50 100%)
```

## Variáveis CSS

```css
:root {
  /* Cores Primárias */
  --ifpr-verde: #1F8A42;
  --ifpr-vermelho: #C72E2E;
  --ifpr-cinza-escuro: #2D2D2D;
  --ifpr-branco: #FFFFFF;

  /* Tons de Verde */
  --ifpr-verde-escuro: #1B5E20;
  --ifpr-verde-medio: #4CAF50;
  --ifpr-verde-claro: #81C784;
  --ifpr-verde-muito-claro: #E8F5E9;

  /* Tons de Vermelho */
  --ifpr-vermelho-claro: #EF5350;
  --ifpr-vermelho-muito-claro: #FFEBEE;

  /* Tons de Cinza */
  --ifpr-cinza-medio: #757575;
  --ifpr-cinza-claro: #BDBDBD;
  --ifpr-cinza-muito-claro: #F5F5F5;
}
```

## Contrastes WCAG

| Combinação | Ratio | Nível | Nota |
|---|---|---|---|
| Verde #1F8A42 sobre branco | 4.4:1 | AA large | Apenas texto 18pt+ ou 14pt bold |
| Branco sobre verde #1F8A42 | 4.4:1 | AA large | Apenas texto 18pt+ ou 14pt bold |
| Vermelho #C72E2E sobre branco | 5.4:1 | AA | Texto normal OK |
| Cinza escuro #2D2D2D sobre branco | 13.8:1 | AAA | Excelente para qualquer texto |
| Cinza médio #757575 sobre branco | 4.6:1 | AA | Texto normal OK, margem estreita |

Para texto normal em cor sobre fundo branco, prefira #2D2D2D (cinza escuro). O verde #1F8A42 funciona melhor como cor de fundo com texto branco em tamanhos grandes (títulos, headers).
