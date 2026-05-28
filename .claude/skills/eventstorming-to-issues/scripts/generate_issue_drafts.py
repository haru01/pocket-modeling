#!/usr/bin/env python3
"""Issue ドラフト MD 生成

使い方:
    python3 generate_issue_drafts.py <es-parsed.json> --output docs/issues/<session-id>/

出力:
    - epics/<bc>__<AGG>.md              AGG Epic（self-contained: CMD/QRY/POLICY 詳細を inline）
    - integration/<scenario>.md          AGG 跨ぎ統合 SCENARIO
    - cross-bc/saga-*.md                Cross-BC Saga (現状未実装、将来拡張)
    - _index.md, _labels.md, _state.json

設計: 1 AGG = 1 Epic = 1 PR を AI エージェントにごっそり任せる粒度。CMD/QRY 単位の
Sub-issue は廃止（Epic 本文に inline）。AGG 跨ぎは integration Issue で別建て。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ============================================================
# es-key / file slug
# ============================================================


def eskey_agg(bc: str, agg: str) -> str:
    return f"bc/{bc}/agg/{agg}"


def eskey_cmd(bc: str, agg: str, cmd: str) -> str:
    return f"bc/{bc}/agg/{agg}/cmd/{cmd}"


def eskey_qry(bc: str, agg: str, qry: str) -> str:
    return f"bc/{bc}/agg/{agg}/qry/{qry}"


def eskey_scenario(bcs: list[str], name: str) -> str:
    return f"bc/{'+'.join(sorted(bcs))}/scenario/{slug_name(name)}"


def slug_name(s: str) -> str:
    """日本語/英語混在から安全なファイル名スラッグを作る"""
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    return s[:60] or "untitled"


def safe_filename(s: str) -> str:
    """ファイル名に使える形に変換 (ASCII 化はしない、日本語も許容)"""
    return slug_name(s)


# ============================================================
# POLICY ルーティング (DML SCENARIO から CMD/EVT → AGG マップ構築)
# ============================================================


def build_cmd_to_agg_map(dml_scenarios: list[dict]) -> dict[str, str]:
    """DML SCENARIO の CMD → AGG 紐付けマップ"""
    m: dict[str, str] = {}
    for s in dml_scenarios:
        cmd = s.get("cmd")
        agg = s.get("agg")
        if cmd and agg and cmd not in m:
            m[cmd] = agg
    return m


def build_evt_to_agg_map(dml_scenarios: list[dict]) -> dict[str, str]:
    """DML SCENARIO の EVT → AGG 紐付けマップ（EVT を発火する AGG を特定）"""
    m: dict[str, str] = {}
    for s in dml_scenarios:
        agg = s.get("agg")
        if not agg:
            continue
        for evt in s.get("events", []):
            name = evt.get("name") if isinstance(evt, dict) else evt
            if name and name not in m:
                m[name] = agg
    return m


def build_agg_to_bc_map(aggregates: list[dict]) -> dict[str, str]:
    return {a["id"]: a["bc_slug"] for a in aggregates}


def route_policies(parsed: dict) -> dict[str, dict[str, list[dict]]]:
    """POLICY を AGG 別に振り分ける。

    返り値: agg_id → {
        "inbound": [{policy, source_agg, source_bc, target_cmd, cross_bc, ...}],
        "outbound_consumers": [{evt, policy, target_agg, target_bc, cross_bc, ...}],
        "side_effects": [{policy, trigger_evt, ...}]
    }
    """
    dml_scenarios = parsed.get("dml_scenarios", [])
    policies = parsed.get("policies", [])
    cmd_to_agg = build_cmd_to_agg_map(dml_scenarios)
    evt_to_agg = build_evt_to_agg_map(dml_scenarios)
    agg_to_bc = build_agg_to_bc_map(parsed.get("aggregates", []))

    routed: dict[str, dict[str, list[dict]]] = {}

    def slot(agg_id: str) -> dict[str, list[dict]]:
        return routed.setdefault(
            agg_id, {"inbound": [], "outbound_consumers": [], "side_effects": [], "unresolved": []}
        )

    for p in policies:
        cmd = p.get("cmd")
        # v1 `trigger`（単一）と v2 `triggers`（join）を統一。trigger_events が
        # 無い古い JSON でも trigger 単一にフォールバックする。
        trigger_evts = p.get("trigger_events")
        if not trigger_evts:
            trigger_evts = [p["trigger"]] if p.get("trigger") else []
        # 各トリガー EVT → source_agg を解決（join では複数の発火元を持ちうる）
        resolved = [(t, evt_to_agg.get(t)) for t in trigger_evts]
        source_aggs = [(t, sa) for t, sa in resolved if sa]
        primary_source = source_aggs[0][1] if source_aggs else None
        primary_source_bc = agg_to_bc.get(primary_source) if primary_source else None
        target_agg = cmd_to_agg.get(cmd) if cmd else None
        target_bc = agg_to_bc.get(target_agg) if target_agg else None

        if cmd and target_agg:
            slot(target_agg)["inbound"].append(
                {
                    "policy": p,
                    "source_agg": primary_source,
                    "source_bc": primary_source_bc,
                    "target_cmd": cmd,
                    "cross_bc": bool(
                        primary_source_bc and target_bc and primary_source_bc != target_bc
                    ),
                }
            )
            # join では各発火元 AGG に outbound consumer を記録する
            for t, sa in source_aggs:
                sa_bc = agg_to_bc.get(sa)
                slot(sa)["outbound_consumers"].append(
                    {
                        "policy": p,
                        "evt": t,
                        "target_agg": target_agg,
                        "target_bc": target_bc,
                        "cross_bc": bool(sa_bc and target_bc and sa_bc != target_bc),
                    }
                )
        elif source_aggs:
            # 副作用専用 POLICY (CMD なし)。各発火元に記録。
            for t, sa in source_aggs:
                slot(sa)["side_effects"].append(
                    {
                        "policy": p,
                        "trigger_evt": t,
                    }
                )
        else:
            # 解決できなかった POLICY は記録しておく
            slot("__unresolved__")["unresolved"].append({"policy": p})

    return routed


def build_agg_evt_index(parsed: dict) -> dict[str, list[dict]]:
    """AGG → そのAGGが発火する EVT 一覧 (DML SCENARIO 経由)"""
    out: dict[str, list[dict]] = {}
    for s in parsed.get("dml_scenarios", []):
        agg = s.get("agg")
        cmd = s.get("cmd")
        if not agg:
            continue
        for evt in s.get("events", []):
            name = evt.get("name") if isinstance(evt, dict) else evt
            if not name:
                continue
            out.setdefault(agg, []).append({"name": name, "via_cmd": cmd})
    return out


# ============================================================
# テンプレ
# ============================================================


from build_dependency_graph import render_state_diagram as _render_state_diagram_for_agg  # type: ignore


def render_state_diagram_for_agg(agg: dict) -> str:
    """CMD 名でラベル付けされた Mermaid 図 (共通実装)"""
    return _render_state_diagram_for_agg(agg)


def find_dml_scenario(cmd_name: str, dml_scenarios: list[dict]) -> dict | None:
    """CMD 名から DML SCENARIO を逆引き"""
    for s in dml_scenarios:
        if s.get("cmd") == cmd_name:
            return s
    return None


def render_cmd_detail(cmd: dict, dml_scenarios: list[dict]) -> str:
    """CMD 詳細インラインブロックを Markdown で返す"""
    name = cmd["name"]
    transitions = cmd.get("transitions") or []
    arrows = ", ".join(f"`{t['from']}` → `{t['to']}`" for t in transitions)
    title_suffix = f" — {arrows}" if arrows else ""
    scenario = find_dml_scenario(name, dml_scenarios)

    lines = [f"### `{name}`{title_suffix}"]

    if cmd.get("jp_scenario") or cmd.get("jp_trigger"):
        lines.append(f"- **由来シナリオ**: {cmd.get('jp_scenario') or cmd.get('jp_trigger')}")

    if scenario:
        actor = scenario.get("actor")
        if actor:
            lines.append(f"- **アクター**: `{actor}`")
        evts = [e.get("name") if isinstance(e, dict) else e for e in scenario.get("events", [])]
        if evts:
            lines.append(f"- **発火 EVT**: " + ", ".join(f"`{e}`" for e in evts))
        rules = scenario.get("rules", [])
        if rules:
            lines.append(f"- **適用 RULE**:")
            for r in rules:
                if isinstance(r, dict):
                    text = r.get("text")
                    why = r.get("why")
                else:
                    text = r
                    why = None
                lines.append(f"  - {text}")
                if why:
                    lines.append(f"    - **なぜ必要か**: {why}")
        errors = scenario.get("errors", [])
        if errors:
            lines.append(f"- **想定 ERR**:")
            for e in errors:
                if isinstance(e, dict):
                    text = e.get("text")
                    when = e.get("when")
                else:
                    text = e
                    when = None
                lines.append(f"  - {text}")
                if when:
                    lines.append(f"    - **発生条件**: {when}")
        pols = scenario.get("policies", [])
        if pols:
            lines.append(f"- **連鎖 POLICY**: " + ", ".join(f"`{p}`" for p in pols))
        if scenario.get("notes"):
            lines.append(f"- メモ: " + " / ".join(scenario["notes"]))
    else:
        lines.append("- (DML SCENARIO 未紐付け — 入力/EVT/RULE は AGG schema と不変条件から推定)")

    return "\n".join(lines)


def render_qry_detail(qry: dict) -> str:
    name = qry.get("id") or qry.get("name", "?")
    lines = [f"### `{name}`"]
    if qry.get("purpose"):
        lines.append(f"- **目的**: {qry['purpose']}")
    if qry.get("user"):
        lines.append(f"- **利用者**: {qry['user']}")
    if qry.get("source"):
        lines.append(f"- **ソース**: {qry['source']}")
    if qry.get("calc"):
        lines.append(f"- **算出**: {qry['calc']}")
    return "\n".join(lines)


def render_inbound_policies(items: list[dict]) -> str:
    if not items:
        return "（なし — この AGG は他 AGG/BC からの EVT 駆動を持たない）"
    blocks = []
    for it in items:
        p = it["policy"]
        head = f"### `{p['name']}`"
        if it.get("cross_bc"):
            head += " ⚠ **cross-BC**"
        lines = [head]
        src = it.get("source_agg") and f"`agg:{it['source_agg']}` (`bc:{it.get('source_bc') or '?'}`)"
        lines.append(f"- **TRIGGER EVT**: `{p.get('trigger')}` ← {src or '(発生元未解決)'}")
        if p.get("qry"):
            lines.append(f"- **QRY** (BULK 対象選択): `{p['qry']}`")
        lines.append(f"- **発火 CMD** (この AGG 内): `{p.get('cmd')}`")
        lines.append(f"- **BULK**: {'true' if p.get('bulk') else 'false'}")
        if p.get("emits"):
            lines.append(f"- **発火 EVT**: `{p['emits']}`")
        if p.get("notes"):
            lines.append(f"- メモ: " + " / ".join(p["notes"]))
        if it.get("cross_bc"):
            lines.append("- **実装**: cross-BC は adapter/port パターンで分離し、上流 BC への直接依存を作らない")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_outbound_evts(
    agg_id: str, agg_evt_index: dict[str, list[dict]], outbound_consumers: list[dict]
) -> str:
    evts = agg_evt_index.get(agg_id, [])
    if not evts:
        return "（なし — DML SCENARIO で EVT 紐付けが見つからない）"

    # consumer を EVT 名でグループ化
    by_evt: dict[str, list[dict]] = {}
    for c in outbound_consumers:
        by_evt.setdefault(c["evt"], []).append(c)

    seen: set[str] = set()
    blocks = []
    for e in evts:
        name = e["name"]
        if name in seen:
            continue
        seen.add(name)
        via = e.get("via_cmd")
        lines = [f"### EVT `{name}`"]
        if via:
            lines.append(f"- **発火 CMD** (この AGG 内): `{via}`")
        consumers = by_evt.get(name, [])
        if consumers:
            lines.append(f"- **消費 POLICY**:")
            for c in consumers:
                p = c["policy"]
                mark = " ⚠ cross-BC" if c.get("cross_bc") else ""
                lines.append(
                    f"  - `{p['name']}` → `agg:{c['target_agg']}.{p.get('cmd')}` (`bc:{c.get('target_bc') or '?'}`){mark}"
                )
        else:
            lines.append("- 消費 POLICY: （現状なし — 観測用 EVT、または下流未モデル）")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_side_effect_policies(items: list[dict]) -> str:
    if not items:
        return ""
    blocks = ["## 副作用専用 POLICY (この AGG の EVT を観測、CMD は発火しない)\n"]
    for it in items:
        p = it["policy"]
        lines = [f"### `{p['name']}`"]
        lines.append(f"- **TRIGGER**: `{p.get('trigger')}` (この AGG 発)")
        if p.get("qry"):
            lines.append(f"- **QRY**: `{p['qry']}`")
        if p.get("emits"):
            lines.append(f"- **観測 EVT**: `{p['emits']}`")
        if p.get("notes"):
            lines.append(f"- メモ: " + " / ".join(p["notes"]))
        lines.append("- 実装: 外部通知サービス等の adapter 経由、AGG 状態は変更しない")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


MODULE_STRUCTURE_TEMPLATE = """```
src/<bc>/<aggregate>/
  index.ts       — Aggregate root + 不変条件
  schema.ts      — 属性スキーマ（attrs[] を実装言語の型/バリデータへ）
  commands/      — 1 CMD = 1 file
  queries/       — 1 QRY = 1 file
  events.ts      — EVT 定義（aggs[].events[].params をペイロード型へ）
  errors.ts      — ERR 定義
  policies.ts    — 受信 POLICY ハンドラ
tests/<bc>/<aggregate>/<aggregate>.spec.ts
```"""


def render_state_cmd_table(state_cmds: list[dict]) -> str:
    if not state_cmds:
        return "（なし）"
    rows = ["| from | to | CMD | Issue | RULE |", "|---|---|---|---|---|"]
    for c in state_cmds:
        for tr in c["transitions"]:
            rows.append(
                f"| `{tr['from']}` | `{tr['to']}` | `{c['name']}` | (未起票) | {tr.get('trigger', '')} |"
            )
    return "\n".join(rows)


def render_attr_cmd_table(attr_cmds: list[dict]) -> str:
    if not attr_cmds:
        return "（なし）"
    rows = ["| CMD | 由来シナリオ | Issue |", "|---|---|---|"]
    for c in attr_cmds:
        rows.append(f"| `{c['name']}` | {c.get('jp_scenario', '')} | (未起票) |")
    return "\n".join(rows)


def render_qry_table(queries: list[dict]) -> str:
    if not queries:
        return "（なし）"
    rows = ["| QRY | 目的 | Issue |", "|---|---|---|"]
    for q in queries:
        rows.append(f"| `{q['id']}` | {q.get('purpose', '')} | (未起票) |")
    return "\n".join(rows)


def render_attrs(attrs: list[dict]) -> str:
    """DML aggs[].attrs[] を Markdown テーブルで描画する。

    各要素は `{name, type?, required?, note?}`。下流（実装担当 AI エージェント）が
    そのまま型/バリデータへ落とせる粒度で表示する。
    """
    if not attrs:
        return "_（DML aggs[].attrs[] 未記載 — `<session>.dml.yaml` の該当 AGG に追記）_"
    rows = ["| 属性 | 型 | 必須 | メモ |", "|---|---|---|---|"]
    for a in attrs:
        name = a.get("name", "")
        type_ = a.get("type", "")
        req = "✓" if a.get("required") else ""
        note = (a.get("note") or "").replace("|", "\\|")
        rows.append(f"| `{name}` | `{type_}` | {req} | {note} |")
    return "\n".join(rows)


def render_event_params(event_params: list[dict]) -> str:
    """DML aggs[].events[].params をイベントごとに表示する。"""
    if not event_params:
        return "_（DML aggs[].events[] 未記載 — `<session>.dml.yaml` の該当 AGG に追記）_"
    blocks: list[str] = []
    for ev in event_params:
        name = ev.get("event_name", "")
        params = ev.get("params") or []
        note = (ev.get("note") or "").strip()
        head = f"### EVT `{name}`"
        if note:
            head += f" — {note}"
        if not params:
            blocks.append(f"{head}\n- _ペイロード未記載_")
            continue
        rows = [head, "", "| 属性 | 型 | 必須 | メモ |", "|---|---|---|---|"]
        for p in params:
            pname = p.get("name", "")
            ptype = p.get("type", "")
            preq = "✓" if p.get("required") else ""
            pnote = (p.get("note") or "").replace("|", "\\|")
            rows.append(f"| `{pname}` | `{ptype}` | {preq} | {pnote} |")
        blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


def render_invariants(items: list[str]) -> str:
    if not items:
        return "- （なし）"
    return "\n".join(f"- {x}" for x in items)


def render_errors(items: list[str]) -> str:
    if not items:
        return "- （なし）"
    return "\n".join(f"- {x}" for x in items)


_MISSING_PROSE_PLACEHOLDER = (
    "_（未記載 — 元 MD の §5 集約候補カードに `#### 目的` / `#### 背景` / `#### 制約` を追記してから再生成）_"
)


def render_business_context(agg: dict, bc_data: dict) -> str:
    """AGG Epic の「ビジネス背景と制約」セクション本文を Markdown で返す。

    AGG レベルの purpose / background / constraints を主、BC レベルがあれば
    末尾に「BC 共通の方針」として転載する。未記載は明示的プレースホルダ。
    """
    purpose = (agg.get("purpose") or "").strip()
    background = (agg.get("background") or "").strip()
    constraints = agg.get("constraints") or []

    lines: list[str] = []
    lines.append("### 目的")
    lines.append(purpose if purpose else _MISSING_PROSE_PLACEHOLDER)
    lines.append("")
    lines.append("### 背景")
    lines.append(background if background else "_（未記載）_")
    lines.append("")
    lines.append("### 制約")
    if constraints:
        for c in constraints:
            lines.append(f"- {c}")
    else:
        lines.append("- _（未記載）_")

    bc_purpose = (bc_data.get("purpose") or "").strip()
    bc_background = (bc_data.get("background") or "").strip()
    bc_constraints = bc_data.get("constraints") or []
    if bc_purpose or bc_background or bc_constraints:
        lines.append("")
        lines.append(f"### BC 共通の方針 (`bc:{bc_data.get('slug', '')}`)")
        if bc_purpose:
            lines.append(f"- 目的: {bc_purpose}")
        if bc_background:
            lines.append(f"- 背景: {bc_background}")
        if bc_constraints:
            lines.append("- 制約:")
            for c in bc_constraints:
                lines.append(f"  - {c}")

    return "\n".join(lines)


def epic_title(bc: str, agg_id: str, agg_jp: str) -> str:
    suffix = f"（{agg_jp}）" if agg_jp else ""
    return f"[bc:{bc}][agg:{agg_id}] {agg_id} 集約{suffix}"


def epic_body(
    agg: dict,
    bcs: dict[str, dict],
    dml_scenarios: list[dict],
    routed_policies: dict,
    agg_evt_index: dict[str, list[dict]],
    integration_for_agg: list[dict],
) -> str:
    eskey = eskey_agg(agg["bc_slug"], agg["id"])
    bc = agg["bc_slug"]
    agg_id = agg["id"]
    transitions = agg.get("transitions", [])

    states = sorted({t["from"] for t in transitions} | {t["to"] for t in transitions})
    state_list = " | ".join(f"`{s}`" for s in states) if states else "（なし）"

    state_cmds = agg.get("state_transition_cmds", [])
    attr_cmds = agg.get("attribute_cmds", [])
    queries = agg.get("queries", [])

    state_cmd_details = "\n\n".join(render_cmd_detail(c, dml_scenarios) for c in state_cmds) or "（なし）"
    attr_cmd_details = "\n\n".join(render_cmd_detail(c, dml_scenarios) for c in attr_cmds) or "（なし）"
    qry_details = "\n\n".join(render_qry_detail(q) for q in queries) or "（なし）"

    pol_slot = routed_policies.get(agg_id, {})
    inbound_md = render_inbound_policies(pol_slot.get("inbound", []))
    outbound_md = render_outbound_evts(
        agg_id, agg_evt_index, pol_slot.get("outbound_consumers", [])
    )
    side_effect_md = render_side_effect_policies(pol_slot.get("side_effects", []))

    inbound_sources = sorted({
        f"`agg:{it['source_agg']}`" for it in pol_slot.get("inbound", []) if it.get("source_agg")
    })
    upstream_bcs = bcs.get(bc, {}).get("upstream", [])
    depends_lines = []
    if upstream_bcs:
        depends_lines.append(
            f"- 上流 BC: " + ", ".join(f"`bc:{u}`" for u in upstream_bcs)
        )
    if inbound_sources:
        depends_lines.append(
            f"- 受信 POLICY 発生元 AGG: " + ", ".join(inbound_sources)
        )
    if integration_for_agg:
        depends_lines.append(
            f"- 統合 Issue: "
            + ", ".join(f"`integration/{safe_filename(s['name'])}.md`" for s in integration_for_agg)
        )
    if not depends_lines:
        depends_lines.append("- なし")

    integration_md = (
        "\n".join(
            f"- `integration/{safe_filename(s['name'])}.md` — {s['name']}（他参加 AGG: "
            + ", ".join(f"`agg:{o}`" for o in s["owners"] if o != agg_id)
            + "）"
            for s in integration_for_agg
        )
        if integration_for_agg
        else "- （なし）"
    )

    body = f"""<!-- es-key: {eskey} -->

