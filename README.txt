# MF Advocacia Site

Site institucional estático da MF Advocacia com captação de leads e widget do assistente SENNE integrado ao n8n.

## Stack e operação
- HTML5/CSS3/JavaScript (sem framework)
- Deploy estático em Nginx
- Integração de captação via webhooks n8n
- Contexto de IA no fluxo n8n com Ollama interno (`http://ollama:11434`)

## Estrutura principal
- `index.html`: página inicial, CTA e formulário de contato principal
- `atendimento.html`: formulário de triagem para agendamento
- `assets/js/site-config.js`: configuração runtime centralizada (local vs produção)
- `assets/js/site.js`: envios para webhooks, feedback de UX e widget SENNE
- `.env.example`: referência operacional de variáveis
- `deploy/nginx.mfadvocacia.api.br.conf.example`: exemplo de vhost Nginx para publicação

## Configuração runtime (frontend)
O frontend usa `window.MF_SITE_CONFIG` com fallback seguro.

### Padrão automático por ambiente
`assets/js/site-config.js` detecta o host:
- `localhost/127.0.0.1/0.0.0.0/*.local` => usa `http://localhost:5678`
- demais hosts => usa `https://n8n.mfadvocacia.api.br`

### Webhooks configuráveis
- Lead (formulário da home): `integration.leadWebhookPath`
- Chat SENNE (widget): `integration.chatWebhookPath`
- Atendimento (triagem): `integration.senneEntradaPath`

> Importante: os *paths reais* devem existir no n8n. O projeto mantém os paths atuais e não inventa novos endpoints.

### Override opcional para produção
Se precisar sobrescrever sem editar `site-config.js`:
1. Copie `assets/js/site-config.override.example.js` para `assets/js/site-config.override.js`
2. Ajuste valores
3. Inclua o arquivo copiado antes de `assets/js/site-config.js` nas páginas desejadas

## Publicação em Ubuntu + Nginx (passo a passo)
1. Copie os arquivos do repositório para o servidor:
   - destino sugerido: `/var/www/mfadvocacia`
2. Configure permissões:
   - `sudo chown -R www-data:www-data /var/www/mfadvocacia`
3. Crie vhost a partir de `deploy/nginx.mfadvocacia.api.br.conf.example`
   - arquivo sugerido: `/etc/nginx/sites-available/mfadvocacia.api.br`
   - escolha aplicada: `try_files` com `=404` para rotas inexistentes (site multipágina), sem fallback global para `/index.html`
4. Habilite site e valide:
   - `sudo ln -s /etc/nginx/sites-available/mfadvocacia.api.br /etc/nginx/sites-enabled/`
   - `sudo nginx -t`
   - `sudo systemctl reload nginx`
5. No Cloudflare:
   - mantenha DNS apontando para o servidor
   - SSL/TLS em Full (strict)
   - não bloquear `POST` para `https://n8n.mfadvocacia.api.br/webhook/*`

## Como validar produção (site -> n8n)
1. Abra `https://mfadvocacia.api.br`
2. Envie o formulário da home e confirme resposta de sucesso no frontend
3. Envie o formulário `atendimento.html` e confirme resposta de sucesso
4. Envie uma mensagem no chat SENNE
5. No n8n, valide as execuções dos três webhooks
6. Se houver erro, o frontend agora mostra status HTTP nas mensagens de falha para diagnóstico

## CORS mínimo recomendado (lado n8n/reverse proxy)
Permitir origem do site para webhooks públicos:
- `Access-Control-Allow-Origin: https://mfadvocacia.api.br`
- `Access-Control-Allow-Methods: POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

Se usar Cloudflare WAF/Bot Fight, criar exceção para os endpoints de webhook usados pelo site.

## Teste local rápido
```bash
python3 -m http.server 8080
```
Acesse `http://localhost:8080`.

> Em localhost, o runtime usa automaticamente `http://localhost:5678` como base do n8n.

## Workflow SENNE (n8n + Ollama)
O script `scripts/reorganize_senne_workflow.py` aplica correções de estabilidade no fluxo SENNE:
- troca `Ollama /api/generate` por `Ollama /api/chat`;
- envia payload em formato chat (`messages`) com prompt de sistema enxuto;
- limita geração com `temperature: 0.3` e `num_predict: 220`;
- habilita fallback para resposta padrão quando houver falha no Ollama;
- força `Respond to Webhook` a retornar JSON no formato `{"ok": true, "reply": "..."}`.

No procedimento operacional (`scripts/senne_hotfix.sh`) há validação explícita para bloquear importação se ainda existir `/api/generate`.
