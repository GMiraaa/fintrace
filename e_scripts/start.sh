#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: Docker não está instalado ou não está disponível no PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Erro: o plugin Docker Compose não está disponível." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Erro: o Docker Engine não está em execução." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Aviso: .env não encontrado; serão usados os padrões do docker-compose.yml."
  echo "Sem GEMINI_API_KEY, o processamento continuará somente com Python."
fi

echo "Construindo e iniciando backend e frontend..."
docker compose up --build --detach --wait --wait-timeout "${START_TIMEOUT_SECONDS:-120}" backend frontend
docker compose ps

backend_address="$(docker compose port backend 8000)"
frontend_address="$(docker compose port frontend 80)"
backend_port="${backend_address##*:}"
frontend_port="${frontend_address##*:}"
echo "FinTrace iniciado com sucesso."
echo "Frontend: http://localhost:${frontend_port}"
echo "Backend:  http://localhost:${backend_port}"
echo "API docs: http://localhost:${backend_port}/docs"
