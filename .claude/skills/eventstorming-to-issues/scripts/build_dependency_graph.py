#!/usr/bin/env python3
"""依存グラフ Mermaid 生成

使い方:
    python3 build_dependency_graph.py <es-parsed.json> [--out <md_path>]

出力:
    - BC 全体グラフ (graph LR)
    - 集約ごとの状態遷移図 (stateDiagram-v2)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MERMAID_BAD_CHARS = re.compile(r"[（）()：:;,'\"`+]")


def sanitize_mermaid_label(text: str) -> str:
    """Mermaid stateDiagram-v2 のラベルからパース失敗の原因を除去。
    空・空白のみになった場合は None 相当として空文字を返す（呼出側でラベル無しに）。"""
    text = MERMAID_BAD_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:40]


def build_state_cmd_map(agg: dict) -> dict[tuple[str, str], str]:
    """(from, to) → CMD 英語名 のマップ。Mermaid ラベル用。"""
    m: dict[tuple[str, str], str] = {}
    for cmd in agg.get("state_transition_cmds", []):
        name = cmd.get("name", "")
        # 英語識別子っぽい場合のみ採用 (日本語フォールバック時は trigger を使う)
        if name and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            for tr in cmd.get("transitions", []):
                m[(tr["from"], tr["to"])] = name
    return m


def render_bc_graph(bcs: list[dict]) -> str:
    lines = ["```mermaid", "graph LR"]
    for bc in bcs:
        slug = bc["slug"]
        # Mermaid node id は英数のみ。kebab を underscore に変換
        node_id = slug.replace("-", "_")
        lines.append(f'    {node_id}["{slug}"]')
    seen_edges = set()
    for bc in bcs:
        src = bc["slug"].replace("-", "_")
        for up in bc.get("upstream", []):
            tgt = up.replace("-", "_")
            edge = (tgt, src)  # Upstream → Downstream の向き
            if edge in seen_edges or tgt == src:
                continue
            seen_edges.add(edge)
            lines.append(f"    {tgt} --> {src}")
    lines.append("```")
    return "\n".join(lines)


def render_state_diagram(agg: dict) -> str:
    transitions = agg.get("transitions", [])
    if not transitions:
        return ""
    cmd_map = build_state_cmd_map(agg)
    lines = ["```mermaid", "stateDiagram-v2"]
    froms = {t["from"] for t in transitions}
    tos = {t["to"] for t in transitions}
    initial_states = froms - tos
    for s in sorted(initial_states):
        lines.append(f"    [*] --> {s}")
    for t in transitions:
        key = (t["from"], t["to"])
        if key in cmd_map:
            label = cmd_map[key]
        else:
            label = sanitize_mermaid_label(t.get("trigger", ""))
        if not label:
            lines.append(f'    {t["from"]} --> {t["to"]}')
        else:
            lines.append(f'    {t["from"]} --> {t["to"]}: {label}')
    lines.append("```")
    return "\n".join(lines)


def render(parsed: dict) -> str:
    out = []
    sid = parsed["session_id"]
    out.append(f"# 依存グラフ — Session {sid}\n")
    out.append("> 自動生成。`build_dependency_graph.py` が再生成します。\n")

    out.append("## BC 依存関係\n")
    out.append(render_bc_graph(parsed["bcs"]))
    out.append("")

    out.append("## 集約別 状態遷移\n")
    for agg in parsed["aggregates"]:
        diagram = render_state_diagram(agg)
        if not diagram:
            continue
        out.append(f"### agg:{agg['id']} （bc:{agg['bc_slug']}）\n")
        out.append(diagram)
        out.append("")

    out.append("## AGG 跨ぎシナリオ\n")
    if parsed["cross_agg_scenarios"]:
        for c in parsed["cross_agg_scenarios"]:
            owners = ", ".join(f"`agg:{a}`" for a in c["owners"])
            cmd = f" → CMD `{c['cmd_name']}`" if c["cmd_name"] else ""
            out.append(f"- **{c['name']}**: {owners}{cmd}")
    else:
        out.append("- なし")
    out.append("")

    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("parsed_json", type=Path)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    parsed = json.loads(args.parsed_json.read_text(encoding="utf-8"))
    text = render(parsed)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
