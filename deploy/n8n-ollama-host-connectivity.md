# n8n (Docker) + Ollama (container) estáveis para o SENNE

Este guia fixa uma topologia estável para o SENNE com n8n, Ollama e Supabase em Docker.

## 1) Princípio recomendado

Quando o Ollama está no container `ollama`, use o hostname de serviço da rede Docker:

```text
http://ollama:11434
```

No n8n (nodes HTTP / AI), prefira:

- Chat: `http://ollama:11434/api/chat`
- Health básico: `http://ollama:11434/api/tags`

> Isso elimina dependência de IPs de gateway variáveis (`172.17.0.1`, `172.20.0.1` etc.).

## 2) Exemplo mínimo de docker-compose

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - TZ=America/Sao_Paulo
    depends_on:
      - ollama
      - supabase-db

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"

  supabase-db:
    image: supabase/postgres:latest
    container_name: supabase-db
    restart: unless-stopped
```

Todos os serviços devem estar na mesma rede Docker (default do compose já resolve).

## 3) Modelo padrão do atendimento

Defina `qwen2.5:3b` como modelo principal do SENNE.

Teste rápido no container Ollama:

```bash
docker exec -it ollama ollama pull qwen2.5:3b
docker exec -it ollama ollama list
```

## 4) Diagnóstico de rede e HTTP

```bash
# containers ativos
 docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# n8n alcança ollama por nome do serviço
 docker exec n8n sh -lc 'curl -fsS http://ollama:11434/api/tags >/dev/null && echo OK'

# endpoint público do webhook do SENNE
 curl -fsS -X POST "https://n8n.mfadvocacia.api.br/webhook/senne-entrada" \
  -H "Content-Type: application/json" \
  -d '{"mensagem":"ping","usuario_id":"diag","canal":"site"}'
```

## 5) Frontend e payload de resposta

Para evitar fallback no site:

- mantenha chat e atendimento apontando para `/webhook/senne-entrada`;
- no retorno do workflow, prefira chave textual (`reply` ou `resposta`);
- se o n8n devolver array/objeto aninhado, o parser do frontend deve extrair o primeiro texto válido.

## 6) Supabase

A integração com Supabase permanece no workflow (nós de persistência não devem ser removidos durante simplificação).

Recomendação operacional:

- simplificar apenas nós duplicados de roteamento/transformação;
- manter nós de gravação/auditoria no Supabase;
- validar que o webhook responde texto mesmo quando a persistência falhar (fallback controlado no n8n).
