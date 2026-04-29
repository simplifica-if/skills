# Simplifica IF Skills

## Resumo

Repositório de skills reutilizáveis do Simplifica IF.

## Skills

- `analise-ppc/` — análise IA-first de Projetos Pedagógicos de Curso técnico do IFPR, com scripts Python, fichas, validações cruzadas, catálogo CNCT empacotado e relatório HTML.
- `ifpr-design/` — identidade visual do IFPR para apresentações, documentos, páginas, materiais visuais e interfaces.
- `verificar-calendario/` — verificação de calendários acadêmicos do IFPR em XLSX ou PDF, com relatório em Markdown e PDF.

## Instalação local

Execute o instalador a partir da raiz do projeto alvo:

```bash
/caminho/para/simplifica-if-skills/instalar.sh
```

Por padrão, o instalador cria symlinks para todas as skills disponíveis em `.agents/skills` e/ou `.claude/skills`, conforme esses diretórios existirem no projeto.

Para instalar apenas uma ou mais skills específicas:

```bash
/caminho/para/simplifica-if-skills/instalar.sh analise-ppc
```
