#!/usr/bin/env bash
set -euo pipefail

log() { echo "== $* =="; }

log "0) Contexto"
whoami
pwd
date

log "1) Conferir containers do n8n"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

log "2) Backup do banco do n8n (Postgres container)"
PG_CONTAINER="${PG_CONTAINER:-n8n_postgres}"
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/n8n_backups}"
mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"

docker exec "$PG_CONTAINER" sh -lc 'pg_isready -U postgres' || true
PGUSER="$(docker exec "$PG_CONTAINER" sh -lc 'echo ${POSTGRES_USER:-postgres}')"
PGDB="$(docker exec "$PG_CONTAINER" sh -lc 'echo ${POSTGRES_DB:-postgres}')"

docker exec "$PG_CONTAINER" sh -lc "pg_dump -U \"$PGUSER\" \"$PGDB\" > /tmp/n8n_${TS}.sql"
docker cp "$PG_CONTAINER:/tmp/n8n_${TS}.sql" "$BACKUP_DIR/n8n_${TS}.sql"
docker exec "$PG_CONTAINER" sh -lc "rm -f /tmp/n8n_${TS}.sql"
echo "Backup OK: $BACKUP_DIR/n8n_${TS}.sql"

log "3) Exportar workflow atual (via API do n8n)"
N8N_API_URL="${N8N_API_URL:-http://localhost:5678}"
if [[ -z "${N8N_API_KEY:-}" ]]; then
  echo "ERRO: defina N8N_API_KEY no ambiente antes de executar." >&2
  exit 1
fi

WF_BACKUP="$BACKUP_DIR/workflows_${TS}.json"
curl -fsS -H "X-N8N-API-KEY: $N8N_API_KEY" "$N8N_API_URL/api/v1/workflows" > "$WF_BACKUP"
echo "Workflow export OK: $WF_BACKUP"

log "4) Atualizar/Importar workflow SENNE"
if [[ -z "${SENNE_WF_JSON:-}" ]]; then
  SENNE_WF_JSON="$(rg --files | rg -i 'senne.*\.json$' | head -n 1 || true)"
fi

if [[ -z "${SENNE_WF_JSON:-}" || ! -f "$SENNE_WF_JSON" ]]; then
  echo "ERRO: não encontrei o JSON do workflow SENNE. Defina SENNE_WF_JSON com caminho válido." >&2
  exit 1
fi

echo "Workflow alvo: $SENNE_WF_JSON"

python3 - "$SENNE_WF_JSON" <<'PY'
import json,sys
p=sys.argv[1]
wf=json.load(open(p,encoding='utf-8'))
nodes=wf.get('nodes',[])
webhooks=[n for n in nodes if n.get('type','').endswith('.webhook') or n.get('type','')=='n8n-nodes-base.webhook']
if not any((n.get('parameters',{}) or {}).get('path')=='senne-entrada' for n in webhooks):
    raise SystemExit("ERRO: workflow SENNE não tem webhook com path 'senne-entrada'. Não vou importar.")
print('OK: webhook path senne-entrada encontrado.')
PY

python3 - "$SENNE_WF_JSON" <<'PY'
import json,os,sys
import requests

api=os.environ.get('N8N_API_URL','http://localhost:5678')
key=os.environ['N8N_API_KEY']
wf_path=sys.argv[1]
wf=json.load(open(wf_path,encoding='utf-8'))

name=wf.get('name','SENNE - Atendimento + CRM (Supabase)')
headers={'X-N8N-API-KEY': key, 'Content-Type':'application/json'}
r=requests.get(f"{api}/api/v1/workflows",headers=headers,timeout=30)
r.raise_for_status()
body=r.json()
items=body.get('data',[]) if isinstance(body,dict) else body

target=None
for it in items:
    if it.get('name','').strip().lower()==name.strip().lower():
        target=it
        break

if target:
    wid=target['id']
    wf['id']=wid
    rr=requests.put(f"{api}/api/v1/workflows/{wid}",headers=headers,data=json.dumps(wf),timeout=30)
    rr.raise_for_status()
    print('UPDATED workflow:', wid, name)
    active=target.get('active')
    if active is False:
        ra=requests.post(f"{api}/api/v1/workflows/{wid}/activate",headers=headers,timeout=30)
        ra.raise_for_status()
        print('ACTIVATED workflow:', wid)
else:
    rr=requests.post(f"{api}/api/v1/workflows",headers=headers,data=json.dumps(wf),timeout=30)
    rr.raise_for_status()
    new=rr.json()
    wid=new.get('id')
    print('CREATED workflow:', wid, name)
    if wid:
        ra=requests.post(f"{api}/api/v1/workflows/{wid}/activate",headers=headers,timeout=30)
        ra.raise_for_status()
        print('ACTIVATED workflow:', wid)
PY

log "5) Testar webhook público"
curl -fsS -X POST "https://n8n.mfadvocacia.api.br/webhook/senne-entrada" \
  -H "Content-Type: application/json" \
  -d '{"canal":"site","usuario_id":"teste_codex","nome":"Teste","mensagem":"Ping do site","origem":"atendimento.html"}' | head -c 400; echo

log "DONE"
