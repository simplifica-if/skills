#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_dirs=()
requested_skills=("$@")

usage() {
  cat <<'USAGE'
Uso:
  instalar.sh [skill...]

Descrição:
  Instala skills deste repositório no projeto atual, criando symlinks em
  .agents/skills e/ou .claude/skills, conforme esses diretórios existirem.

Exemplos:
  instalar.sh
  instalar.sh analise-ppc
USAGE
}

is_skill_dir() {
  local dir="$1"
  [[ -f "$dir/SKILL.md" ]]
}

collect_all_skills() {
  local skill_dir
  for skill_dir in "$repo_dir"/*; do
    [[ -d "$skill_dir" ]] || continue
    is_skill_dir "$skill_dir" || continue
    basename "$skill_dir"
  done | sort
}

resolve_skill_dir() {
  local skill_name="$1"
  local skill_dir="$repo_dir/$skill_name"

  if ! is_skill_dir "$skill_dir"; then
    echo "Erro: skill '$skill_name' não encontrada em $repo_dir." >&2
    exit 1
  fi

  printf '%s\n' "$skill_dir"
}

install_skill_into() {
  local skill_dir="$1"
  local skills_target_dir="$2"
  local skill_name
  local target

  skill_name="$(basename "$skill_dir")"
  target="$skills_target_dir/$skill_name"

  if [[ -L "$target" ]]; then
    ln -sfn "$skill_dir" "$target"
    echo "Atualizado: $target -> $skill_dir"
    return
  fi

  if [[ -e "$target" ]]; then
    echo "Erro: $target já existe e não é symlink. Remova ou renomeie antes de instalar." >&2
    exit 1
  fi

  ln -s "$skill_dir" "$target"
  echo "Instalado: $target -> $skill_dir"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

for maybe_target in "$PWD/.agents/skills" "$PWD/.claude/skills"; do
  if [[ -d "$maybe_target" ]]; then
    target_dirs+=("$maybe_target")
  fi
done

if [[ "${#target_dirs[@]}" -eq 0 ]]; then
  echo "Erro: nenhum diretório .agents/skills ou .claude/skills encontrado em $PWD." >&2
  exit 1
fi

if [[ "${#requested_skills[@]}" -eq 0 ]]; then
  while IFS= read -r skill_name; do
    requested_skills+=("$skill_name")
  done < <(collect_all_skills)
fi

if [[ "${#requested_skills[@]}" -eq 0 ]]; then
  echo "Erro: nenhuma skill encontrada em $repo_dir." >&2
  exit 1
fi

for skill_name in "${requested_skills[@]}"; do
  skill_dir="$(resolve_skill_dir "$skill_name")"
  for target_dir in "${target_dirs[@]}"; do
    install_skill_into "$skill_dir" "$target_dir"
  done
done
