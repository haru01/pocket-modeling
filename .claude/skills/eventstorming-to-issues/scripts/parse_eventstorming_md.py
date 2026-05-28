#!/usr/bin/env python3
"""EventStorming MD + DML → 構造化 JSON

使い方:
    python3 parse_eventstorming_md.py <md_path> [--out <json_path>]

入力:
    - `<md_path>`: セッション MD（§4 BC カード / §10 用語集 / §6 QRY 等を読む）
    - `<md_path>` の兄弟ファイル `<session>.dml.yaml`: 集約・SCENARIO・POLICY・FLOW のモデル真実源

出力 JSON は generate_issue_drafts.py / build_dependency_graph.py が消費する。
集約属性・イベントペイロード・状態遷移・不変条件・エラーはすべて DML から導出する。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
FACILITATOR_SCRIPTS = (
    PROJECT_ROOT / ".claude" / "skills" / "eventstorming-facilitator" / "scripts"
)
sys.path.insert(0, str(FACILITATOR_SCRIPTS))

from eventstorming_build import (  # noqa: E402
    aggregates_from_dml,
    build_flows_from_dml,
    build_glossary_index,
    parse_md,
)


# ============================================================
# 補助: BC slug 抽出
# ============================================================


def extract_bc_slug(name_line: str) -> str:
    """`event-planning（イベント企画）` → `event-planning`"""
    m = re.match(r"^([a-z0-9][a-z0-9-]*)", name_line)
    return m.group(1) if m else name_line


# ============================================================
# 集約データ: DML から導出
# ============================================================


def _normalize_transition(tr: dict) -> list[dict]:
    """DML transition（from/to/via/when）を generate_issue_drafts / build_dependency_graph が
    期待する `{from, to, trigger}` 形式へ展開する。

    `to` は単一 or 配列のため、配列なら各 to 先ごとに 1 エッジへ展開する。trigger は
    `via`（CMD 名）を採用し、`when` は補助情報として note に保持する。
    """
    via = tr.get("via", "")
    when = tr.get("when") or ""
    frm = tr.get("from", "")
    to = tr.get("to")
    tos: list[str] = to if isinstance(to, list) else [to] if to else []
    out: list[dict] = []
    for t in tos:
        out.append(
            {
                "from": frm,
                "to": t,
                "trigger": via,
                "when": when,
                "note": tr.get("note") or "",
            }
        )
    return out


def _classify_agg_scenarios(
    agg_name: str,
    dml_scenarios: list[dict],
    transition_cmds: set[str],
) -> tuple[list[dict], list[dict], list[str]]:
    """この AGG に属する scs[] を「状態遷移 CMD」「属性更新 CMD」「related_scenarios」に分類。

    - transition_cmds: 集約の transitions[].via に登場する CMD 名集合
    - dml_scenarios: 正規化済みシナリオ（_normalize_scenario の出力）

    返り値: (state_transition_cmds, attribute_cmds, related_scenarios)
    """
    related_scenarios: list[str] = []
    by_cmd_state: dict[str, dict] = {}
    by_cmd_attr: dict[str, dict] = {}
    for sc in dml_scenarios:
        if sc.get("agg") != agg_name:
            continue
        name = sc.get("name") or ""
        if name:
            related_scenarios.append(name)
        cmd = sc.get("cmd")
        if not cmd:
            continue
        if cmd in transition_cmds:
            entry = by_cmd_state.setdefault(
                cmd,
                {
                    "name": cmd,
                    "jp_scenario": name,
                    "jp_trigger": name,
                    "mutates_state": True,
                    "transitions": [],
                },
            )
            # transitions は後段で集約 transitions と突合して埋める
            if name and not entry.get("jp_scenario"):
                entry["jp_scenario"] = name
        else:
            by_cmd_attr.setdefault(
                cmd,
                {
                    "name": cmd,
                    "jp_scenario": name,
                    "mutates_state": False,
                },
            )
    return list(by_cmd_state.values()), list(by_cmd_attr.values()), related_scenarios


def _attach_transitions_to_state_cmds(
    state_cmds: list[dict], transitions: list[dict]
) -> None:
    """state_transition_cmds[].transitions に、対応する transitions（from/to/trigger）を埋める。

    `trigger == cmd.name` で突合する。
    """
    by_via: dict[str, list[dict]] = {}
    for tr in transitions:
        by_via.setdefault(tr["trigger"], []).append(tr)
    for c in state_cmds:
        c["transitions"] = by_via.get(c["name"], [])


def _format_invariant(r: dict | str) -> str:
    """DML rules 要素（dict or str）を表示用の 1 文字列へ。"""
    if isinstance(r, dict):
        text = (r.get("rule") or "").strip()
        why = (r.get("why") or "").strip()
        if text and why:
            return f"{text}（なぜ: {why}）"
        return text or why
    return str(r)


def _format_error(e: dict | str) -> str:
    """DML errs 要素（dict or str）を表示用の 1 文字列へ。"""
    if isinstance(e, dict):
        cond = (e.get("cond") or "").strip()
        err = (e.get("err") or "").strip()
        when = (e.get("when") or "").strip()
        head = f"{cond} → {err}" if cond and err else (cond or err)
        return f"{head}（{when}）" if when and head else head
    return str(e)


def enrich_aggregates(
    model: dict, dml_scenarios: list[dict]
) -> list[dict]:
    """DML model から集約情報を導出し、下流テンプレが期待する dict 形式へ正規化する。

    出力 dict のキー（互換維持）:
      - id: PascalCase 集約名
      - jp_name: 集約の日本語名（DML には無いので英語と同値、将来 glossary で拡張可能）
      - bc_slug: 所属 BC
      - attrs: list[{name, type, required, note}]
      - event_params: list[{event_name, params: [...]}]
      - purpose / background / constraints: DML から
      - invariants: scs[].rules を agg 一致で集約（表示用文字列リスト）
      - errors: scs[].errs を agg 一致で集約（表示用文字列リスト）
      - transitions: list[{from, to, trigger, when, note}]
      - state_transition_cmds: transitions[].via に出現する CMD のシナリオ
      - attribute_cmds: それ以外で agg を更新する scs のシナリオ
      - related_scenarios: scs[].name のリスト（agg 一致）
      - cross_agg_scenarios: 空配列（scs は単一 agg なので意味を持たない）
      - notes / derived: 空配列（DML に直接対応なし）
    """
    enriched: list[dict] = []
    for ag in aggregates_from_dml(model):
        name = ag["name"]
        # transitions を {from,to,trigger,when,note} 形式へ
        transitions: list[dict] = []
        for tr in ag.get("transitions") or []:
            transitions.extend(_normalize_transition(tr))
        transition_cmds = {tr["trigger"] for tr in transitions if tr.get("trigger")}

        state_cmds, attr_cmds, related = _classify_agg_scenarios(
            name, dml_scenarios, transition_cmds
        )
        _attach_transitions_to_state_cmds(state_cmds, transitions)

        # transitions[].via が CMD なのに対応 scs が存在しないケースも
        # state_cmds として残す（Mermaid ラベル/受け入れ条件で見えるように）
        seen_state = {c["name"] for c in state_cmds}
        for via in transition_cmds:
            if via and via not in seen_state:
                state_cmds.append(
                    {
                        "name": via,
                        "jp_scenario": "",
                        "jp_trigger": "",
                        "mutates_state": True,
                        "transitions": [
                            tr for tr in transitions if tr["trigger"] == via
                        ],
                    }
                )

        # event_params: DML aggs[].events[].params をペイロード一覧として保持
        event_params: list[dict] = []
        for ev in ag.get("events") or []:
            event_params.append(
                {
                    "event_name": ev.get("name", ""),
                    "params": list(ev.get("params") or []),
                    "note": ev.get("note") or "",
                }
            )

        enriched.append(
            {
                "id": name,
                "jp_name": name,  # DML に日本語名は無いので英語そのまま
                "name_line": name,
                "bc_slug": ag.get("ctx", ""),
                "attrs": list(ag.get("attrs") or []),
                "event_params": event_params,
                "purpose": ag.get("purpose", ""),
                "background": ag.get("background", ""),
                "constraints": list(ag.get("constraints") or []),
                "invariants": [_format_invariant(r) for r in ag.get("invariants", [])],
                "errors": [_format_error(e) for e in ag.get("errors", [])],
                "transitions": transitions,
                "state_transition_cmds": state_cmds,
                "attribute_cmds": attr_cmds,
                "cross_agg_scenarios": [],
                "related_scenarios": related,
                "notes": [],
                "derived": [],
            }
        )
    return enriched


# ============================================================
# BC データの整形（MD §4 BC カードから）
# ============================================================


def enrich_bcs(bc_cards: list[dict]) -> list[dict]:
    known_slugs = {extract_bc_slug(bc.get("name", "")) for bc in bc_cards}

    def filter_slugs(text: str) -> list[str]:
        # バッククォート囲み or 単独 token から既知の BC slug のみ抽出
        tokens = re.findall(r"`([^`]+)`|([a-z][a-z0-9-]*)", text)
        result = []
        seen: set[str] = set()
        for backtick, plain in tokens:
            tok = backtick or plain
            tok = tok.strip()
            if tok in known_slugs and tok not in seen:
                result.append(tok)
                seen.add(tok)
        return result

    return [
        {
            "slug": extract_bc_slug(bc.get("name", "")),
            "name_line": bc.get("name", ""),
            "reason": bc.get("reason", ""),
            "upstream": filter_slugs(bc.get("upstream", "")),
            "downstream": filter_slugs(bc.get("downstream", "")),
            "languages": bc.get("languages", []),
            "purpose": bc.get("purpose", ""),
            "background": bc.get("background", ""),
            "constraints": bc.get("constraints", []),
        }
        for bc in bc_cards
    ]


def attach_queries_to_aggregates(
    aggregates: list[dict], qry_cards: list[dict]
) -> tuple[list[dict], list[dict]]:
    """QRY カードを AGG に紐付ける（最初のヒットしたAGGに）。残りは未紐付けとして返す。"""
    agg_by_id = {a["id"]: a for a in aggregates}
    for a in aggregates:
        a["queries"] = []

    unattached: list[dict] = []
    for qry in qry_cards:
        qry_name = re.match(r"^([A-Za-z][A-Za-z0-9]*)", qry.get("name", ""))
        qry_id = qry_name.group(1) if qry_name else qry.get("name", "")
        # 名前に集約名が含まれているかでざっくり紐付け
        attached = False
        for agg_id, agg in agg_by_id.items():
            if agg_id in qry_id or agg_id in qry.get("source", ""):
                agg["queries"].append({"id": qry_id, **qry})
                attached = True
                break
        if not attached:
            unattached.append({"id": qry_id, **qry})

    return aggregates, unattached


# ============================================================
# DML（YAML）から SCENARIO / POLICY を抽出
# ============================================================


def parse_dml_blocks(dml_text: str) -> dict:
    """DML（YAML）テキストから scenarios / policies を抽出する。

    YAML を `yaml.safe_load` で読み、下流スクリプト（generate_issue_drafts.py /
    build_dependency_graph.py）が消費する既存の dict 構造へ正規化して返す。
    返り値: {"scenarios": [...], "policies": [...], "model": <yaml dict>}

    （CONTEXT/BC は `## コンテキスト候補` カードから取得するため、ここでは
    YAML の `contexts` は読まない＝旧テキスト DML と同じ役割分担を維持する）
    """
    if not dml_text.strip():
        return {"scenarios": [], "policies": [], "model": {}}
    data = yaml.safe_load(dml_text)
    if not isinstance(data, dict):
        return {"scenarios": [], "policies": [], "model": {}}
    scenarios = [
        _normalize_scenario(s) for s in (data.get("scs") or []) if isinstance(s, dict)
    ]
    policies = [
        _normalize_policy(p) for p in (data.get("pols") or []) if isinstance(p, dict)
    ]
    return {"scenarios": scenarios, "policies": policies, "model": data}


def _as_list(value) -> list[str]:
    """str / list / None を文字列リストへ正規化する。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _normalize_scenario(s: dict) -> dict:
    """YAML scenario dict を既存 dict 構造へ正規化する。

    - `evt`（単一）と `branches[].evt` をまとめて `events` に
    - `pol` / `policies` と `branches[].pol` を `policies` に
    - `rules: [{rule, why, note}]` → `[{text, notes, why}]`
    - `errors: [{condition, error, when, note}]` → `[{text: "cond → Error", notes, when}]`
    """
    events: list[dict] = []
    if s.get("evt"):
        events.append({"name": s["evt"], "notes": []})

    policies = _as_list(s.get("pol"))

    for br in s.get("brs") or []:
        if not isinstance(br, dict):
            continue
        if br.get("evt"):
            events.append({"name": br["evt"], "notes": []})
        policies.extend(_as_list(br.get("pol")))

    rules: list[dict] = []
    for r in s.get("rules") or []:
        if isinstance(r, str):
            rules.append({"text": r, "notes": [], "why": None})
        elif isinstance(r, dict):
            note = r.get("note")
            rules.append(
                {
                    "text": r.get("rule", ""),
                    "notes": [note] if note else [],
                    "why": r.get("why"),
                }
            )

    errors: list[dict] = []
    for e in s.get("errs") or []:
        if isinstance(e, str):
            errors.append({"text": e, "notes": [], "when": None})
        elif isinstance(e, dict):
            cond = str(e.get("cond", "")).strip()
            err = str(e.get("err", "")).strip()
            text = f"{cond} → {err}" if cond and err else (cond or err)
            note = e.get("note")
            errors.append(
                {
                    "text": text,
                    "notes": [note] if note else [],
                    "when": e.get("when"),
                }
            )

    return {
        "name": s.get("name", ""),
        "context": s.get("ctx"),
        "actor": s.get("actor"),
        "cmd": s.get("cmd"),
        "events": events,
        "branch_mode": s.get("brMode"),   # v2: exclusive/concurrent/inclusive（brs 時）
        "agg": s.get("agg"),
        "rules": rules,
        "errors": errors,
        "policies": policies,
        "notes": _as_list(s.get("note") or s.get("notes")),
    }