## 実装担当範囲
- **BC (大項目)**: `bc:{bc}`
- **AGG (中項目)**: `agg:{agg_id}`
- **スコープ**: この AGG の全 CMD / QRY / 受信 POLICY を 1 PR で実装
- **原則**: 1 AGG = 1 オーナー = 1 PR (AI エージェント 1 担当)
- **本 Epic 外**: AGG 跨ぎ統合 Issue で扱う処理は別 Issue（下記「AGG 跨ぎ統合 Issue への参加」参照）

## Aggregate 概要
{agg.get('jp_name') or agg_id} 集約。

## ビジネス背景と制約

{render_business_context(agg, bcs.get(bc, {}))}

## 属性 (DML aggs[].attrs[])

{render_attrs(agg.get('attrs', []))}

## イベントペイロード (DML aggs[].events[].params)

{render_event_params(agg.get('event_params', []))}

## 不変条件 (RULE)
{render_invariants(agg.get('invariants', []))}

## エラー (ERR)
{render_errors(agg.get('errors', []))}

## 状態モデル

状態: {state_list}

## 状態遷移 (State Transitions)

{render_state_diagram_for_agg(agg)}

## 状態遷移を起こす CMD（一覧）

{render_state_cmd_table(state_cmds)}

## 状態遷移を起こす CMD（詳細）

