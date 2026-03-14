#!/usr/bin/env bash
set -euo pipefail

# Valida conectividade do Ollama no host e do container n8n para o host-gateway.
# Uso opcional: N8N_CONTAINER=n8n_main bash scripts/validate_ollama_connectivity.sh

N8N_CONTAINER="${N8N_CONTAINER:-n8n}"

echo "== 1) Host responde em localhost =="
curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null
echo "OK: localhost:11434 respondeu"

echo "== 2) Host responde via bridge gateway =="
curl -fsS "http://172.17.0.1:11434/api/tags" >/dev/null
echo "OK: 172.17.0.1:11434 respondeu"

echo "== 3) Container n8n -> host gateway =="
if docker ps --format '{{.Names}}' | rg -qx "$N8N_CONTAINER"; then
  docker exec "$N8N_CONTAINER" sh -lc "curl -fsS http://172.17.0.1:11434/api/tags >/dev/null"
  echo "OK: container $N8N_CONTAINER acessa 172.17.0.1:11434"
else
  echo "WARN: container '$N8N_CONTAINER' não encontrado; pulando teste de dentro do container."
fi
