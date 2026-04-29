# Tipografia IFPR - Referência Detalhada

## Fonte Institucional: Open Sans

- **Fonte oficial**: Open Sans (Steve Matteson / Google Fonts)
- **Disponibilidade**: Livre para uso
- **Formatos**: TTF, OTF, WOFF, WOFF2
- **Famílias**: Light (300), Regular (400), Semibold (600), Bold (700)
- **Download**: https://fonts.google.com/specimen/Open+Sans

## Hierarquia Tipográfica

### H1 - Títulos Principais
```css
font-size: 48px;
font-weight: 700; /* Bold */
letter-spacing: -0.5px;
line-height: 1.2;
color: #1F8A42 ou #2D2D2D;
```
**Uso**: Títulos de apresentações, títulos de página, cabeçalhos principais

### H2 - Títulos Secundários
```css
font-size: 36px;
font-weight: 600; /* Semibold */
letter-spacing: -0.3px;
line-height: 1.3;
color: #1F8A42 ou #2D2D2D;
```
**Uso**: Títulos de seções, subtítulos em slides

### H3 - Títulos Terciários
```css
font-size: 24px;
font-weight: 600; /* Semibold */
letter-spacing: 0px;
line-height: 1.4;
color: #1F8A42 ou #2D2D2D;
```
**Uso**: Subtítulos, títulos de cards, labels importantes

### Corpo de Texto
```css
font-size: 16px;
font-weight: 400; /* Regular */
letter-spacing: 0px;
line-height: 1.6;
color: #2D2D2D;
margin-bottom: 16px;
```
**Uso**: Parágrafos, conteúdo principal, descrições

### Texto Pequeno / Labels
```css
font-size: 14px;
font-weight: 400; /* Regular */
letter-spacing: 0.5px;
line-height: 1.5;
color: #757575;
```
**Uso**: Labels, captions, texto secundário, rodapés

### Legenda de Imagem
```css
font-size: 12px;
font-weight: 400; /* Regular */
letter-spacing: 0px;
line-height: 1.4;
color: #757575;
font-style: italic;
```
**Uso**: Descrição de imagens, legendas em apresentações

## Cores do Texto

- **Texto Principal**: #2D2D2D - Corpo de texto, conteúdo legível
- **Texto Secundário**: #757575 - Labels, captions, informações menos importantes
- **Texto em Fundos Verdes**: #FFFFFF - Texto sobre fundo #1F8A42
- **Texto com Ênfase**: #1F8A42 - Destaques, links, chamadas à ação (apenas texto grande)

## Estilos Especiais

### Bloco de Citação
```css
font-size: 18px;
font-weight: 600;
color: #1F8A42;
border-left: 4px solid #1F8A42;
padding-left: 16px;
margin: 20px 0;
font-style: italic;
```

### Links - Estilo Padrão
```css
color: #1F8A42;
text-decoration: none;
border-bottom: 1px solid #1F8A42;
font-weight: 600;
```

### Links - Hover
```css
color: #1B5E20;
border-bottom: 2px solid #1B5E20;
```

## Importação

### Google Fonts (HTML)
```html
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
```

### Fallback Stack (CSS)
```css
font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
```

### Self-Hosted (Otimizado)
```css
@font-face {
  font-family: 'Open Sans';
  src: url('/fonts/open-sans-400.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}
```