{state_cmd_details}

## 状態を変えない CMD（属性更新・一覧）

{render_attr_cmd_table(attr_cmds)}

## 状態を変えない CMD（詳細）

{attr_cmd_details}

## QRY（読み出し口・詳細）

{qry_details}

## 受信 POLICY (inbound: 他 AGG / BC の EVT に反応してこの AGG の CMD を発火)

{inbound_md}

## 発信イベント (outbound: この AGG が発火する EVT とその消費先)

{outbound_md}

{side_effect_md}## 推奨モジュール構造

{MODULE_STRUCTURE_TEMPLATE}

## 受け入れ条件
- [ ] 属性スキーマ（attrs[]）が Epic 記載の型/必須と一致
- [ ] イベントペイロード（events[].params）が Epic 記載と一致
- [ ] 状態遷移図の全エッジが実装されテストでカバー
- [ ] 全不変条件 (RULE) が enforce され、違反時に Epic 記載の ERR が発火
- [ ] 全 CMD / QRY が公開 API として動作
- [ ] 受信 POLICY 全件のハンドラが実装され、テストで TRIGGER EVT → CMD 発火が検証されている
- [ ] 発信 EVT 全件が CMD 成功時に確実に publish され、ペイロード schema が一致
- [ ] POLICY の冪等性（重複 EVT 受信時の重複 CMD 防止）がテストでカバー
- [ ] 上流 BC との依存が adapter / port パターンで分離（cross-BC POLICY 含む）
- [ ] AGG 跨ぎ統合 Issue で扱う処理は本 Epic 外（参照 link のみ）

