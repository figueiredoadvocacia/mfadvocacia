#!/usr/bin/env python3
"""Patch do workflow SENNE para integração resiliente com Ollama via n8n.

Ajustes aplicados automaticamente:
1) Migra chamadas Ollama de /api/generate para /api/chat.
2) Troca payload de prompt bruto por formato de chat (system + user).
3) Limita geração com options.num_predict = 220 e temperature = 0.3.
4) Habilita fallback em falhas de node Ollama (continueOnFail + mensagem padrão).
5) Garante resposta do webhook em JSON no formato {"ok": true, "reply": "..."}.
6) Reduz prompt-base do sistema para evitar consumo excessivo de memória.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_OLLAMA_CHAT_ENDPOINT = "http://172.17.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:3b"
FALLBACK_REPLY = "Recebi sua mensagem. Vou organizar as informações e um momento já te respondo."
SYSTEM_PROMPT = (
    "Você é SENNE, assistente jurídico da MF Advocacia. "
    "Responda em português do Brasil, com objetividade, educação e linguagem simples. "
    "Não invente fatos, leis ou prazos. Se faltar contexto, peça dados essenciais em até 2 perguntas curtas. "
    "Finalize com próximo passo claro."
)

CHAT_BODY_EXPR = "={{ ({\n" \
    "  model: $json.model || '" + DEFAULT_MODEL + "',\n" \
    "  messages: [\n" \
    "    { role: 'system', content: $json.systemPrompt || '" + SYSTEM_PROMPT.replace("'", "\\'") + "' },\n" \
    "    { role: 'user', content: String($json.mensagem || $json.message || $json.text || '') }\n" \
    "  ],\n" \
    "  stream: false,\n" \
    "  options: {\n" \
    "    temperature: 0.3,\n" \
    "    num_predict: 220\n" \
    "  }\n" \
    "}) }}"

RESPONSE_JSON_EXPR = (
    "={{ ({ "
    "ok: true, "
    "reply: $json.reply || "
    "$json.response || "
    "$json.output || "
    "$json.text || "
    "$json['message']?.content || "
    "$json['output']?.content || "
    f"'{FALLBACK_REPLY}'"
    " }) }}"
)



def find_nodes(nodes: list[dict[str, Any]], predicate) -> list[dict[str, Any]]:
    return [node for node in nodes if predicate(node)]



def normalize_ollama_endpoint(url: str) -> str:
    if "/api/generate" in url:
        return url.replace("/api/generate", "/api/chat")
    if url.rstrip("/").endswith("/api/chat"):
        return url
    if "11434" in url and "/api/" not in url:
        return url.rstrip("/") + "/api/chat"
    return url



def patch_ollama_node(node: dict[str, Any], changed: list[str]) -> None:
    params = node.setdefault("parameters", {})

    # Endpoint
    for key in ("url", "endpoint", "requestUrl", "baseURL"):
        if key in params and isinstance(params[key], str):
            new_url = normalize_ollama_endpoint(params[key])
            if new_url != params[key]:
                params[key] = new_url
                changed.append(f"{node.get('name')}.{key} -> {new_url}")

    if "url" not in params:
        params["url"] = DEFAULT_OLLAMA_CHAT_ENDPOINT
        changed.append(f"{node.get('name')}.url -> {DEFAULT_OLLAMA_CHAT_ENDPOINT}")

    # Force POST + JSON body in chat format
    if params.get("method") != "POST":
        params["method"] = "POST"
        changed.append(f"{node.get('name')}.method -> POST")

    params["sendBody"] = True
    params["contentType"] = "json"
    params["jsonBody"] = CHAT_BODY_EXPR

    # Compatibility for nodes using bodyParameters
    body_params = params.get("bodyParameters")
    if isinstance(body_params, dict):
        body_params.clear()

    node["continueOnFail"] = True
    changed.append(f"{node.get('name')} habilitado com continueOnFail + payload chat")



def patch_response_webhook_node(node: dict[str, Any], changed: list[str]) -> None:
    params = node.setdefault("parameters", {})

    if params.get("respondWith") != "json":
        params["respondWith"] = "json"
        changed.append(f"{node.get('name')}.respondWith -> json")

    params["responseBody"] = RESPONSE_JSON_EXPR
    params["options"] = params.get("options") or {}
    if params["options"].get("responseCode") != 200:
        params["options"]["responseCode"] = 200
        changed.append(f"{node.get('name')}.options.responseCode -> 200")



def patch_set_or_code_fallback(node: dict[str, Any], changed: list[str]) -> None:
    name = str(node.get("name", "")).lower()
    if "fallback" not in name and "erro" not in name and "error" not in name:
        return

    params = node.setdefault("parameters", {})

    # Set node style
    values = params.get("values")
    if isinstance(values, dict):
        values.setdefault("string", [])
        string_items = values["string"]
        if not any((item.get("name") == "reply") for item in string_items if isinstance(item, dict)):
            string_items.append({"name": "reply", "value": FALLBACK_REPLY})
            changed.append(f"{node.get('name')} adicionou values.string.reply de fallback")

    # Code node style
    if "jsCode" in params and isinstance(params["jsCode"], str):
        if FALLBACK_REPLY not in params["jsCode"]:
            params["jsCode"] += (
                "\n\nfor (const item of items) {\n"
                f"  item.json.reply = item.json.reply || '{FALLBACK_REPLY}';\n"
                "}\nreturn items;\n"
            )
            changed.append(f"{node.get('name')} reforçou fallback em jsCode")



def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python3 scripts/reorganize_senne_workflow.py <workflow.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    workflow = json.loads(path.read_text(encoding="utf-8"))
    nodes = workflow.get("nodes") or []

    changed: list[str] = []

    ollama_nodes = find_nodes(
        nodes,
        lambda n: (
            "ollama" in str(n.get("name", "")).lower()
            or "ollama" in json.dumps(n.get("parameters", {}), ensure_ascii=False).lower()
        ),
    )
    for node in ollama_nodes:
        patch_ollama_node(node, changed)

    response_nodes = find_nodes(
        nodes,
        lambda n: str(n.get("type", "")).endswith("respondToWebhook")
        or "respond to webhook" in str(n.get("name", "")).lower(),
    )
    for node in response_nodes:
        patch_response_webhook_node(node, changed)

    for node in nodes:
        patch_set_or_code_fallback(node, changed)

    # Fallback global mínimo: se existir node SENNE (LLM Chain), reduzir prompt de entrada gigante
    for node in nodes:
        if node.get("name") == "SENNE (LLM Chain)":
            params = node.setdefault("parameters", {})
            params["text"] = "={{ String($json.mensagem || $json.message || '').slice(0, 1400) }}"
            changed.append("SENNE (LLM Chain).parameters.text reduzido para 1400 chars")

    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=== Patch SENNE aplicado ===")
    if ollama_nodes:
        print(f"- Nodes Ollama ajustados para /api/chat: {len(ollama_nodes)}")
    else:
        print("- Aviso: nenhum node Ollama identificado automaticamente.")
    if response_nodes:
        print(f"- Nodes Respond to Webhook ajustados para JSON: {len(response_nodes)}")
    else:
        print("- Aviso: nenhum node Respond to Webhook identificado.")

    if changed:
        print("- Alterações detalhadas:")
        for item in changed:
            print(f"  * {item}")
    else:
        print("- Nenhuma alteração necessária.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
