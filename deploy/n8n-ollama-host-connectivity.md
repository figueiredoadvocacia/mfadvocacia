# n8n (Docker) acessando Ollama no host Ubuntu

Este guia fixa uma forma estável de acesso do n8n (container) ao Ollama rodando no host.

## 1) Princípio recomendado

Use `host.docker.internal` no node HTTP do n8n e configure no `docker-compose`:

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - TZ=America/Sao_Paulo
```

> Isso evita depender de gateway IP variável (`172.17.0.1`, `172.20.0.1`, etc.).

## 2) URL final para o node HTTP no n8n

Use:

```text
http://host.docker.internal:11434/api/chat
```

Para teste simples de conectividade:

```text
http://host.docker.internal:11434/api/tags
```

## 3) Bind do Ollama no host

No host Ubuntu, o serviço precisa escutar fora de localhost:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Valide:

```bash
ss -ltnp | rg 11434
curl -fsS http://127.0.0.1:11434/api/tags
curl -fsS http://<IP_DO_HOST>:11434/api/tags
```

## 4) Comandos de diagnóstico Docker

```bash
# ver rede do container n8n
docker inspect n8n --format '{{json .NetworkSettings.Networks}}' | jq

# descobrir gateway da rede principal do container
NET=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{printf "%s\n" $k}}{{end}}' n8n | head -n1)
docker network inspect "$NET" -f '{{(index .IPAM.Config 0).Gateway}}'

# validar resolução do host.docker.internal dentro do n8n
docker exec n8n getent hosts host.docker.internal

# validar acesso ao Ollama via nome estável
docker exec n8n curl -fsS http://host.docker.internal:11434/api/tags
```

## 5) Firewall e roteamento

Se houver UFW/iptables no host, liberar entrada TCP 11434 na interface bridge do Docker.

Exemplo com UFW:

```bash
sudo ufw allow in on docker0 to any port 11434 proto tcp
```

Se o n8n estiver em rede custom (`br-xxxx`), troque `docker0` pela interface correspondente.

## 6) Fallback (apenas se necessário)

Se não puder usar `extra_hosts`, use o gateway real da rede do container:

```text
http://<GATEWAY_DA_REDE_DO_N8N>:11434/api/chat
```

Mas trate como fallback; o recomendado para estabilidade operacional é `host.docker.internal` + `host-gateway`.
