#!/usr/bin/env bash
set -euo pipefail

# Configura o serviço Ollama para escutar fora do localhost.
# Requer sudo/root no host Ubuntu.

SERVICE_NAME="ollama"
OVERRIDE_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
ENV_LINE='Environment="OLLAMA_HOST=0.0.0.0:11434"'

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "ERRO: execute como root (ex.: sudo bash scripts/configure_ollama_host.sh)" >&2
  exit 1
fi

echo "== Criando override do systemd para ${SERVICE_NAME} =="
mkdir -p "$OVERRIDE_DIR"
cat > "$OVERRIDE_FILE" <<EOF
[Service]
$ENV_LINE
EOF

echo "== Recarregando systemd e reiniciando ${SERVICE_NAME} =="
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true

echo "== Validando bind do Ollama =="
if ss -ltnp | rg -q '0\.0\.0\.0:11434'; then
  echo "OK: Ollama escutando em 0.0.0.0:11434"
else
  echo "ERRO: porta 11434 não está em 0.0.0.0. Confira logs: journalctl -u ${SERVICE_NAME} -n 100 --no-pager" >&2
  exit 1
fi

echo "== Teste HTTP local =="
curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null
echo "OK: endpoint local respondeu /api/tags"

echo "Concluído."