## AGG 跨ぎ統合 Issue への参加
{integration_md}

## Depends on
{chr(10).join(depends_lines)}

## Source
- セッション MD: `{agg.get('source_path') or 'docs/eventstorming/eventstorming-' + (agg.get('session_id') or '') + '.md'}`
"""
    return body


def render_sub_issue_checklist(agg: dict) -> str:
    items = []
    for c in agg.get("state_transition_cmds", []):
        items.append(f"- [ ] CMD `{c['name']}` (mutates-state)")
    for c in agg.get("attribute_cmds", []):
        items.append(f"- [ ] CMD `{c['name']}`")
    for q in agg.get("queries", []):
        items.append(f"- [ ] QRY `{q['id']}`")
    return "\n".join(items) if items else "- （なし）"


def render_cross_participation(agg: dict) -> str:
    scens = agg.get("cross_agg_scenarios", [])
    if not scens:
        return "- （なし）"
    return "\n".join(f"- {s}" for s in scens)


def cmd_title(bc: str, agg: str, cmd: dict) -> str:
    if cmd.get("mutates_state"):
        tt = cmd.get("transitions", [])
        if tt:
            arrows = ",".join(f"{t['from']}→{t['to']}" for t in tt)
            return f"[bc:{bc}][agg:{agg}] {cmd['name']} ({arrows})"
    return f"[bc:{bc}][agg:{agg}] {cmd['name']}"


def cmd_body(bc: str, agg_id: str, cmd: dict, scenarios: list[dict]) -> str:
    eskey = eskey_cmd(bc, agg_id, cmd["name"])
    transitions_md = ""
    if cmd.get("mutates_state") and cmd.get("transitions"):
        lines = [f"- `{t['from']}` → `{t['to']}`" for t in cmd["transitions"]]
        transitions_md = "## 状態遷移\n" + "\n".join(lines) + "\n"

    # SCENARIO 本文を引く
    scenario_text = ""
    scenario_name = cmd.get("jp_scenario") or cmd.get("jp_trigger") or ""
    for s in scenarios:
        if s.get("name") == scenario_name:
            scenario_text = s.get("text", "")
            break

    return f"""<!-- es-key: {eskey} -->

