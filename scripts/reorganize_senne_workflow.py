#!/usr/bin/env python3
"""Hotfix de contexto do workflow SENNE (n8n).

Uso:
  python3 scripts/reorganize_senne_workflow.py caminho/workflow.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def normalize(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def find_node(nodes: list[dict[str, Any]], exact_name: str) -> dict[str, Any] | None:
    for n in nodes:
        if n.get("name") == exact_name:
            return n
    return None


def find_node_by_keywords(nodes: list[dict[str, Any]], *keywords: str) -> dict[str, Any] | None:
    kws = [normalize(k) for k in keywords]
    for n in nodes:
        name = normalize(n.get("name", ""))
        if all(k in name for k in kws):
            return n
    return None


def ensure_connection(conns: dict[str, Any], src: str, dst: str, src_out: int = 0, dst_in: int = 0) -> None:
    src_map = conns.setdefault(src, {"main": []})
    main = src_map.setdefault("main", [])
    while len(main) <= src_out:
        main.append([])
    target = {"node": dst, "type": "main", "index": dst_in}
    if target not in main[src_out]:
        main[src_out].append(target)


def remove_incoming(conns: dict[str, Any], target: str, input_index: int | None = None) -> None:
    for src_name, src_data in list(conns.items()):
        main = (src_data or {}).get("main") or []
        changed = False
        for out_idx, out_links in enumerate(main):
            new_links = []
            for l in out_links:
                if l.get("node") != target:
                    new_links.append(l)
                    continue
                if input_index is not None and l.get("index") != input_index:
                    new_links.append(l)
                    continue
                changed = True
            main[out_idx] = new_links
        if changed:
            conns[src_name]["main"] = main


def ensure_merge_node(nodes: list[dict[str, Any]], template_from: dict[str, Any], name: str, x_offset: int, y_offset: int) -> dict[str, Any]:
    existing = find_node(nodes, name)
    if existing:
        existing.setdefault("parameters", {})
        existing["parameters"]["mode"] = "mergeByPosition"
        return existing

    new_node = {
        "parameters": {"mode": "mergeByPosition"},
        "id": f"auto-{name.lower().replace(' ', '-').replace('+', 'plus')}",
        "name": name,
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2,
        "position": [
            int((template_from.get("position") or [0, 0])[0]) + x_offset,
            int((template_from.get("position") or [0, 0])[1]) + y_offset,
        ],
    }
    nodes.append(new_node)
    return new_node


def upsert_notes(node: dict[str, Any], text: str) -> None:
    notes = (node.get("notes") or "").strip()
    if text not in notes:
        node["notes"] = f"{notes}\n{text}".strip()
    node["notesInFlow"] = True


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: reorganize_senne_workflow.py <workflow.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    wf = json.loads(path.read_text(encoding="utf-8"))
    nodes = wf.get("nodes") or []
    conns = wf.setdefault("connections", {})

    required_nodes = [
        "Normalizar Entrada",
        "É Imagem?",
        "É Áudio?",
        "Ollama Vision (Imagem)",
        "SENNE (LLM Chain)",
        "SENNE (Ollama Chat Model)",
        "Extrair resposta IA2",
        "Respond to Webhook",
    ]
    missing = [n for n in required_nodes if not find_node(nodes, n)]
    if missing:
        raise SystemExit(f"Workflow incompleto; faltam nodes obrigatórios: {', '.join(missing)}")

    changed: list[str] = []
    created: list[str] = []

    llm_chain = find_node(nodes, "SENNE (LLM Chain)")
    llm_chain.setdefault("parameters", {})["text"] = "={{ $json.mensagem }}"
    changed.append("SENNE (LLM Chain): parameters.text = {{$json.mensagem}}")

    normalizar = find_node(nodes, "Normalizar Entrada")
    contato_node = (
        find_node_by_keywords(nodes, "supabase", "contato")
        or find_node_by_keywords(nodes, "inserir", "contato")
        or find_node_by_keywords(nodes, "atualizar", "contato")
    )
    if not contato_node:
        raise SystemExit("Não encontrei node de contato no Supabase (upsert/inserir/atualizar contato).")

    merge_contato = ensure_merge_node(nodes, contato_node, "Merge contato + contexto", 280, 0)
    if merge_contato.get("id", "").startswith("auto-"):
        created.append("Merge contato + contexto")
    else:
        changed.append("Merge contato + contexto (reutilizado)")

    ensure_connection(conns, contato_node["name"], merge_contato["name"], 0, 0)
    ensure_connection(conns, normalizar["name"], merge_contato["name"], 0, 1)

    salvar_msg_cliente = find_node(nodes, "Supabase (salvar msg cliente)")
    if not salvar_msg_cliente:
        raise SystemExit("Não encontrei node 'Supabase (salvar msg cliente)'.")
    remove_incoming(conns, salvar_msg_cliente["name"])
    ensure_connection(conns, merge_contato["name"], salvar_msg_cliente["name"], 0, 0)
    changed.append("Supabase (salvar msg cliente): entrada passa a vir do Merge contato + contexto")

    extrair_ia = find_node(nodes, "Extrair resposta IA2")
    merge_resposta = ensure_merge_node(nodes, extrair_ia, "Merge resposta + contexto", 280, 40)
    if merge_resposta.get("id", "").startswith("auto-"):
        created.append("Merge resposta + contexto")
    else:
        changed.append("Merge resposta + contexto (reutilizado)")

    ensure_connection(conns, extrair_ia["name"], merge_resposta["name"], 0, 0)
    ensure_connection(conns, merge_contato["name"], merge_resposta["name"], 0, 1)

    salvar_resposta = (
        find_node_by_keywords(nodes, "supabase", "resposta", "ia")
        or find_node_by_keywords(nodes, "salvar", "resposta", "ia")
    )
    if salvar_resposta:
        remove_incoming(conns, salvar_resposta["name"])
        ensure_connection(conns, merge_resposta["name"], salvar_resposta["name"], 0, 0)
        changed.append(f"{salvar_resposta['name']}: entrada passa a vir do Merge resposta + contexto")

    respond = find_node(nodes, "Respond to Webhook")
    rp = respond.setdefault("parameters", {})
    rp["respondWith"] = "json"
    rp["responseBody"] = (
        "={{ ({\n"
        "  ok: true,\n"
        "  reply: $json.reply || $json.resposta || 'Recebi sua mensagem. Já vou te responder.',\n"
        "  resposta: $json.reply || $json.resposta || 'Recebi sua mensagem. Já vou te responder.'\n"
        "}) }}"
    )
    remove_incoming(conns, respond["name"])
    if salvar_resposta:
        ensure_connection(conns, salvar_resposta["name"], respond["name"], 0, 0)
    else:
        ensure_connection(conns, merge_resposta["name"], respond["name"], 0, 0)
    changed.append("Respond to Webhook: JSON de resposta consolidado e ligado ao contexto final")

    vision = find_node(nodes, "Ollama Vision (Imagem)")
    vision_params = vision.setdefault("parameters", {})
    endpoint = ""
    for key in ("url", "endpoint", "requestUrl", "baseURL"):
        val = vision_params.get(key)
        if isinstance(val, str) and val:
            endpoint = val
            break
    if "host.docker.internal" in endpoint:
        upsert_notes(
            vision,
            "Em Linux/Docker, se host.docker.internal falhar, use http://172.17.0.1:11434/api/chat.",
        )
        changed.append("Ollama Vision (Imagem): adicionada observação de endpoint alternativo 172.17.0.1")

    path.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=== SENNE workflow hotfix aplicado ===")
    print("Nodes alterados:")
    for c in changed:
        print(f"- {c}")
    print("Nodes criados:")
    if created:
        for c in created:
            print(f"- {c}")
    else:
        print("- (nenhum)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