def _normalize_policy(p: dict) -> dict:
    """YAML policy dict を既存 dict 構造へ正規化する。

    `trigger`（v1・単一 EVT）に加え、v2 の `triggers: {events: [...], mode}`（join）も
    取り込む。下流（route_policies）が単一・複数の両方を扱えるよう、全トリガー EVT を
    `trigger_events`（リスト）に統一しつつ、`trigger`（単一・後方互換）も保持する。
    """
    qry = p.get("qry")
    if isinstance(qry, list):
        qry = qry[0] if qry else None

    single = p.get("trg")
    triggers_obj = p.get("trgs")
    trigger_events: list[str] = [single] if single else []
    trigger_mode = None
    if isinstance(triggers_obj, dict):
        trigger_events.extend(
            t for t in (triggers_obj.get("evts") or []) if t
        )
        trigger_mode = triggers_obj.get("mode")

    return {
        "name": p.get("name", ""),
        "context": p.get("ctx"),
        "trigger": single,                 # v1 後方互換（join のみの場合は None）
        "trigger_events": trigger_events,   # v1+v2 を統一した全トリガー EVT
        "trigger_mode": trigger_mode,       # exclusive/concurrent/inclusive（join 時）
        "qry": qry,
        "cmd": p.get("cmd"),
        "bulk": bool(p.get("bulk", False)),
        "emits": p.get("evt"),
        "notes": _as_list(p.get("note") or p.get("notes")),
    }