## Owner BC
`bc:{bc}`

## 対象集約
`agg:{agg_id}`（Epic: 未起票）

{transitions_md}
## 概要
{scenario_name or '(SCENARIO 名未解決 — MD をレビューして補完してください)'}

{scenario_text}

## 入力 (Command Schema)

- AGG `attrs[]` から本 CMD の入力に必要な属性を抜粋（型 / 必須は Epic 本文参照）

## 発火イベント (EVT)

- AGG `events[].params` から該当 EVT のペイロードを参照

## 適用される RULE
- TODO: 該当する不変条件を Epic から抜粋

## 受け入れ条件
- [ ] コマンドが受け付けられる
- [ ] バリデーションエラーが正しく返る
- [ ] イベントが発火される
- [ ] AGG `{agg_id}` に永続化される
{(_ac_state := '- [ ] 状態が `' + cmd['transitions'][0]['from'] + '` → `' + cmd['transitions'][0]['to'] + '` に変わる') if cmd.get('mutates_state') and cmd.get('transitions') else ''}

## Depends on
- なし
"""


def qry_title(bc: str, agg_id: str, qry: dict) -> str:
    name = qry.get("name", qry.get("id", ""))
    return f"[bc:{bc}][agg:{agg_id}] QRY {name}"


def qry_body(bc: str, agg_id: str, qry: dict) -> str:
    eskey = eskey_qry(bc, agg_id, qry.get("id", ""))
    return f"""<!-- es-key: {eskey} -->

