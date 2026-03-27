#!/usr/bin/env python3
"""Simplifica e estabiliza o workflow SENNE para operação com n8n + Ollama + Supabase.

Ajustes aplicados no JSON do workflow:
1) Garante que o prompt do LLM use a mensagem de entrada do webhook.
2) Padroniza endpoints do Ollama para o serviço Docker `http://ollama:11434`.
3) Mantém o nome do modelo textual em `qwen2.5:3b` quando o campo existir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OLLAMA_BASE = "http://ollama:11434"
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS_ENDPOINT = f"{OLLAMA_BASE}/api/tags"
LLM_TEXT_EXPR = "={{ $json.mensagem }}"
TEXT_MODEL = "qwen2.5:3b"
SUPABASE_CONTATOS_URL = "https://oizwhtofmmfxfrmqzolu.supabase.co/rest/v1/contatos"


def find_nodes(nodes: list[dict[str, Any]], *, name_contains: str = "", type_contains: str = "") -> list[dict[str, Any]]:
  matched: list[dict[str, Any]] = []
  for node in nodes:
    name = str(node.get("name") or "")
    node_type = str(node.get("type") or "")
    if name_contains and name_contains.lower() not in name.lower():
      continue
    if type_contains and type_contains.lower() not in node_type.lower():
      continue
    matched.append(node)
  return matched


def set_if_present(params: dict[str, Any], keys: tuple[str, ...], value: str) -> str | None:
  for key in keys:
    if key in params:
      params[key] = value
      return key
  return None


def patch_llm_nodes(nodes: list[dict[str, Any]]) -> list[str]:
  patched: list[str] = []
  candidates = find_nodes(nodes, name_contains="llm") + find_nodes(nodes, type_contains="langchain")

  seen = set()
  for node in candidates:
    node_id = id(node)
    if node_id in seen:
      continue
    seen.add(node_id)

    params = node.setdefault("parameters", {})
    params["text"] = LLM_TEXT_EXPR

    model_key = set_if_present(params, ("model", "modelName"), TEXT_MODEL)
    model_info = f"; {model_key}={TEXT_MODEL}" if model_key else ""
    patched.append(f"{node.get('name')} -> text={LLM_TEXT_EXPR}{model_info}")

  if not patched:
    raise SystemExit("ERRO: nenhum node LLM encontrado para ajustar texto de entrada.")

  return patched


def patch_ollama_http_nodes(nodes: list[dict[str, Any]]) -> list[str]:
  patched: list[str] = []

  for node in nodes:
    params = node.get("parameters")
    if not isinstance(params, dict):
      continue

    name = str(node.get("name") or "")
    node_type = str(node.get("type") or "")

    is_http_like = "http" in node_type.lower() or any(k in params for k in ("url", "endpoint", "requestUrl", "baseURL"))
    mentions_ollama = "ollama" in name.lower() or "11434" in json.dumps(params, ensure_ascii=False)

    if not (is_http_like and mentions_ollama):
      continue

    endpoint = OLLAMA_CHAT_ENDPOINT if "chat" in name.lower() or "vision" in name.lower() else OLLAMA_TAGS_ENDPOINT
    key = set_if_present(params, ("url", "endpoint", "requestUrl", "baseURL"), endpoint)
    if key:
      patched.append(f"{name} -> {key}={endpoint}")

    model_key = set_if_present(params, ("model", "modelName"), TEXT_MODEL)
    if model_key:
      patched.append(f"{name} -> {model_key}={TEXT_MODEL}")

  if not patched:
    raise SystemExit("ERRO: nenhum node Ollama/HTTP encontrado para padronizar endpoint.")

  return patched


def patch_supabase_lookup_node(nodes: list[dict[str, Any]]) -> list[str]:
  patched: list[str] = []

  for node in nodes:
    name = str(node.get("name") or "")
    if name.strip().lower() != "supabase (buscar contato)":
      continue

    params = node.setdefault("parameters", {})
    params["url"] = SUPABASE_CONTATOS_URL
    params["sendQuery"] = True
    params["queryParametersUi"] = {
      "parameter": [
        {"name": "select", "value": "id,canal_origem,usuario_id,nome,status"},
        {"name": "canal_origem", "value": "={{ 'eq.' + $json.canal }}"},
        {"name": "usuario_id", "value": "={{ 'eq.' + $json.usuario_id }}"},
        {"name": "limit", "value": "1"},
      ]
    }

    patched.append(
      f"{name} -> url={SUPABASE_CONTATOS_URL}; query params separados (select/canal_origem/usuario_id/limit)"
    )

  if not patched:
    raise SystemExit("ERRO: node 'Supabase (buscar contato)' não encontrado para ajuste.")

  return patched


def main() -> int:
  if len(sys.argv) != 2:
    print("Uso: python3 scripts/reorganize_senne_workflow.py <workflow.json>", file=sys.stderr)
    return 2

  path = Path(sys.argv[1])
  workflow = json.loads(path.read_text(encoding="utf-8"))
  nodes = workflow.get("nodes") or []
  if not nodes:
    raise SystemExit("ERRO: JSON sem nós de workflow.")

  llm_changes = patch_llm_nodes(nodes)
  ollama_changes = patch_ollama_http_nodes(nodes)
  supabase_changes = patch_supabase_lookup_node(nodes)

  path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

  print("=== Patch SENNE aplicado ===")
  print("- LLM")
  for line in llm_changes:
    print(f"  - {line}")
  print("- Ollama")
  for line in ollama_changes:
    print(f"  - {line}")
  print("- Supabase (buscar contato)")
  for line in supabase_changes:
    print(f"  - {line}")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