# ============================================================
# main
# ============================================================


def build_session_id(md_path: Path) -> str:
    """eventstorming-20260515-1901.md → 20260515-1901"""
    name = md_path.stem
    if name.startswith("eventstorming-"):
        return name[len("eventstorming-"):]
    return name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("md_path", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                        help="出力 JSON のパス（省略時は stdout）")
    args = parser.parse_args()

    md_text = args.md_path.read_text(encoding="utf-8")
    sections = parse_md(md_text)

    # DML はサイドカー `<session>.dml.yaml`（純 YAML）を優先。
    # 無ければ §9 の埋め込み ```dml フェンスから抽出済みの sections.dml にフォールバック。
    dml_path = args.md_path.with_name(args.md_path.stem + ".dml.yaml")
    dml_text = dml_path.read_text(encoding="utf-8") if dml_path.exists() else (sections.dml or "")
    # JSON Schema 検証（警告のみ・non-blocking）。違反があっても Issue 生成は続行する。
    # validate_dml が無い／スキーマが無い場合は静かにスキップ（疎結合）。
    try:
        from validate_dml import validate_dml_text  # facilitator scripts（sys.path 済）

        for e in validate_dml_text(dml_text):
            print(f"⚠ DML schema: {dml_path.name}: {e}", file=sys.stderr)
    except Exception:
        pass
    dml_blocks = parse_dml_blocks(dml_text)
    model = dml_blocks["model"]

    # 集約・QRY・BC は DML / MD から組み立てる
    aggregates = enrich_aggregates(model, dml_blocks["scenarios"])
    aggregates, unattached_qrys = attach_queries_to_aggregates(
        aggregates, sections.qry_cards
    )
    bcs = enrich_bcs(sections.bc_cards)

    # FLOW: DML の flows[]+scs/pols から Lane/Note 形式を組み立て
    glossary_index = build_glossary_index(sections.glossary)
    flows = build_flows_from_dml(model, glossary_index) if model else []

    # AGG 跨ぎ SCENARIO: DML scs[] は単一 agg なので空配列で出す
    # （ポリシー連鎖の cross-agg 検出は将来拡張・現状は空にして下流テンプレが
    # 「なし」と表示するようにする）
    cross_agg: list[dict] = []

    result = {
        "session_id": build_session_id(args.md_path),
        "source_path": str(args.md_path),
        "header": sections.header,
        "bcs": bcs,
        "aggregates": aggregates,
        "cross_agg_scenarios": cross_agg,
        "unattached_queries": unattached_qrys,
        "dml_scenarios": dml_blocks["scenarios"],
        "policies": dml_blocks["policies"],
        "flows": [
            {
                "title": f.title,
                "lanes": [
                    {
                        "bc_name": ln.bc_name,
                        "description": ln.description,
                        "notes": [asdict(n) for n in ln.notes],
                        "joins_into_next": ln.joins_into_next,
                    }
                    for ln in f.lanes
                ],
            }
            for f in flows
        ],
        "scenarios": sections.scenarios,
        "glossary": sections.glossary,
        "dml": dml_text,
    }

    out_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(out_text, encoding="utf-8")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
