#!/usr/bin/env python3
"""EventStorming MD → 構造化 JSON

使い方:
    python3 parse_eventstorming_md.py <md_path> [--out <json_path>]

出力 JSON は generate_issue_drafts.py / build_dependency_graph.py が消費する。

eventstorming-facilitator/scripts/eventstorming_build.py の parse_md() を
再利用し、AGG カードから「状態遷移を起こす CMD」表を抽出する追加処理を行う。
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

from eventstorming_build import parse_md  # noqa: E402


# ============================================================
# 補助: BC slug 抽出
# ============================================================


def extract_bc_slug(name_line: str) -> str:
    """`event-planning（イベント企画）` → `event-planning`"""
    m = re.match(r"^([a-z0-9][a-z0-9-]*)", name_line)
    return m.group(1) if m else name_line


def extract_bc_slug_from_context(ctx: str) -> str:
    """AGG カードの `コンテキスト: event-planning` 値から slug を取り出す"""
    return ctx.strip().strip("`")


# ============================================================
# 状態遷移パース
# ============================================================


TRANSITION_RE = re.compile(
    r"^[`']?(\S+?)[`']?\s*[→\-]>?\s*[`']?(\S+?)[`']?\s*:\s*(.+)$"
)


def parse_transitions(items: list[str]) -> list[dict]:
    """AGG カードの状態遷移リスト各行をパース

    入力例:
        "`DRAFT` → `PUBLISHED`: 公開操作（必須項目チェック）"
    出力:
        {"from": "DRAFT", "to": "PUBLISHED", "trigger": "公開操作（必須項目チェック）"}
    """
    transitions = []
    for item in items:
        # バッククォート除去
        clean = item.strip()
        m = TRANSITION_RE.match(clean)
        if m:
            transitions.append(
                {
                    "from": m.group(1).strip("`'"),
                    "to": m.group(2).strip("`'"),
                    "trigger": m.group(3).strip(),
                }
            )
    return transitions


# ============================================================
# 用語集から SCENARIO 名 → CMD 名 マップ作成
# ============================================================


def build_command_name_map(glossary: dict) -> dict[str, str]:
    """用語集の「コマンド」カテゴリから 日本語 → 英語 のマップを作成

    SCENARIO の本文に含まれる動詞句から CMD 識別子を推定するための辞書。
    """
    result: dict[str, str] = {}
    for cat in ("コマンド", "Command"):
        rows = glossary.get(cat, [])
        for row in rows:
            jp = row.get("jp", "").strip()
            en = row.get("en", "").strip()
            if jp and en:
                result[jp] = en
    return result


def lookup_command_name(scenario_name: str, cmd_map: dict[str, str]) -> str | None:
    """SCENARIO 名から CMD 識別子を最長一致で推定"""
    candidates = [(jp, en) for jp, en in cmd_map.items() if jp in scenario_name]
    if not candidates:
        return None
    candidates.sort(key=lambda x: -len(x[0]))
    return candidates[0][1]


# ============================================================
# AGG → CMD 紐付け
# ============================================================


def split_related_scenarios(related: str) -> list[str]:
    """関連シナリオの値からバッククォート囲みのシナリオ名リストを抽出"""
    return [s.strip().strip("`") for s in re.findall(r"`([^`]+)`", related)]


KANJI_SEQ_RE = re.compile(r"[一-龥]+")


def extract_kanji_keywords(text: str) -> set[str]:
    """text 内の連続漢字シーケンスから 2-gram を抽出 (部分一致のため)"""
    bigrams: set[str] = set()
    for seq in KANJI_SEQ_RE.findall(text):
        if len(seq) < 2:
            continue
        for i in range(len(seq) - 1):
            bigrams.add(seq[i:i + 2])
    return bigrams


def resolve_cmd_for_transition(
    trigger: str, related_scenarios: list[str], cmd_map: dict[str, str]
) -> tuple[str | None, str | None]:
    """状態遷移トリガー文 → 対応する CMD 名 (関連シナリオ経由)

    手順:
        1. trigger に cmd_map のキー (日本語動詞句) が含まれれば即マッチ
        2. それ以外は trigger と各 related の連続漢字シーケンス集合の積を取り、
           共通文字数が最大の related から CMD を引く
    """
    # Step 1: trigger 直接マッチ (最長優先)
    for jp in sorted(cmd_map.keys(), key=len, reverse=True):
        if jp in trigger:
            return cmd_map[jp], None

    # Step 2: 漢字キーワード共有
    trigger_kw = extract_kanji_keywords(trigger)
    if not trigger_kw:
        return None, None
    best_cmd = None
    best_scenario = None
    best_score = 0
    for s in related_scenarios:
        common = trigger_kw & extract_kanji_keywords(s)
        if not common:
            continue
        score = sum(len(k) for k in common)
        if score > best_score:
            cmd = lookup_command_name(s, cmd_map)
            if cmd:
                best_cmd = cmd
                best_scenario = s
                best_score = score
    return best_cmd, best_scenario


def build_scenario_owners(agg_cards: list[dict]) -> dict[str, list[str]]:
    """SCENARIO 名 → そのシナリオを「関連」と宣言した AGG 名のリスト"""
    owners: dict[str, list[str]] = {}
    for agg in agg_cards:
        name = extract_agg_name(agg["name"])
        for scenario in split_related_scenarios(agg.get("related", "")):
            owners.setdefault(scenario, []).append(name)
    return owners


def extract_agg_name(name_line: str) -> str:
    """`Event（イベント）` → `Event`"""
    m = re.match(r"^([A-Za-z][A-Za-z0-9]*)", name_line)
    return m.group(1) if m else name_line


def extract_agg_jp(name_line: str) -> str:
    """`Event（イベント）` → `イベント`"""
    m = re.search(r"（([^）]+)）", name_line)
    return m.group(1) if m else ""


# ============================================================
# 集約データの拡張
# ============================================================


def enrich_aggregates(
    agg_cards: list[dict],
    scenario_owners: dict[str, list[str]],
    cmd_map: dict[str, str],
) -> list[dict]:
    """AGG カードに以下を追加:
    - id (PascalCase 名)
    - jp_name
    - bc_slug
    - transitions (構造化)
    - commands: そのAGGに固有のCMDリスト (state-transition / attribute-only)
    - queries: 別途リードモデルから紐付け
    """
    enriched = []
    for agg in agg_cards:
        agg_id = extract_agg_name(agg["name"])
        bc_slug = extract_bc_slug_from_context(agg.get("context", ""))
        transitions = parse_transitions(agg.get("transitions", []))

        related_scenarios = split_related_scenarios(agg.get("related", ""))

        # state-transition triggers から CMD 識別子を推定
        state_transition_cmds: list[dict] = []
        seen_cmd: set[str] = set()
        resolved_via_scenario: set[str] = set()
        for tr in transitions:
            cmd_name, matched_scenario = resolve_cmd_for_transition(
                tr["trigger"], related_scenarios, cmd_map
            )
            if not cmd_name:
                cmd_name = tr["trigger"]  # フォールバック
            else:
                if matched_scenario:
                    resolved_via_scenario.add(matched_scenario)
            if cmd_name in seen_cmd:
                # 既出のCMDなら from/to の幅を広げるだけにする
                for c in state_transition_cmds:
                    if c["name"] == cmd_name:
                        c["transitions"].append(tr)
                        break
                continue
            seen_cmd.add(cmd_name)
            state_transition_cmds.append(
                {
                    "name": cmd_name,
                    "jp_trigger": tr["trigger"],
                    "mutates_state": True,
                    "transitions": [tr],
                }
            )

        # AGG に「のみ」紐づくシナリオ → 属性更新 CMD 候補
        # ただし state-transition で既に解決済みの SCENARIO は除外
        attribute_cmds: list[dict] = []
        cross_scenarios: list[str] = []
        for scenario in related_scenarios:
            owners = scenario_owners.get(scenario, [])
            if len(owners) > 1:
                cross_scenarios.append(scenario)
                continue
            if scenario in resolved_via_scenario:
                continue  # 状態遷移 CMD として既に登録済み
            cmd_name = lookup_command_name(scenario, cmd_map)
            if not cmd_name:
                continue
            if cmd_name in seen_cmd:
                continue  # state-transition で既出
            seen_cmd.add(cmd_name)
            attribute_cmds.append(
                {
                    "name": cmd_name,
                    "jp_scenario": scenario,
                    "mutates_state": False,
                }
            )

        enriched.append(
            {
                "id": agg_id,
                "jp_name": extract_agg_jp(agg["name"]),
                "name_line": agg["name"],
                "bc_slug": bc_slug,
                "zod": agg.get("zod", ""),
                "purpose": agg.get("purpose", ""),
                "background": agg.get("background", ""),
                "constraints": agg.get("constraints", []),
                "invariants": agg.get("invariants", []),
                "errors": agg.get("errors", []),
                "transitions": transitions,
                "state_transition_cmds": state_transition_cmds,
                "attribute_cmds": attribute_cmds,
                "cross_agg_scenarios": cross_scenarios,
                "related_scenarios": related_scenarios,
                "notes": agg.get("notes", []),
                "derived": agg.get("derived", []),
            }
        )
    return enriched


# ============================================================
# BC データの整形
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
# AGG 跨ぎ SCENARIO の抽出
# ============================================================


def extract_cross_agg_scenarios(
    scenarios: list[dict],
    agg_scenario_owners: dict[str, list[str]],
    cmd_map: dict[str, str],
) -> list[dict]:
    """関連シナリオ言及が 2 つ以上の AGG にまたがる SCENARIO のリスト

    Story 内 SCENARIO (### 見出し) と Alternative Scenarios の両方を見る。
    ここでは agg_scenario_owners から複数オーナーのものだけを返す。
    """
    result = []
    for scenario_name, owners in agg_scenario_owners.items():
        if len(owners) <= 1:
            continue
        cmd_name = lookup_command_name(scenario_name, cmd_map)
        # SCENARIO テキストを scenarios から探す
        text = ""
        for s in scenarios:
            if s["name"] == scenario_name:
                text = s.get("text", "")
                break
        result.append(
            {
                "name": scenario_name,
                "cmd_name": cmd_name,
                "owners": owners,
                "text": text,
            }
        )
    return result


# ============================================================
# DML（YAML）から SCENARIO / POLICY を抽出
# ============================================================


def parse_dml_blocks(dml_text: str) -> dict:
    """DML（YAML）テキストから scenarios / policies を抽出する。

    YAML を `yaml.safe_load` で読み、下流スクリプト（generate_issue_drafts.py /
    build_dependency_graph.py）が消費する既存の dict 構造へ正規化して返す。
    返り値: {"scenarios": [...], "policies": [...]}

    （CONTEXT/BC は `## コンテキスト候補` カードから取得するため、ここでは
    YAML の `contexts` は読まない＝旧テキスト DML と同じ役割分担を維持する）
    """
    if not dml_text.strip():
        return {"scenarios": [], "policies": []}
    data = yaml.safe_load(dml_text)
    if not isinstance(data, dict):
        return {"scenarios": [], "policies": []}
    scenarios = [
        _normalize_scenario(s) for s in (data.get("scenarios") or []) if isinstance(s, dict)
    ]
    policies = [
        _normalize_policy(p) for p in (data.get("policies") or []) if isinstance(p, dict)
    ]
    return {"scenarios": scenarios, "policies": policies}


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

    policies = _as_list(s.get("pol") or s.get("policies"))

    for br in s.get("branches") or []:
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
    for e in s.get("errors") or []:
        if isinstance(e, str):
            errors.append({"text": e, "notes": [], "when": None})
        elif isinstance(e, dict):
            cond = str(e.get("condition", "")).strip()
            err = str(e.get("error", "")).strip()
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
        "context": s.get("context"),
        "actor": s.get("actor"),
        "cmd": s.get("cmd"),
        "events": events,
        "branch_mode": s.get("branchMode"),   # v2: exclusive/concurrent/inclusive（branches 時）
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

    single = p.get("trigger")
    triggers_obj = p.get("triggers")
    trigger_events: list[str] = [single] if single else []
    trigger_mode = None
    if isinstance(triggers_obj, dict):
        trigger_events.extend(
            t for t in (triggers_obj.get("events") or []) if t
        )
        trigger_mode = triggers_obj.get("mode")

    return {
        "name": p.get("name", ""),
        "context": p.get("context"),
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

    cmd_map = build_command_name_map(sections.glossary)
    scenario_owners = build_scenario_owners(sections.agg_cards)
    aggregates = enrich_aggregates(sections.agg_cards, scenario_owners, cmd_map)
    aggregates, unattached_qrys = attach_queries_to_aggregates(
        aggregates, sections.qry_cards
    )

    bcs = enrich_bcs(sections.bc_cards)

    # AGG 跨ぎ SCENARIO
    cross_agg = extract_cross_agg_scenarios(
        sections.scenarios, scenario_owners, cmd_map
    )

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
            for f in sections.flows
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
