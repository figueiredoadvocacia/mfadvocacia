#!/usr/bin/env bash
set -euo pipefail

# Valida conectividade Ollama (host Ubuntu) <-> container n8n em Docker.
#
# Uso:
#   N8N_CONTAINER=n8n bash scripts/validate_ollama_connectivity.sh
#
# Estratégia:
# 1) valida Ollama no host (localhost e IP LAN opcional)
# 2) descobre gateway da rede bridge do container n8n
# 3) testa acesso do container via gateway e via host.docker.internal

N8N_CONTAINER="${N8N_CONTAINER:-n8n}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_PATH="${OLLAMA_PATH:-/api/tags}"
HOST_LAN_IP="${HOST_LAN_IP:-}"

HOST_LOCAL_URL="http://127.0.0.1:${OLLAMA_PORT}${OLLAMA_PATH}"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERRO: comando obrigatório não encontrado: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd docker
require_cmd rg

log "== 1) Host responde em localhost =="
curl -fsS "$HOST_LOCAL_URL" >/dev/null
log "OK: ${HOST_LOCAL_URL} respondeu"

if [[ -n "$HOST_LAN_IP" ]]; then
  LAN_URL="http://${HOST_LAN_IP}:${OLLAMA_PORT}${OLLAMA_PATH}"
  log "== 2) Host responde via IP LAN informado =="
  curl -fsS "$LAN_URL" >/dev/null
  log "OK: ${LAN_URL} respondeu"
fi

if ! docker ps --format '{{.Names}}' | rg -qx "$N8N_CONTAINER"; then
  echo "ERRO: container '$N8N_CONTAINER' não encontrado em execução." >&2
  exit 1
fi

NETWORK_NAME="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{printf "%s\n" $k}}{{end}}' "$N8N_CONTAINER" | head -n1)"
if [[ -z "$NETWORK_NAME" ]]; then
  echo "ERRO: não foi possível descobrir a rede do container '$N8N_CONTAINER'." >&2
  exit 1
fi

GATEWAY_IP="$(docker network inspect "$NETWORK_NAME" -f '{{(index .IPAM.Config 0).Gateway}}')"
if [[ -z "$GATEWAY_IP" || "$GATEWAY_IP" == "<no value>" ]]; then
  echo "ERRO: não foi possível obter o gateway da rede '$NETWORK_NAME'." >&2
  exit 1
fi

log "== 3) Rede Docker do n8n =="
log "Container: $N8N_CONTAINER"
log "Rede principal: $NETWORK_NAME"
log "Gateway da rede: $GATEWAY_IP"

GATEWAY_URL="http://${GATEWAY_IP}:${OLLAMA_PORT}${OLLAMA_PATH}"
log "== 4) Container n8n -> gateway da própria rede =="
docker exec "$N8N_CONTAINER" sh -lc "curl -fsS ${GATEWAY_URL} >/dev/null"
log "OK: container $N8N_CONTAINER acessa ${GATEWAY_URL}"

log "== 5) Container n8n -> host.docker.internal (se configurado) =="
if docker exec "$N8N_CONTAINER" sh -lc "getent hosts host.docker.internal >/dev/null 2>&1"; then
  docker exec "$N8N_CONTAINER" sh -lc "curl -fsS http://host.docker.internal:${OLLAMA_PORT}${OLLAMA_PATH} >/dev/null"
  log "OK: host.docker.internal:${OLLAMA_PORT} respondeu de dentro do container"
else
  log "WARN: host.docker.internal não resolve dentro do container (faltando extra_hosts: host-gateway)."
fi

log "Concluído."
