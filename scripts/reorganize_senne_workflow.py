#!/usr/bin/env python3
"""Patch pontual do workflow SENNE (sem alterar lógica restante).

Aplica apenas:
1) SENNE (LLM Chain).parameters.text = ={{ $json.mensagem }}
2) Ollama Vision (Imagem) endpoint para http://172.17.0.1:11434/api/chat
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OLLAMA_ENDPOINT = "http://172.17.0.1:11434/api/chat"
LLM_TEXT_EXPR = "={{ $json.mensagem }}"


def find_node(nodes: list[dict[str, Any]], exact_name: str) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("name") == exact_name:
            return node
    return None


def set_first_existing_key(params: dict[str, Any], keys: tuple[str, ...], value: str) -> str:
    for key in keys:
        if key in params:
            params[key] = value
            return key
    params[keys[0]] = value
    return keys[0]


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python3 scripts/reorganize_senne_workflow.py <workflow.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    workflow = json.loads(path.read_text(encoding="utf-8"))
    nodes = workflow.get("nodes") or []

    llm_chain = find_node(nodes, "SENNE (LLM Chain)")
    if not llm_chain:
        raise SystemExit("ERRO: node 'SENNE (LLM Chain)' não encontrado.")

    vision_node = find_node(nodes, "Ollama Vision (Imagem)")
    if not vision_node:
        raise SystemExit("ERRO: node 'Ollama Vision (Imagem)' não encontrado.")

    llm_params = llm_chain.setdefault("parameters", {})
    llm_params["text"] = LLM_TEXT_EXPR

    vision_params = vision_node.setdefault("parameters", {})
    endpoint_key = set_first_existing_key(
        vision_params,
        ("url", "endpoint", "requestUrl", "baseURL"),
        OLLAMA_ENDPOINT,
    )

    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=== Patch SENNE aplicado ===")
    print(f"- SENNE (LLM Chain).parameters.text = {LLM_TEXT_EXPR}")
    print(f"- Ollama Vision (Imagem).parameters.{endpoint_key} = {OLLAMA_ENDPOINT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