## Owner BC
`bc:{bc}`

## 対象集約
`agg:{agg_id}`（Epic: 未起票）

## 概要
{qry.get('purpose', 'TODO: 用途を記入')}

## 利用者
{qry.get('user', '')}

## ソース
{qry.get('source', '')}

## 算出
{qry.get('calc', '')}

## 受け入れ条件
- [ ] 結果が期待される形式で返る
- [ ] パフォーマンス目標（必要なら）

## Depends on
- なし
"""


def scenario_title(bcs: list[str], aggs: list[str], name: str) -> str:
    bc_part = "+".join(sorted(bcs))
    agg_part = "+".join(aggs)
    return f"[bc:{bc_part}][agg:{agg_part}] {name}"


def scenario_body(scenario: dict, agg_bc_map: dict[str, str]) -> str:
    aggs = scenario["owners"]
    bcs = sorted({agg_bc_map.get(a, "?") for a in aggs})
    eskey = eskey_scenario(bcs, scenario["name"])
    return f"""<!-- es-key: {eskey} -->

## 関係する BC
{chr(10).join(f'- `bc:{b}`' for b in bcs)}

## 関係する集約
{chr(10).join(f'- `agg:{a}` (Epic: 未起票)' for a in aggs)}

## 概要
{scenario.get('text', '').strip()}

## 構成要素
- CMD: `{scenario.get('cmd_name') or '未解決'}`
- 関係する各集約の CMD / POLICY Issue を起票後にここへリンク

## 受け入れ条件
- [ ] 全 CMD が成功時に正しい順序で発火される
- [ ] 部分失敗時の整合性が保たれる

