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
# DML 内 POLICY / SCENARIO ブロックの抽出
# ============================================================


def parse_dml_blocks(dml_text: str) -> dict:
    """DML テキストから SCENARIO / POLICY ブロックを抽出。

    返り値: {"scenarios": [...], "policies": [...]}
    各ブロックの行頭の `#` コメントは preceding_notes として block に紐付ける。
    """
    scenarios: list[dict] = []
    policies: list[dict] = []
    pending_notes: list[str] = []
    lines = dml_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            pending_notes = []
            i += 1
            continue

        if stripped.startswith("#"):
            pending_notes.append(stripped.lstrip("#").strip())
            i += 1
            continue

        m_scenario = re.match(r"^SCENARIO\s+(.+)$", stripped)
        m_policy = re.match(r"^POLICY\s+(\S+)\s*$", stripped)

        if m_scenario or m_policy:
            block_kind = "scenario" if m_scenario else "policy"
            name = (m_scenario or m_policy).group(1).strip()
            notes = pending_notes[:]
            pending_notes = []
            body: list[tuple[str, str, list[str]]] = []
            i += 1
            inline_notes: list[str] = []
            while i < len(lines):
                child = lines[i]
                child_stripped = child.strip()
                if not child_stripped:
                    break
                if not child.startswith(" "):
                    break
                if child_stripped.startswith("#"):
                    inline_notes.append(child_stripped.lstrip("#").strip())
                    i += 1
                    continue
                m_kv = re.match(r"^(\w+)\s+(.+)$", child_stripped)
                if m_kv:
                    body.append((m_kv.group(1), m_kv.group(2).strip(), inline_notes[:]))
                    inline_notes = []
                i += 1

            if block_kind == "scenario":
                scenarios.append(_assemble_scenario(name, body, notes))
            else:
                policies.append(_assemble_policy(name, body, notes))
            continue

        i += 1

    return {"scenarios": scenarios, "policies": policies}


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and (
        (v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")
    ):
        return v[1:-1]
    return v


def _assemble_scenario(name: str, body: list[tuple[str, str, list[str]]], notes: list[str]) -> dict:
    """SCENARIO ブロック行を辞書化。同名キーは list で保持。

    `RULE` 行の直下に `WHY "..."` があれば直前の RULE dict に `why` を注入する。
    `ERR` 行の直下に `WHEN "..."` があれば直前の ERR dict に `when` を注入する。
    （`WHEN` キーは SCENARIO の制御フロー分岐としても使われるので、直前が ERR
    の場合のみ ERR.when として扱う。それ以外の WHEN は無視＝既存動作と同じ）
    """
    result: dict = {
        "name": name,
        "actor": None,
        "cmd": None,
        "events": [],
        "agg": None,
        "rules": [],
        "errors": [],
        "policies": [],
        "notes": notes,
    }
    last_kind: str | None = None
    for key, value, kv_notes in body:
        k = key.upper()
        if k == "ACTOR":
            result["actor"] = value
            last_kind = "ACTOR"
        elif k == "CMD":
            result["cmd"] = value
            last_kind = "CMD"
        elif k == "EVT":
            result["events"].append({"name": value, "notes": kv_notes})
            last_kind = "EVT"
        elif k == "AGG":
            result["agg"] = value
            last_kind = "AGG"
        elif k == "RULE":
            result["rules"].append({"text": value, "notes": kv_notes, "why": None})
            last_kind = "RULE"
        elif k == "ERR":
            result["errors"].append({"text": value, "notes": kv_notes, "when": None})
            last_kind = "ERR"
        elif k == "POL":
            result["policies"].append(value)
            last_kind = "POL"
        elif k == "WHY":
            if last_kind == "RULE" and result["rules"]:
                result["rules"][-1]["why"] = _strip_quotes(value)
        elif k == "WHEN":
            if last_kind == "ERR" and result["errors"]:
                result["errors"][-1]["when"] = _strip_quotes(value)
            # それ以外の WHEN は SCENARIO の制御フロー分岐として無視（既存動作）
    return result


def _assemble_policy(name: str, body: list[tuple[str, str, list[str]]], notes: list[str]) -> dict:
    """POLICY ブロック行を辞書化。"""
    result: dict = {
        "name": name,
        "trigger": None,
        "qry": None,
        "cmd": None,
        "bulk": False,
        "emits": None,
        "notes": notes,
    }
    for key, value, _kv_notes in body:
        k = key.upper()
        if k == "TRIGGER":
            result["trigger"] = value
        elif k == "QRY":
            result["qry"] = value
        elif k == "CMD":
            result["cmd"] = value
        elif k == "BULK":
            result["bulk"] = value.lower() == "true"
        elif k == "EVT":
            result["emits"] = value
    return result


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

    dml_blocks = parse_dml_blocks(sections.dml or "")

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
        "dml": sections.dml,
    }

    out_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(out_text, encoding="utf-8")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
