#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_name="analise-ppc"
installed=0

install_into() {
  local skills_dir="$1"
  local target="${skills_dir}/${skill_name}"

  if [[ -L "$target" ]]; then
    ln -sfn "$skill_dir" "$target"
    echo "Atualizado: $target -> $skill_dir"
    installed=1
    return
  fi

  if [[ -e "$target" ]]; then
    echo "Erro: $target já existe e não é symlink. Remova ou renomeie antes de instalar." >&2
    exit 1
  fi

  ln -s "$skill_dir" "$target"
  echo "Instalado: $target -> $skill_dir"
  installed=1
}

for skills_dir in "$PWD/.agents/skills" "$PWD/.claude/skills"; do
  if [[ -d "$skills_dir" ]]; then
    install_into "$skills_dir"
  fi
done

if [[ "$installed" -eq 0 ]]; then
  echo "Erro: nenhum diretório .agents/skills ou .claude/skills encontrado em $PWD." >&2
  exit 1
fi