## Depends on
- 関係する集約の CMD / POLICY Issue
"""


# ============================================================
# 全体生成
# ============================================================


def labels_for_agg(bc: str, agg_id: str) -> list[str]:
    return [f"bc:{bc}", f"agg:{agg_id}", "type:aggregate"]


def labels_for_cmd(bc: str, agg_id: str, cmd: dict) -> list[str]:
    out = [f"bc:{bc}", f"agg:{agg_id}", "type:command"]
    if cmd.get("mutates_state"):
        out.append("mutates-state")
    return out


def labels_for_qry(bc: str, agg_id: str) -> list[str]:
    return [f"bc:{bc}", f"agg:{agg_id}", "type:query"]


def labels_for_scenario(bcs: list[str], aggs: list[str]) -> list[str]:
    out = [f"bc:{b}" for b in bcs] + [f"agg:{a}" for a in aggs] + ["type:scenario"]
    if len(bcs) > 1:
        out.append("cross-bc")
    return out


def collect_all_labels(parsed: dict, agg_bc_map: dict[str, str]) -> list[dict]:
    """必要な Label 集合を返す。{name, color, description}"""
    labels: dict[str, dict] = {}

    def add(name: str, color: str, desc: str):
        if name not in labels:
            labels[name] = {"name": name, "color": color, "description": desc}

    add("type:aggregate", "1D76DB", "EventStorming: 集約 Epic (AI dispatch 単位)")
    add("type:scenario", "C2E0C6", "EventStorming: AGG 跨ぎ統合シナリオ")
    add("type:saga", "D93F0B", "EventStorming: Cross-BC Saga")
    add("cross-bc", "B60205", "EventStorming: BC 横断 POLICY / Saga")

    # bc:* — HSL ハッシュで色を割り当てる
    for bc in parsed["bcs"]:
        slug = bc["slug"]
        color = bc_color(slug)
        add(f"bc:{slug}", color, f"EventStorming: BC {slug}")

    # agg:*
    for a in parsed["aggregates"]:
        add(f"agg:{a['id']}", "EDEDED", f"EventStorming: 集約 {a['id']}")

    return list(labels.values())


def bc_color(slug: str) -> str:
    """BC slug から決定論的に HEX 色を生成 (HSL ハッシュ)"""
    import hashlib

    h = int(hashlib.md5(slug.encode()).hexdigest(), 16) % 360
    # HSL(h, 50%, 70%) → RGB
    import colorsys

    r, g, b = colorsys.hls_to_rgb(h / 360.0, 0.7, 0.5)
    return f"{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


# ============================================================
# main
# ============================================================


def main():
    p = argparse.ArgumentParser()
    p.add_argument("parsed_json", type=Path)
    p.add_argument("--output", type=Path, required=True,
                   help="出力ディレクトリ (docs/issues/<session-id>/)")
    args = p.parse_args()

    parsed = json.loads(args.parsed_json.read_text(encoding="utf-8"))
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "epics").mkdir(exist_ok=True)
    (out / "integration").mkdir(exist_ok=True)
    (out / "cross-bc").mkdir(exist_ok=True)

    bcs_by_slug = {b["slug"]: b for b in parsed["bcs"]}
    agg_bc_map = {a["id"]: a["bc_slug"] for a in parsed["aggregates"]}
    dml_scenarios = parsed.get("dml_scenarios", [])
    routed_policies = route_policies(parsed)
    agg_evt_index = build_agg_evt_index(parsed)

    # 各 AGG が参加する統合 SCENARIO
    integration_by_agg: dict[str, list[dict]] = {}
    for s in parsed.get("cross_agg_scenarios", []):
        for owner in s.get("owners", []):
            integration_by_agg.setdefault(owner, []).append(s)

    summary: dict = {"epics": [], "integration": [], "labels": [], "unresolved_policies": []}

    # session_id を AGG に注入（Source 表示用）
    session_id = parsed.get("session_id", "")
    for agg in parsed["aggregates"]:
        agg.setdefault("session_id", session_id)

    for agg in parsed["aggregates"]:
        bc = agg["bc_slug"]
        agg_id = agg["id"]

        epic_path = out / "epics" / f"{bc}__{agg_id}.md"
        title = epic_title(bc, agg_id, agg.get("jp_name", ""))
        body = f"# {title}\n\n" + epic_body(
            agg,
            bcs_by_slug,
            dml_scenarios,
            routed_policies,
            agg_evt_index,
            integration_by_agg.get(agg_id, []),
        )
        epic_path.write_text(body, encoding="utf-8")
        summary["epics"].append(
            {
                "file": str(epic_path.relative_to(out)),
                "es_key": eskey_agg(bc, agg_id),
                "title": title,
                "labels": labels_for_agg(bc, agg_id),
            }
        )

    # 未解決 POLICY を warning として記録
    unresolved = routed_policies.get("__unresolved__", {}).get("unresolved", [])
    if unresolved:
        summary["unresolved_policies"] = [u["policy"]["name"] for u in unresolved]
        print(
            f"WARNING: {len(unresolved)} POLICY が AGG 解決できませんでした: "
            + ", ".join(summary["unresolved_policies"]),
            file=sys.stderr,
        )

    # --- 統合 SCENARIO ---
    for scen in parsed.get("cross_agg_scenarios", []):
        aggs = scen["owners"]
        bcs_set = sorted({agg_bc_map.get(a, "?") for a in aggs})
        path = out / "integration" / f"{safe_filename(scen['name'])}.md"
        t = scenario_title(bcs_set, aggs, scen["name"])
        b = f"# {t}\n\n" + scenario_body(scen, agg_bc_map)
        path.write_text(b, encoding="utf-8")
        summary["integration"].append(
            {
                "file": str(path.relative_to(out)),
                "es_key": eskey_scenario(bcs_set, scen["name"]),
                "title": t,
                "labels": labels_for_scenario(bcs_set, aggs),
            }
        )

    # --- ラベル ---
    labels = collect_all_labels(parsed, agg_bc_map)
    summary["labels"] = labels

    # --- _state.json (初期) ---
    state = {item["es_key"]: None for item in (
        summary["epics"] + summary["integration"]
    )}
    (out / "_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- _labels.md ---
    label_md = ["# 必要 Labels\n"]
    label_md.append("| Name | Color | Description |")
    label_md.append("|---|---|---|")
    for lab in labels:
        label_md.append(f"| `{lab['name']}` | `#{lab['color']}` | {lab['description']} |")
    (out / "_labels.md").write_text("\n".join(label_md), encoding="utf-8")

    # --- _index.md (集約別ナビ) ---
    write_index(out, parsed, summary)

    # --- dependency-graph.md ---
    from build_dependency_graph import render as render_dep_graph  # type: ignore
    (out / "dependency-graph.md").write_text(
        render_dep_graph(parsed), encoding="utf-8"
    )

    # サマリを stdout
    print(f"Generated:")
    print(f"  Epics: {len(summary['epics'])}")
    print(f"  Integration: {len(summary['integration'])}")
    print(f"  Labels: {len(labels)}")
    if summary.get("unresolved_policies"):
        print(f"  Unresolved POLICY: {len(summary['unresolved_policies'])}")
    print(f"Output: {out}")


def write_index(out: Path, parsed: dict, summary: dict):
    lines = [f"# Issue Index — Session {parsed['session_id']}\n"]
    lines.append(f"Source: `{parsed['source_path']}`\n")
    lines.append(
        "> **設計**: 大項目 = BC、中項目 = AGG。1 AGG Epic = 1 PR = AI エージェント 1 担当。\n"
        "> CMD/QRY/受信 POLICY の詳細は各 Epic に inline。AGG 跨ぎは integration Issue で別建て。\n"
    )

    # 大項目 (BC) > 中項目 (AGG) ナビ
    lines.append("## BC（大項目）× AGG（中項目）\n")
    aggs_by_bc: dict[str, list[dict]] = {}
    for agg in parsed["aggregates"]:
        aggs_by_bc.setdefault(agg["bc_slug"], []).append(agg)

    for bc in parsed["bcs"]:
        slug = bc["slug"]
        up = ", ".join(f"`bc:{u}`" for u in bc.get("upstream", [])) or "なし"
        dn = ", ".join(f"`bc:{d}`" for d in bc.get("downstream", [])) or "なし"
        lines.append(f"### `bc:{slug}`\n")
        lines.append(f"UP: {up} / DOWN: {dn}\n")
        bc_aggs = aggs_by_bc.get(slug, [])
        if not bc_aggs:
            lines.append("- （AGG なし）\n")
            continue
        for agg in bc_aggs:
            agg_id = agg["id"]
            st = len(agg.get("state_transition_cmds", []))
            at = len(agg.get("attribute_cmds", []))
            qr = len(agg.get("queries", []))
            lines.append(
                f"- **`agg:{agg_id}`** → [Epic](epics/{slug}__{agg_id}.md)  "
                f"— 状態遷移 CMD {st} / 属性 CMD {at} / QRY {qr}"
            )
        lines.append("")

    # AGG 跨ぎ統合 Issue
    lines.append("## AGG 跨ぎ統合 Issue（複数 AGG を跨ぐシナリオ）\n")
    if summary["integration"]:
        for item in summary["integration"]:
            lines.append(f"- `{item['file']}` — {item['title']}")
    else:
        lines.append("- （なし）")
    lines.append("")

    # BC 依存関係
    lines.append("## BC 依存関係（再掲）\n")
    lines.append("詳細は [dependency-graph.md](dependency-graph.md) を参照。\n")

    if summary.get("unresolved_policies"):
        lines.append("## ⚠ 未解決 POLICY\n")
        lines.append(
            "次の POLICY は CMD / TRIGGER EVT を AGG に紐付けられませんでした。"
            "DML SCENARIO の CMD/EVT 名と照合してください:\n"
        )
        for name in summary["unresolved_policies"]:
            lines.append(f"- `{name}`")
        lines.append("")

    (out / "_index.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
