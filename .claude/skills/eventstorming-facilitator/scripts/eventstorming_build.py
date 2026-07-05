#!/usr/bin/env python3
"""EventStorming DML → HTML ビルダー（YAML-only）

`.dml.yaml`（DML）を **唯一の入力** とし、HTML 全セクションを DML だけから生成する。
v5 で `.md` 入力サポートを廃止し、v8 でハッピーパス散文 `story` を `narratives[kind:happy]` に統合：
散文（narratives）/ 次のアクション（actions）/ オープンクエスチョン（questions）/
BC 散文（contexts[].description）/ リードモデル（queries）も DML 内に保持される。glossary_index（語彙の英→日変換）は DML `contexts[].lang` を
全 BC 走査して機械的に生成する。

使い方:
    python3 scripts/eventstorming_build.py <yaml_path>            # 個別ビルド
    python3 scripts/eventstorming_build.py --all                  # 全件ビルド（*.dml.yaml）
    python3 scripts/eventstorming_build.py --watch [<dir>]        # 監視モード
    python3 scripts/eventstorming_build.py <yaml_path> --artifact # Artifact 互換 HTML
    python3 scripts/eventstorming_build.py <yaml_path> --artifact --copy
                                                                  # pbcopy でクリップボードへ
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    # DML を構造化して読むためのオプション依存（validate_dml.py と同じ依存）。
    # 不在時は §3/§9/§7 は描画スキップ（§11 の生 DML 表示にフォールバック）。
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# このスクリプトは .claude/skills/eventstorming-facilitator/scripts/ に配置されている想定
# SCRIPT_DIR = scripts/ なので SCRIPT_DIR.parents:
#   [0]=eventstorming-facilitator, [1]=skills, [2]=.claude, [3]=プロジェクトルート
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "docs" / "eventstorming"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist" / "eventstorming"
TEMPLATE_PATH = SKILL_ROOT / "templates" / "event-flow.html"

KIND_LABEL = {
    "actor": "Actor",
    "command": "Command",
    "event": "Event",
    "policy": "Policy",
    "readmodel": "Read Model",
}
# アクター名が `System` のシナリオでは actor 付箋を省略して図のノイズを減らす
# （ポリシー駆動の連鎖は前段のポリシー付箋で文脈が伝わるため）。
SKIP_SYSTEM_ACTOR = True
LANE_COLOR_CLASSES = [
    "bc-default-1",
    "bc-default-2",
    "bc-default-3",
    "bc-default-4",
    "bc-default-5",
]


# ============================================================
# データクラス
# ============================================================


@dataclass
class Note:
    kind: str  # actor/command/event/policy/readmodel
    label: str
    is_async: bool = False
    is_fanout: bool = False  # *> 後段。スタック描画 + ×N バッジ
    is_pivotal: bool = False  # scenarios[].pivotal 由来。節目イベントの強調描画


@dataclass
class Lane:
    bc_name: str
    description: str
    notes: list[Note] = field(default_factory=list)
    joins_into_next: bool = False  # 行末 &>>。次レーンへ Join 遷移（BPMN シンクバー描画）


@dataclass
class Flow:
    title: str
    lanes: list[Lane] = field(default_factory=list)


@dataclass
class DMLDocument:
    """`.dml.yaml` を構造化した HTML ビルダー入力。

    各フィールドはレンダラがそのまま消費するため、`load_dml_document` で
    YAML 由来の構造を取り回しやすい形に正規化する。
    """
    session: dict = field(default_factory=dict)
    narratives: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    qrys: list[dict] = field(default_factory=list)
    dml_text: str = ""              # 元 YAML 全文（§10 表示用）
    dml_errors: list[str] = field(default_factory=list)
    model: dict | None = None       # yaml.safe_load 結果（contexts/aggregates/scenarios/policies/narratives/decisions の参照元）


def load_dml_document(yaml_text: str) -> DMLDocument:
    """YAML 全文を DMLDocument に正規化する。

    解析失敗・PyYAML 不在は空ドキュメントを返す（呼び出し側でフォールバック）。
    """
    doc = DMLDocument(dml_text=yaml_text)
    if yaml is None or not yaml_text.strip():
        return doc
    try:
        loaded = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:  # type: ignore[attr-defined]
        print(f"⚠ DML YAML 解析失敗: {e}", file=sys.stderr)
        return doc
    if not isinstance(loaded, dict):
        return doc

    doc.model = loaded
    doc.session = loaded.get("session") or {}
    doc.narratives = [n for n in (loaded.get("narratives") or []) if isinstance(n, dict)]
    doc.actions = [a for a in (loaded.get("actions") or []) if isinstance(a, dict)]
    doc.questions = [q for q in (loaded.get("questions") or []) if isinstance(q, dict)]
    doc.qrys = [q for q in (loaded.get("queries") or []) if isinstance(q, dict)]
    return doc


def _format_dml_deps(deps: list) -> tuple[str, list[str]]:
    """DML `contexts[].up` / `dn` のリストを表示用文字列と slug リストに変換する。"""
    if not deps:
        return "(none)", []
    parts: list[str] = []
    slugs: list[str] = []
    for d in deps:
        if not isinstance(d, dict):
            continue
        ctx_name = str(d.get("ctx", "?"))
        rel = str(d.get("rel", ""))
        note = str(d.get("note", ""))
        s = ctx_name
        if rel:
            s += f" ({rel})"
        if note:
            s += f" — {note}"
        parts.append(s)
        slugs.append(ctx_name)
    if not parts:
        return "(none)", []
    return " · ".join(parts), slugs


# ============================================================
# DML 駆動の生成（フロー / 集約 / 意思決定ログ）
# ============================================================
#
# `.dml.yaml` を yaml.safe_load した dict（MDSections.dml_model）から、
# HTML §3（イベントフロー）・§9（集約カード）・§7（意思決定ログ）を組み立てる。
# 旧来の手書き event-flow-svg DSL や `.md` §5 (旧)= §9 (新) Zod ブロックは廃止。
#
# 共有公開関数:
#   - build_glossary_index_from_dml(model) → {EN識別子: 日本語ラベル}（DML contexts[].lang 走査）
#   - localize(identifier, glossary_idx)   → 日本語ラベル or 英語フォールバック
#   - build_flows_from_dml(model, gloss)  → list[Flow]（render_flow 再利用）
#   - aggregates_from_dml(model)          → 集約情報（下流スキル to-issues も利用）
#
# 描画関数:
#   - render_agg_cards_from_dml(...)      → HTML §9 集約カード
#   - render_decisions(...)               → HTML 意思決定ログ


# `contexts[].lang` のカテゴリ別キーと表示名の対応
LANG_CATEGORIES: list[tuple[str, str]] = [
    ("aggs", "集約"),
    ("vos", "値オブジェクト"),
    ("actors", "アクター"),
    ("cmds", "コマンド"),
    ("evts", "イベント"),
    ("pols", "ポリシー"),
    ("qrys", "リードモデル"),
    ("states", "状態"),
]


def build_glossary_index_from_dml(model: dict | None) -> dict[str, str]:
    """DML model 全体を走査して `{英語識別子: 日本語ラベル}` を機械的に生成する。

    `contexts[].lang` はカテゴリ別 dict-of-dicts 構造:
      lang:
        aggs:   { EnId: jp, ... }
        actors: { EnId: jp, ... }
        cmds:   { EnId: jp, ... }
        evts:   { EnId: jp, ... }
        pols:   { EnId: jp, ... }
        qrys:   { EnId: jp, ... }
        vos:    { EnId: jp, ... }

    全 BC・全カテゴリを横断して `{en: jp}` の平坦 dict に畳み込む。同一識別子が
    複数 BC に登場した場合は最初の登録を優先（後勝ちだとフロー描画ラベルが BC 順序
    依存になり不安定）。HTML §4 用語集セクションは廃止済みで、本 index は
    フロー図ラベル・§6 意思決定ログの affects 表示で英語識別子を日本語に置換する
    用途にのみ使う。
    """
    index: dict[str, str] = {}
    if not model:
        return index
    contexts = model.get("contexts") or []
    for ctx in contexts:
        if not isinstance(ctx, dict):
            continue
        lang = ctx.get("lang") or {}
        if not isinstance(lang, dict):
            continue
        for cat_key, _label in LANG_CATEGORIES:
            cat_dict = lang.get(cat_key) or {}
            if not isinstance(cat_dict, dict):
                continue
            for term, definition in cat_dict.items():
                key = str(term).strip()
                value = str(definition).strip()
                if not key or not value:
                    continue
                index.setdefault(key, value)
    return index


def localize(identifier: str, glossary_index: dict[str, str]) -> str:
    """英語識別子（PascalCase 等）を用語集経由で日本語化。無ければ英語のまま。"""
    if not identifier:
        return ""
    return glossary_index.get(identifier, identifier)


def _pick_active_branch(sc: dict, flow_id: str) -> dict | None:
    """指定フロー上で「いまアクティブな」brs[] エントリを 1 つ選ぶ。

    優先順位:
      1. `terminal == flow_id` の brs（このフローはここで終わる宣言）
      2. `terminal` を持たない brs（happy 系・デフォルト分岐）
      3. fallback: 最初の brs
    brs が無ければ None を返す。
    """
    brs = sc.get("brs") or []
    if not brs:
        return None
    for br in brs:
        if br.get("terminal") == flow_id:
            return br
    for br in brs:
        if not br.get("terminal"):
            return br
    return brs[0]


def _collect_pivotal_evts(model: dict) -> set[str]:
    """scenarios[].pivotal: true の scenario が発火する EVT 名（evt / brs[].evt）を集める。

    policy 経由で同名 EVT が描画されるケース（pol.evt が pivotal scenario の evt と一致）
    でも強調が落ちないよう、Note 生成は「pivotal scenario への所属」ではなく
    「EVT 名がこの集合に含まれるか」で判定する。
    """
    evts: set[str] = set()
    for sc in model.get("scenarios") or []:
        if not isinstance(sc, dict) or not sc.get("pivotal"):
            continue
        if sc.get("evt"):
            evts.add(sc["evt"])
        for br in sc.get("brs") or []:
            if isinstance(br, dict) and br.get("evt"):
                evts.add(br["evt"])
    return evts


def _scenario_steps_to_notes(
    sc: dict,
    gloss: dict[str, str],
    active_br: dict | None = None,
    pivotal_evts: set[str] | None = None,
) -> list[Note]:
    """1 つの SCENARIO ステップを Note リストに展開する。

    順序: actor → qry[] → cmd → (active_br.evt | scenario.evt | brs[].evt 全列挙)。
    actor=System は省略可（クラッタ抑制）。

    `active_br` が指定された時はその evt のみを採用（フロー別描画）。
    指定なし時は従来動作: scenario.evt があればそれを採用、無ければ brs[] 全列挙
    （brMode=concurrent では 2 件目以降を fanout 化）。
    `pivotal_evts` に含まれる EVT の付箋は is_pivotal=True で強調描画される。
    """
    pivotal_evts = pivotal_evts or set()
    notes: list[Note] = []
    actor = sc.get("actor") or ""
    if actor and not (SKIP_SYSTEM_ACTOR and actor == "System"):
        notes.append(Note(kind="actor", label=localize(actor, gloss)))
    for q in sc.get("qry") or []:
        notes.append(Note(kind="readmodel", label=localize(q, gloss)))
    cmd = sc.get("cmd")
    if cmd:
        notes.append(Note(kind="command", label=localize(cmd, gloss)))
    if active_br is not None:
        # フロー別描画: アクティブな brs.evt のみ
        ev = active_br.get("evt")
        if ev:
            notes.append(Note(kind="event", label=localize(ev, gloss), is_pivotal=ev in pivotal_evts))
    elif sc.get("evt"):
        ev = sc["evt"]
        notes.append(Note(kind="event", label=localize(ev, gloss), is_pivotal=ev in pivotal_evts))
    elif sc.get("brs"):
        mode = sc.get("brMode", "exclusive")
        for i, br in enumerate(sc["brs"]):
            ev = br.get("evt")
            if not ev:
                continue
            n = Note(kind="event", label=localize(ev, gloss), is_pivotal=ev in pivotal_evts)
            if mode == "concurrent" and i > 0:
                n.is_fanout = True
            notes.append(n)
    return notes


def _policy_steps_to_notes(
    pol: dict, gloss: dict[str, str], pivotal_evts: set[str] | None = None
) -> list[Note]:
    """1 つの POLICY ステップを Note リストに展開する。

    順序: policy → qry? → evt?。`pol.cmd` は後続シナリオの cmd と重複するため
    意図的に**出力しない**（フロー DSL の伝統的な見せ方 `$Policy > !cmd > [evt]` で
    cmd 付箋は 1 枚のみ、というのと整合）。
    側壁: 副作用専用 POLICY が cmd を持つ稀少ケースでは cmd 付箋が省略されるが、
    pol.evt が立つことで結果は可視化される（cmd の同定は §11 生 DML を参照）。
    bulk: true の場合 evt 付箋を fanout 化（×N スタック）。
    trgs（join）の表示は呼び出し側で前レーン `joins_into_next=True` として処理する。
    """
    pivotal_evts = pivotal_evts or set()
    notes: list[Note] = []
    bulk = bool(pol.get("bulk"))
    notes.append(Note(kind="policy", label=localize(pol.get("name", ""), gloss)))
    qry = pol.get("qry")
    if qry:
        notes.append(Note(kind="readmodel", label=localize(qry, gloss)))
    if pol.get("evt"):
        ev = pol["evt"]
        n = Note(kind="event", label=localize(ev, gloss), is_pivotal=ev in pivotal_evts)
        if bulk:
            n.is_fanout = True
        notes.append(n)
    return notes


def build_flows_from_dml(model: dict, glossary_index: dict[str, str]) -> list[Flow]:
    """DML の `narratives[].entry` を起点に scenarios[].next を辿り、フロー描画用の
    `list[Flow]` を組み立てる（v6）。policy ステップは scenario.evt → policy.trg
    のマッチで自動挿入する（再帰的に policy.evt → 後続 policy.trg も辿る）。

    既存の `render_flow()`（Big Picture グリッド HTML 生成）が消費する Flow/Lane/Note
    dataclass を作るだけで、HTML 生成本体は再利用する。

    フロー連鎖の解釈:
      - narratives[].entry: フロー開始 scenario.name
      - scenarios[].next: string → 全フロー共通の次 / dict → narratives[].id 別の次
      - scenarios[].brs[].terminal: <flow_id> → このフローはこの brs 発火後に終端
      - scenarios[].brs[] の active 選択: terminal が当フロー一致 > terminal 無し > 先頭

    レーン併合ルール:
      - 同一 ctx で sync な継続（scenarios→scenarios かつ前段の最後の遷移が非同期でない）→ 同一 Lane に Note 連結
      - ctx が変わる、または次が policy ステップ（EVENTUAL-TX）→ 新規 Lane。前 Lane 末尾の Note を is_async=True
      - 次が trgs（join）policy → 前 Lane の joins_into_next=True（BPMN Σ N シンクバー）
    """
    scenarios = model.get("scenarios") or []
    policies = model.get("policies") or []
    narratives = model.get("narratives") or []
    pivotal_evts = _collect_pivotal_evts(model)

    scenarios_by_name: dict[str, dict] = {}
    for s in scenarios:
        if not isinstance(s, dict):
            continue
        name = s.get("name")
        if not name:
            continue
        if name in scenarios_by_name:
            print(f"⚠ DML scenarios: 重複した name: {name}", file=sys.stderr)
        scenarios_by_name[name] = s

    # evt 名 → トリガーされる policies のリスト
    policies_by_trg: dict[str, list[dict]] = {}
    for p in policies:
        if not isinstance(p, dict):
            continue
        trg = p.get("trg")
        if trg:
            policies_by_trg.setdefault(trg, []).append(p)
        trgs = p.get("trgs") or {}
        if isinstance(trgs, dict):
            for evt in (trgs.get("evts") or []):
                policies_by_trg.setdefault(evt, []).append(p)

    def emit_policies(evt: str, flow: Flow, ctx_box: list, visited: set):
        """evt をトリガーとする policy を再帰的に挿入する。"""
        if not evt:
            return
        for pol in policies_by_trg.get(evt, []):
            pol_name = pol.get("name")
            if not pol_name or pol_name in visited:
                continue
            visited.add(pol_name)
            pol_notes = _policy_steps_to_notes(pol, glossary_index, pivotal_evts=pivotal_evts)
            if not pol_notes:
                continue
            pol_ctx = pol.get("ctx", "")
            if flow.lanes and flow.lanes[-1].notes:
                flow.lanes[-1].notes[-1].is_async = True
                if pol.get("trgs"):
                    flow.lanes[-1].joins_into_next = True
            lane = Lane(bc_name=pol_ctx, description="")
            lane.notes = list(pol_notes)
            flow.lanes.append(lane)
            ctx_box[0] = pol_ctx
            # 再帰: この policy が emit する evt で更に triggering policies を辿る
            if pol.get("evt"):
                emit_policies(pol["evt"], flow, ctx_box, visited)

    out: list[Flow] = []
    for n in narratives:
        if not isinstance(n, dict):
            continue
        entry = n.get("entry")
        if not entry:
            continue  # entry 無し narrative は §2 散文のみで §3 には描画しない
        flow_id = n.get("id", "")
        flow = Flow(title=n.get("title") or flow_id)
        ctx_box = [None]  # [prev_ctx] — closure 経由で更新するため list
        visited_scenarios: set[str] = set()
        visited_policies: set[str] = set()

        current = entry
        while current and current not in visited_scenarios:
            visited_scenarios.add(current)
            sc = scenarios_by_name.get(current)
            if not sc:
                print(
                    f"⚠ DML narratives[{flow_id}]: 未解決の entry/next scenario: {current}",
                    file=sys.stderr,
                )
                break

            active_br = _pick_active_branch(sc, flow_id)
            notes = _scenario_steps_to_notes(
                sc, glossary_index, active_br=active_br, pivotal_evts=pivotal_evts
            )
            if notes:
                ctx = sc.get("ctx", "")
                if flow.lanes and ctx == ctx_box[0]:
                    flow.lanes[-1].notes.extend(notes)
                else:
                    if flow.lanes and flow.lanes[-1].notes:
                        flow.lanes[-1].notes[-1].is_async = True
                    lane = Lane(bc_name=ctx, description="")
                    lane.notes = list(notes)
                    flow.lanes.append(lane)
                ctx_box[0] = ctx

            # この scenario の発火 evt（active_br 優先、無ければ scenario.evt）
            cur_evt = active_br.get("evt") if active_br else sc.get("evt")
            if cur_evt:
                emit_policies(cur_evt, flow, ctx_box, visited_policies)

            # active_br が当フローの終端宣言なら、ここで終わる
            if active_br and active_br.get("terminal") == flow_id:
                break

            # 次の scenario を決定: active_br.next を優先、無ければ sc.next
            br_next = active_br.get("next") if active_br else None
            if br_next:
                next_name = br_next
            else:
                next_value = sc.get("next")
                if isinstance(next_value, str):
                    next_name = next_value
                elif isinstance(next_value, dict):
                    next_name = next_value.get(flow_id)
                else:
                    next_name = None
            current = next_name

        if flow.lanes:
            out.append(flow)
    return out


def aggregates_from_dml(model: dict) -> list[dict]:
    """DML から集約情報を導出する公開ヘルパー（下流スキル to-issues も利用）。

    出力は集約 1 件あたり以下のキーを持つ dict のリスト:
      name / ctx / purpose / background / constraints
      states / transitions / attrs / events
      invariants (=scenarios[].rules で agg 一致) / errors (=scenarios[].errs で agg 一致)
      related_scenarios (=該当 scenarios[].name のリスト)

    `aggregates[].events` が空のときは scenarios[] から **イベント名のみ**を自動補完する
    （params は空のまま）。明示的に declare 済みの events[] はそのまま使う。
    `aggregates[].transitions[]` は設計判断（from/to/via の組み合わせ）が必要なため
    自動補完しない — 空のときは空のまま返す。
    """
    aggregates = model.get("aggregates") or []
    scenarios = model.get("scenarios") or []
    # AGG 名で scenarios を集計
    rules_by_agg: dict[str, list[dict]] = {}
    errs_by_agg: dict[str, list[dict]] = {}
    rel_by_agg: dict[str, list[str]] = {}
    evt_names_by_agg: dict[str, list[str]] = {}  # 重複除去で順序保持
    for s in scenarios:
        a = s.get("agg")
        if not a:
            continue
        rel_by_agg.setdefault(a, []).append(s.get("name") or "")
        for r in s.get("rules") or []:
            rules_by_agg.setdefault(a, []).append(r)
        for e in s.get("errs") or []:
            errs_by_agg.setdefault(a, []).append(e)
        # evt の収集（scenarios[].evt と scenarios[].brs[].evt の両方）
        seen = evt_names_by_agg.setdefault(a, [])
        cand = []
        if s.get("evt"):
            cand.append(s["evt"])
        for br in s.get("brs") or []:
            if br.get("evt"):
                cand.append(br["evt"])
        for e in cand:
            if e and e not in seen:
                seen.append(e)
    out: list[dict] = []
    for ag in aggregates:
        name = ag.get("name", "")
        declared_events = list(ag.get("events") or [])
        # フォールバック: events[] が未記述なら scenarios[].evt から名前だけ補完（params は空）
        if not declared_events:
            derived = [{"name": ev} for ev in evt_names_by_agg.get(name, [])]
        else:
            derived = declared_events
        out.append({
            "name": name,
            "ctx": ag.get("ctx", ""),
            "purpose": ag.get("purpose", ""),
            "background": ag.get("background", ""),
            "constraints": list(ag.get("constraints") or []),
            "states": list(ag.get("states") or []),
            "transitions": list(ag.get("transitions") or []),
            "attrs": list(ag.get("attrs") or []),
            "events": derived,
            "note": ag.get("note", ""),
            "invariants": rules_by_agg.get(name, []),
            "errors": errs_by_agg.get(name, []),
            "related_scenarios": [n for n in rel_by_agg.get(name, []) if n],
        })
    return out


# ============================================================
# HTML レンダラ
# ============================================================


def esc(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PHASE_DONE_COUNT = {
    "1": 1, "2": 2, "3": 3, "4": 4,
    "4.5": 5, "4.6": 6,
    "5": 7, "6": 8, "7": 9,
}


def render_progress(status: str, phase: str | None = None) -> str:
    """SKILL.md のワークフロー（9 ステップ）と整合する進捗バーを生成。

    v7: 構造化フィールド `session.phase`（"1".."7"）があれば最優先で使う。
    後方互換のため `status` 文字列の regex 解釈も残す（`session.phase` 未設定時）。
    """
    phases = [
        "1. スコープ",
        "2. ストーリー",
        "3. イベント発見",
        "4. CMD-EVT-POLICY",
        "4.5. BC 境界",
        "4.6. 目的・背景・制約",
        "5. 不変条件・エラー＋属性",
        "6. 意思決定ログ",
        "7. 整合性チェック",
    ]
    done_count = 0
    # 構造化フィールド優先（v7）
    if phase and str(phase) in PHASE_DONE_COUNT:
        done_count = PHASE_DONE_COUNT[str(phase)]
    else:
        # レガシー: status 文字列の regex 解釈
        # 順序は具体度の高いものから（"フェーズ4.6" は "フェーズ4" にもマッチするため先行評価）
        # 「フェーズ」「Phase」両表記を許容。数字との間は半角/全角の空白を許容する。
        phase_kw = r"(?:フェーズ|Phase)"
        if re.search(rf"{phase_kw}\s*7.*完了", status):
            done_count = 9
        elif re.search(rf"{phase_kw}\s*6", status):
            done_count = 8
        elif re.search(rf"{phase_kw}\s*5", status):
            done_count = 7
        elif re.search(rf"{phase_kw}\s*4\.6", status):
            done_count = 6
        elif re.search(rf"{phase_kw}\s*4\.5", status):
            done_count = 5
        elif re.search(rf"{phase_kw}\s*4", status):
            done_count = 4
        elif re.search(rf"{phase_kw}\s*3", status):
            done_count = 3
        elif re.search(rf"{phase_kw}\s*2", status):
            done_count = 2
        elif re.search(rf"{phase_kw}\s*1", status):
            done_count = 1

    last_idx = len(phases) - 1
    items = []
    for i, name in enumerate(phases):
        if i < done_count:
            cls = "phase done"
            label = name + (" ✅" if i == last_idx else "")
        elif i == done_count:
            cls = "phase current"
            label = name
        else:
            cls = "phase"
            label = name
        items.append(f'<div class="{cls}">{esc(label)}</div>')
    return "\n    ".join(items)


def render_narratives(narratives: list[dict]) -> str:
    """`narratives[]` をストーリーとして描画（kind:happy 先頭・黄背景、kind:alt 後続・白カード）。"""
    if not narratives:
        return '<div class="todo-placeholder">TODO: フェーズ2完了後に追記</div>'
    # happy を先頭、alt を後続。kind 不在は alt 扱いで末尾。
    ordered = sorted(
        narratives,
        key=lambda n: 0 if n.get("kind") == "happy" else (1 if n.get("kind") == "alt" else 2),
    )
    parts = []
    for n in ordered:
        title = n.get("title") or n.get("id") or ""
        prose = n.get("prose") or ""
        if n.get("kind") == "happy":
            paragraphs = [p.strip() for p in prose.split("\n\n") if p.strip()]
            inner = "\n    ".join(f"<p>{esc(p)}</p>" for p in paragraphs)
            heading = f'<h3 class="story-title">{esc(title)}</h3>\n    ' if title else ""
            parts.append(f'<div class="story">\n    {heading}{inner}\n  </div>')
        else:
            text_html = "\n    ".join(
                f"<p>{esc(line.strip())}</p>"
                for line in prose.split("\n")
                if line.strip()
            )
            parts.append(
                f'<div class="scenario-card">\n'
                f'    <h3>{esc(title)}</h3>\n'
                f"    {text_html}\n"
                f"  </div>"
            )
    return "\n  ".join(parts)


def render_flows(flows: list[Flow]) -> str:
    if not flows:
        return '<div class="todo-placeholder">フロー未定義</div>'

    legend = (
        '<div class="legend">\n'
        '    <span class="note-mini actor">Actor</span>\n'
        '    <span class="note-mini command">Command</span>\n'
        '    <span class="note-mini event">Event</span>\n'
        '    <span class="note-mini policy">Policy</span>\n'
        '    <span class="note-mini readmodel">Read Model</span>\n'
        '    <span class="legend-divider"></span>\n'
        '    <span class="note-mini event fanout-mini">×N (BULK)</span>\n'
        '    <span class="legend-sync">Σ N (Join)</span>\n'
        '    <span class="note-mini event pivotal-mini">⭐ Pivotal (節目)</span>\n'
        "  </div>"
    )

    out_parts = [legend]
    for flow in flows:
        out_parts.append(render_flow(flow))
    return "\n  ".join(out_parts)


def render_flow(flow: Flow) -> str:
    """1 つの Flow を Big Picture グリッド HTML に変換"""
    # 同じ BC を統合して unique 行を作る
    unique_bcs: list[str] = []
    bc_to_row: dict[str, int] = {}
    for lane in flow.lanes:
        if lane.bc_name not in bc_to_row:
            bc_to_row[lane.bc_name] = len(unique_bcs) + 1
            unique_bcs.append(lane.bc_name)

    # BC 名 → カラー class
    bc_to_color: dict[str, str] = {}
    for i, bc in enumerate(unique_bcs):
        bc_to_color[bc] = LANE_COLOR_CLASSES[i % len(LANE_COLOR_CLASSES)]

    # === 左カラム: レーンヘッダ(横スクロール対象外) ===
    lane_header_items: list[str] = []
    for bc in unique_bcs:
        row = bc_to_row[bc]
        color = bc_to_color[bc]
        lane_header_items.append(
            f'<div class="lane-name {color}" style="grid-row: {row};">'
            f"{esc(bc)}</div>"
        )
    lane_header_html = "\n        ".join(lane_header_items)

    # === 右カラム: notes と矢印のみ。grid-column は 1 から開始 ===
    note_elements: list[str] = []
    col = 1
    prev_lane: Lane | None = None
    for li, lane in enumerate(flow.lanes):
        row = bc_to_row[lane.bc_name]
        # 前レーンとの非同期遷移
        if prev_lane is not None and prev_lane.notes and prev_lane.notes[-1].is_async:
            prev_row = bc_to_row[prev_lane.bc_name]
            arrow_dir = "down" if row > prev_row else "up"
            r1, r2 = (prev_row, row) if row > prev_row else (row, prev_row)
            if prev_lane.joins_into_next:
                # N → 1 Join: BPMN シンクバー（黒太線 + Σ N ラベル）
                note_elements.append(
                    f'<div class="sync-bar {arrow_dir}" style="grid-row: {r1} / {r2 + 1}; grid-column: {col};">'
                    f'<span class="async-label">Σ N</span></div>'
                )
            else:
                note_elements.append(
                    f'<div class="arrow-v {arrow_dir}" style="grid-row: {r1} / {r2 + 1}; grid-column: {col};">'
                    f'<span class="async-label">⚡ async</span></div>'
                )
            col += 1

        for ni, note in enumerate(lane.notes):
            if ni > 0:
                # 同期矢印: 非 fanout → fanout の境界で fork 矢印に切替
                prev_note = lane.notes[ni - 1]
                if note.is_fanout and not prev_note.is_fanout:
                    arrow_cls = "arrow-h fork"
                else:
                    arrow_cls = "arrow-h"
                note_elements.append(
                    f'<div class="{arrow_cls}" style="grid-row: {row}; grid-column: {col};"></div>'
                )
                col += 1
            kind_label = KIND_LABEL[note.kind]
            label_html = esc(note.label).replace("\n", "<br>")
            note_cls = f"note {note.kind}"
            if note.is_fanout:
                note_cls += " fanout"
            if note.is_pivotal:
                note_cls += " pivotal"
            note_elements.append(
                f'<div class="{note_cls}" style="grid-row: {row}; grid-column: {col};">'
                f'<span class="kind">{kind_label}</span>{label_html}</div>'
            )
            col += 1
        prev_lane = lane

    # 右端スペーサー: 横スクロール時に padding-right が効かない(Grid + overflow)
    # ブラウザ挙動の対策として、最終 column に幅 48px のダミー要素を入れる。
    note_elements.append(
        f'<div class="end-spacer" style="grid-row: 1; grid-column: {col};"></div>'
    )

    notes_html = "\n          ".join(note_elements)
    # .flow-body の grid-template-rows を動的生成。
    # minmax(80px, auto) で各行は最低 80px、内容が大きければ自動拡張。
    # subgrid 設定により .lane-header / .flow-scroll は同じ行高さを共有する。
    n_rows = len(unique_bcs)
    rows_template = " ".join(["minmax(80px, auto)"] * n_rows)
    return (
        f'<div class="flow">\n'
        f'    <div class="flow-title">{esc(flow.title)}</div>\n'
        f'    <div class="flow-body" style="grid-template-rows: {rows_template};">\n'
        f'      <div class="lane-header">\n'
        f"        {lane_header_html}\n"
        f"      </div>\n"
        f'      <div class="flow-scroll">\n'
        f"        {notes_html}\n"
        f"      </div>\n"
        f"    </div>\n"
        f"  </div>"
    )


def bc_cards_from_dml(model: dict | None) -> list[dict]:
    """DML `contexts[]` から BC カード表示用 dict 列を組み立てる。

    各カードは slug/name/description（導入散文）/purpose/background/constraints
    /upstream/downstream/downstream_slugs/languages_by_cat を持つ。purpose/background/
    constraints は render_intent_blocks で色付きブロックに描画される。
    """
    if not model:
        return []
    contexts = model.get("contexts") or []
    cards: list[dict] = []
    for ctx in contexts:
        if not isinstance(ctx, dict):
            continue
        slug = str(ctx.get("name") or "").strip()
        if not slug:
            continue

        languages_by_cat: list[tuple[str, list[tuple[str, str]]]] = []
        lang_dict = ctx.get("lang") or {}
        if isinstance(lang_dict, dict):
            for cat_key, cat_label in LANG_CATEGORIES:
                cat_dict = lang_dict.get(cat_key) or {}
                if not isinstance(cat_dict, dict) or not cat_dict:
                    continue
                rows: list[tuple[str, str]] = []
                for term, definition in cat_dict.items():
                    en = str(term).strip()
                    jp = str(definition).strip()
                    if en and jp:
                        rows.append((en, jp))
                if rows:
                    languages_by_cat.append((cat_label, rows))

        upstream_str, _ = _format_dml_deps(ctx.get("up") or [])
        downstream_str, downstream_slugs = _format_dml_deps(ctx.get("dn") or [])

        label_ja = str(ctx.get("label_ja") or "").strip()
        cards.append(
            {
                "slug": slug,
                "name": slug,
                "label_ja": label_ja,
                "description": ctx.get("description") or "",
                "purpose": ctx.get("purpose") or "",
                "background": ctx.get("background") or "",
                "constraints": ctx.get("constraints") or [],
                "upstream": upstream_str,
                "downstream": downstream_str,
                "downstream_slugs": downstream_slugs,
                "languages_by_cat": languages_by_cat,
            }
        )
    return cards


def _render_markdown_prose(text: str) -> str:
    """description 内の素朴な Markdown（段落 / `- ` 箇条書き / `**強調**`）を HTML 化する。

    本格的な MD パーサは導入しない（依存最小化のため）。description はテンプレ準拠の
    bullet と段落を想定。改行 1 つを段落区切りとし、`- ` 行は <ul><li> として纏める。
    `**...**` を <strong> に変換、それ以外はテキストとしてエスケープ済みで出力する。
    """
    if not text.strip():
        return ""
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: list[str] = []
    bullet_buffer: list[str] = []

    def flush_bullets() -> None:
        if bullet_buffer:
            items = "\n      ".join(f"<li>{ln}</li>" for ln in bullet_buffer)
            out.append(f"<ul>\n      {items}\n    </ul>")
            bullet_buffer.clear()

    para_buffer: list[str] = []

    def flush_para() -> None:
        if para_buffer:
            joined = " ".join(para_buffer).strip()
            if joined:
                out.append(f"<p>{joined}</p>")
            para_buffer.clear()

    for raw in lines:
        s = raw.strip()
        if not s:
            flush_bullets()
            flush_para()
            continue
        if s.startswith("- "):
            flush_para()
            bullet_buffer.append(_inline_md(s[2:].strip()))
            continue
        flush_bullets()
        para_buffer.append(_inline_md(s))
    flush_bullets()
    flush_para()
    return "\n    ".join(out)


_INLINE_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _inline_md(text: str) -> str:
    """インライン MD（`**強調**` のみ）を HTML 化。それ以外はエスケープ。"""
    parts: list[str] = []
    pos = 0
    for m in _INLINE_MD_BOLD_RE.finditer(text):
        parts.append(esc(text[pos:m.start()]))
        parts.append(f"<strong>{esc(m.group(1))}</strong>")
        pos = m.end()
    parts.append(esc(text[pos:]))
    return "".join(parts)


def render_bc_cards(cards: list[dict]) -> str:
    if not cards:
        return '<div class="todo-placeholder">TODO: フェーズ4完了後に追記</div>'
    out = []
    for c in cards:
        desc_html = _render_markdown_prose(c.get("description") or "")
        intent_html = render_intent_blocks(c)
        lang_html = _render_bc_languages(c.get("languages_by_cat") or [])
        label_ja = c.get("label_ja") or ""
        if label_ja:
            heading = (
                f'<span class="label-ja">{esc(label_ja)}</span>'
                f' <span class="dash">—</span> '
                f'<span class="slug">{esc(c["name"])}</span>'
            )
        else:
            heading = f'<span class="slug">{esc(c["name"])}</span>'
        out.append(
            f'<div class="bc-card">\n'
            f'    <h3>{heading}</h3>\n'
            f"    {desc_html}\n"
            f'    <div class="dep"><strong>UPSTREAM:</strong> {esc(c["upstream"])} · '
            f'<strong>DOWNSTREAM:</strong> {esc(c["downstream"])}</div>\n'
            f"    {intent_html}\n"
            f"    {lang_html}\n"
            f"  </div>"
        )
    return "\n  ".join(out)


def _render_bc_languages(
    languages_by_cat: list[tuple[str, list[tuple[str, str]]]]
) -> str:
    """BC カードの LANGUAGE をカテゴリ別タイプ表として描画する。

    各カテゴリごとに `日本語ラベル | 英語識別子` の 2 列表を出す。
    順序は LANG_CATEGORIES の宣言順（集約→VO→Actor→CMD→EVT→POL→QRY）。
    """
    if not languages_by_cat:
        return ""
    sections: list[str] = []
    for cat_label, rows in languages_by_cat:
        body_rows = "\n        ".join(
            f"<tr><td>{esc(jp)}</td><td class=\"code-cell\">{esc(en)}</td></tr>"
            for en, jp in rows
        )
        sections.append(
            f'<div class="lang-cat">\n'
            f"      <h4>{esc(cat_label)}</h4>\n"
            f'      <table class="lang-table">\n'
            f"        <thead><tr><th>日本語</th><th>英語</th></tr></thead>\n"
            f"        <tbody>\n        {body_rows}\n        </tbody>\n"
            f"      </table>\n"
            f"    </div>"
        )
    body = "\n    ".join(sections)
    return (
        f'<div class="lang-section">\n'
        f'      <div class="lang-section-label"><strong>用語集</strong></div>\n'
        f"      {body}\n"
        f"    </div>"
    )


def render_intent_blocks(card: dict) -> str:
    """目的・背景・制約サブセクションを HTML として描画する共通関数。

    AGG カード・BC カードのいずれにも使う。3 項目すべてが空なら空文字を返す。
    """
    purpose = card.get("purpose", "") or ""
    background = card.get("background", "") or ""
    constraints = card.get("constraints", []) or []
    if not (purpose or background or constraints):
        return ""
    parts: list[str] = []
    if purpose:
        parts.append(
            f'<div class="purpose-section">'
            f"<strong>目的:</strong> {esc(purpose)}"
            f"</div>"
        )
    if background:
        parts.append(
            f'<div class="background-section">'
            f"<strong>背景:</strong> {esc(background)}"
            f"</div>"
        )
    if constraints:
        items = "\n      ".join(f"<li>{esc(x)}</li>" for x in constraints)
        parts.append(
            f'<div class="constraints-section">'
            f"<strong>制約:</strong>"
            f"<ul>\n      {items}\n    </ul>"
            f"</div>"
        )
    return "\n    ".join(parts)


def render_context_map(cards: list[dict]) -> str:
    """BC 依存関係を簡易 SVG として描画"""
    if not cards:
        return ""
    n = len(cards)
    if n == 0:
        return ""
    width = 600
    height = max(200, 80 * n + 60)
    cx = width // 2
    box_w = 180
    box_h = 50
    gap_y = 80
    start_y = 40

    boxes = []
    bc_y: dict[str, int] = {}
    for i, c in enumerate(cards):
        y = start_y + i * gap_y
        x = cx - box_w // 2
        bc_y[c["slug"]] = y + box_h // 2
        # BC 名は kind-neutral な Blue Gray で描画する（Command 色との混同を避ける）。
        boxes.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="6" '
            f'fill="#CFD8DC" stroke="#37474F" stroke-width="2"/>'
            f'<text x="{cx}" y="{y + box_h // 2 + 5}" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="#263238">{esc(c["slug"])}</text>'
        )

    arrows = []
    for c in cards:
        # downstream_slugs（DML `contexts[].dn` 由来）から全ての矢印を描く。
        # 複数 DOWNSTREAM がある BC でも全ての関係を表現する。
        for target_slug in c.get("downstream_slugs") or []:
            if target_slug not in bc_y:
                continue
            y1 = bc_y[c["slug"]]
            y2 = bc_y[target_slug]
            if y1 == y2:
                continue
            arrows.append(
                f'<line x1="{cx + box_w // 2 + 10}" y1="{y1}" '
                f'x2="{cx + box_w // 2 + 10}" y2="{y2}" '
                f'stroke="#37474F" stroke-width="2" marker-end="url(#cm-arr)"/>'
                f'<text x="{cx + box_w // 2 + 30}" y="{(y1 + y2) // 2}" '
                f'font-size="11" fill="#455A64">downstream</text>'
            )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'style="max-width: {width}px; background: #FAFAFA; '
        f'border: 1px solid #CFD8DC; border-radius: 6px; padding: 8px;" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f"  <defs>\n"
        f'    <marker id="cm-arr" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M0 0L10 5L0 10z" fill="#37474F"/></marker>\n'
        f"  </defs>\n"
        f"  {' '.join(arrows)}\n"
        f"  {' '.join(boxes)}\n"
        f"</svg>"
    )
    return f"<h3>コンテキストマップ</h3>\n  {svg}"


def _render_attr_table(rows: list[dict], header_class: str = "") -> str:
    """`aggregates[].attrs` / `events[].params` の共通属性表レンダリング。

    各行は dict（{name, type, required, note}）。空リストなら ""（呼び出し側で抑制）。
    """
    if not rows:
        return ""
    body = "\n        ".join(
        f"<tr>"
        f"<td class=\"code-cell\">{esc(r.get('name', ''))}</td>"
        f"<td class=\"code-cell\">{esc(str(r.get('type', '')))}</td>"
        f"<td>{'✓' if r.get('required') else ''}</td>"
        f"<td>{esc(r.get('note', '') or '')}</td>"
        f"</tr>"
        for r in rows
    )
    cls = f'attr-table {header_class}'.strip()
    return (
        f'<table class="{cls}">\n'
        f"      <thead><tr><th>属性</th><th>型</th><th>必須</th><th>備考</th></tr></thead>\n"
        f"      <tbody>\n        {body}\n      </tbody>\n"
        f"    </table>"
    )


def _render_state_diagram(agg: dict, glossary_index: dict[str, str]) -> str:
    """AGG の states / transitions から Mermaid stateDiagram-v2 ブロックを生成する。

    Mermaid 構文:
        stateDiagram-v2
            state "計算済み" as CALCULATED
            CALCULATED --> CONSUMED : PlaceOrder
            CALCULATED --> EXPIRED : ExpireQuote

    transitions が無い AGG は空文字を返す（HTML 側で何も描画されない）。
    """
    transitions = agg.get("transitions") or []
    states = agg.get("states") or []
    if not transitions:
        return ""

    lines: list[str] = ["stateDiagram-v2"]

    # 状態に日本語ラベルを与える
    declared: set[str] = set()
    for s in states:
        s_name = str(s)
        jp = localize(s_name, glossary_index)
        label = jp if jp and jp != s_name else s_name
        # ラベル/識別子は信頼できない DML 由来。esc() で HTML エスケープし、
        # <pre class="mermaid"> からの要素脱出（</pre> 注入による stored XSS）を防ぐ
        lines.append(f'    state "{esc(label)}" as {esc(s_name)}')
        declared.add(s_name)

    # 遷移行（from -> to : via）
    for t in transitions:
        if not isinstance(t, dict):
            continue
        frm = str(t.get("from", "")).strip()
        to = t.get("to", "")
        via = str(t.get("via", "")).strip()
        if not frm or not to:
            continue
        targets = to if isinstance(to, list) else [to]
        for tgt in targets:
            tgt = str(tgt).strip()
            if not tgt:
                continue
            for needed in (frm, tgt):
                if needed and needed not in declared:
                    lines.append(f'    state "{esc(needed)}" as {esc(needed)}')
                    declared.add(needed)
            if via:
                via_jp = localize(via, glossary_index)
                via_label = via_jp if via_jp and via_jp != via else via
                lines.append(f"    {esc(frm)} --> {esc(tgt)} : {esc(via_label)}")
            else:
                lines.append(f"    {esc(frm)} --> {esc(tgt)}")

    return (
        '<div class="state-diagram">\n'
        '      <div class="state-diagram-label">状態遷移図</div>\n'
        '      <pre class="mermaid">\n' + "\n".join(lines) + "\n      </pre>\n"
        "    </div>"
    )


def render_agg_cards_from_dml(
    model: dict, glossary_index: dict[str, str]
) -> str:
    """DML `aggregates[]` から集約カードを描画する（旧 Zod ブロックは廃止）。

    各カード: コンテキスト · 関連シナリオ → 目的/背景/制約 → 属性表 → 状態/状態遷移 →
    不変条件（scenarios[].rules を agg 一致で集約）→ エラーケース（scenarios[].errs を agg 一致で集約）
    → イベントごとのペイロード表（events[].params）。
    """
    enriched = aggregates_from_dml(model)
    if not enriched:
        return '<div class="todo-placeholder">TODO: DML に aggregates[] 未記述</div>'

    out: list[str] = []
    for a in enriched:
        rel = "・".join(f"`{n}`" for n in a["related_scenarios"]) or "—"
        meta = (
            f'<div class="dep"><strong>コンテキスト:</strong> '
            f'<code>{esc(a["ctx"])}</code> · '
            f'<strong>関連シナリオ:</strong> {esc(rel)}</div>'
        )
        intent_html = render_intent_blocks({
            "purpose": a["purpose"],
            "background": a["background"],
            "constraints": a["constraints"],
        })

        attr_html = _render_attr_table(a["attrs"])
        if not attr_html:
            attr_html = (
                '<div class="agg-subsection"><em style="color:#90A4AE;">'
                "属性未記述（DML aggregates[].attrs[] 追記）</em></div>"
            )

        def _state_label(state: str) -> str:
            """状態を「日本語 (CODE)」形式に整形（日本語名を左、英語名を右に）。"""
            jp = localize(state, glossary_index)
            if jp and jp != state:
                return f'{esc(jp)} <code class="state-code">{esc(state)}</code>'
            return f'<code>{esc(state)}</code>'

        state_diagram_html = _render_state_diagram(a, glossary_index)

        states_html = ""
        if a["states"]:
            states_html = (
                '<div class="agg-subsection"><strong>状態:</strong> '
                + " → ".join(_state_label(s) for s in a["states"])
                + "</div>"
            )

        transitions_html = ""
        if a["transitions"]:
            items = []
            for t in a["transitions"]:
                frm_html = _state_label(str(t.get("from", "")))
                to = t.get("to", "")
                to_html = (
                    " | ".join(_state_label(str(x)) for x in to)
                    if isinstance(to, list) else _state_label(str(to))
                )
                via = esc(str(t.get("via", "")))
                via_jp = esc(localize(str(t.get("via", "")), glossary_index))
                when = t.get("when") or t.get("note") or ""
                when_html = f' <span class="why">（{esc(when)}）</span>' if when else ""
                via_label = f"<code>{via}</code>" + (
                    f" <span class=\"why\">({via_jp})</span>" if via_jp and via_jp != via else ""
                )
                items.append(
                    f"<li>{frm_html} → {to_html} via {via_label}{when_html}</li>"
                )
            transitions_html = (
                '<details class="agg-subsection transitions-details">'
                '<summary><strong>状態遷移（詳細）</strong> '
                '<span class="why">— POL / when 補足を含む</span></summary>'
                f"<ul>\n      " + "\n      ".join(items) + "\n    </ul></details>"
            )

        inv_html = ""
        if a["invariants"]:
            items = []
            for r in a["invariants"]:
                base = esc(r.get("rule", ""))
                why = r.get("why") or ""
                why_html = f' <span class="why">— {esc(why)}</span>' if why else ""
                items.append(f"<li>{base}{why_html}</li>")
            inv_html = (
                '<div class="inv-section"><strong>✓ 不変条件:</strong>'
                f"<ul>\n      " + "\n      ".join(items) + "\n    </ul></div>"
            )

        err_html = ""
        if a["errors"]:
            items = []
            for e in a["errors"]:
                err = esc(e.get("err", ""))
                cond = esc(e.get("cond", ""))
                when = e.get("when") or e.get("note") or ""
                when_html = f' <span class="why">（{esc(when)}）</span>' if when else ""
                items.append(
                    f'<li><code class="err-code">{err}</code>: {cond}{when_html}</li>'
                )
            err_html = (
                '<div class="err-section"><strong>⚠ エラーケース:</strong>'
                f"<ul>\n      " + "\n      ".join(items) + "\n    </ul></div>"
            )

        events_html = ""
        if a["events"]:
            parts = []
            for ev in a["events"]:
                name = ev.get("name", "")
                name_jp = localize(name, glossary_index)
                title = esc(name) + (
                    f" <span class=\"why\">({esc(name_jp)})</span>"
                    if name_jp and name_jp != name else ""
                )
                params_html = _render_attr_table(
                    ev.get("params") or [], header_class="payload-table"
                )
                if not params_html:
                    params_html = (
                        '<div class="agg-subsection"><em style="color:#90A4AE;">'
                        "ペイロード未記述（params[] 追記）</em></div>"
                    )
                note = ev.get("note") or ""
                note_html = (
                    f'<div class="agg-subsection" style="margin-top:4px;color:#455A64;">'
                    f"{esc(note)}</div>" if note else ""
                )
                parts.append(
                    f'<div class="agg-event">\n'
                    f"      <h4>{title}</h4>\n"
                    f"      {note_html}\n"
                    f"      {params_html}\n"
                    f"    </div>"
                )
            events_html = (
                '<div class="agg-events">\n'
                "    <strong>イベントペイロード:</strong>\n    "
                + "\n    ".join(parts)
                + "\n  </div>"
            )

        sections = [
            meta, intent_html, attr_html, states_html,
            state_diagram_html, transitions_html, inv_html, err_html, events_html,
        ]
        agg_label_ja = glossary_index.get(a["name"], "")
        if agg_label_ja and agg_label_ja != a["name"]:
            heading = (
                f'<span class="label-ja">{esc(agg_label_ja)}</span>'
                f' <span class="dash">—</span> '
                f'<span class="slug">{esc(a["name"])}</span>'
            )
        else:
            heading = f'<span class="slug">{esc(a["name"])}</span>'
        out.append(
            f'<div class="bc-card">\n'
            f'    <h3>{heading}</h3>\n'
            "    " + "\n    ".join(s for s in sections if s)
            + "\n  </div>"
        )
    return "\n  ".join(out)


def render_decisions(model: dict, glossary_index: dict[str, str]) -> str:
    """DML `decisions[]` から意思決定ログを描画する。

    各カード: トピック・採用 ・影響要素 / 各オプション（採用 ✓ 緑 ／ 不採用 灰・取り消し線）。
    decisions[] が空なら "" を返し、呼び出し側で見出しごと抑制する。
    """
    decisions = (model or {}).get("decisions") or []
    if not decisions:
        return ""
    out: list[str] = []
    for d in decisions:
        did = esc(d.get("id", ""))
        topic = esc(d.get("topic", ""))
        chosen = d.get("chosen", "")
        options = d.get("options") or []
        # chosen に対応する option を引き、label があれば「label (name)」形式で見出しに反映
        chosen_label = ""
        for opt in options:
            if opt.get("name") == chosen:
                chosen_label = opt.get("label") or ""
                break
        chosen_html = (
            f'<code>{esc(chosen_label)}</code> <code class="opt-id">({esc(str(chosen))})</code>'
            if chosen_label else f'<code>{esc(str(chosen))}</code>'
        )
        affects = d.get("affects") or []
        affects_html = ""
        if affects:
            chips = " ".join(
                f"<code>{esc(localize(str(a), glossary_index))}</code>"
                for a in affects
            )
            affects_html = f" · <strong>影響:</strong> {chips}"
        opts_html_parts: list[str] = []
        for opt in options:
            name = opt.get("name", "")
            label = opt.get("label") or ""
            adopted = opt.get("adopted")
            if adopted is None:
                adopted = (name == chosen)
            cls = "adopted" if adopted else "rejected"
            if adopted:
                reason = opt.get("why") or ""
                marker = "✓ "
                reason_html = (
                    f'<span class="opt-why">{esc(reason)}</span>' if reason else ""
                )
            else:
                reason = opt.get("why_not") or opt.get("why") or ""
                marker = ""
                reason_html = (
                    f'<span class="opt-why-not">{esc(reason)}</span>' if reason else ""
                )
            # label があれば日本語ラベルを左、英語識別子をその右の括弧書きに
            if label:
                name_html = (
                    f'<span class="opt-name">{marker}{esc(label)}'
                    f' <span class="opt-id">({esc(name)})</span></span>'
                )
            else:
                name_html = f'<span class="opt-name">{marker}{esc(name)}</span>'
            opts_html_parts.append(
                f'<div class="opt {cls}">'
                f'{name_html}'
                f"{reason_html}"
                f"</div>"
            )
        opts_html = "\n      ".join(opts_html_parts)
        note = d.get("note") or ""
        note_html = (
            f'<div class="decision-note">{esc(note)}</div>' if note else ""
        )
        out.append(
            f'<div class="decision-card">\n'
            f'    <h3>{did}. {topic}</h3>\n'
            f'    <div class="dep"><strong>採用:</strong> '
            f'{chosen_html}{affects_html}</div>\n'
            f'    <div class="decision-options">\n      {opts_html}\n    </div>\n'
            f"    {note_html}\n"
            f"  </div>"
        )
    return "\n  ".join(out)


def render_qry_cards(qrys: list[dict]) -> str:
    """`queries[]`（旧 .md §9）をリードモデルカードとして描画。

    新スキーマでは name/ctx/purpose/users/sources/formula を持つ。
    """
    if not qrys:
        return '<div class="todo-placeholder">TODO: フェーズ4〜5完了後に追記</div>'
    out = []
    for q in qrys:
        name = q.get("name") or ""
        ctx = q.get("ctx") or ""
        purpose = q.get("purpose") or ""
        users = q.get("users") or ""
        sources_raw = q.get("sources") or []
        if isinstance(sources_raw, list):
            sources = " · ".join(str(s) for s in sources_raw if s)
        else:
            sources = str(sources_raw)
        formula = q.get("formula") or ""
        ctx_html = f' <code style="font-size: 12px; color: #607D8B;">{esc(ctx)}</code>' if ctx else ""
        out.append(
            f'<div class="bc-card" style="border-left: 4px solid #2E7D32;">\n'
            f'    <h3 style="color: #2E7D32;">{esc(name)}{ctx_html}</h3>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>利用者:</strong> {esc(users)}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>目的:</strong> {esc(purpose)}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>ソース:</strong> {esc(sources)}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>算出:</strong> {esc(formula)}</p>\n'
            f"  </div>"
        )
    return "\n  ".join(out)


def render_questions(questions: list[dict]) -> str:
    """`questions[]`（旧 .md §5）をオープン/クローズで色分け描画する。

    新スキーマ: { id, topic, why, status: open|closed, decision_id? }。
    旧 MD の番号 Q{n} 表記を維持するため id をそのまま使う（先頭が Q なら除去して表示）。
    """
    if not questions:
        return '<div class="todo-placeholder">未確認事項なし</div>'

    open_qs = [q for q in questions if q.get("status") != "closed"]
    closed_qs = [q for q in questions if q.get("status") == "closed"]

    parts: list[str] = []
    if not open_qs and closed_qs:
        parts.append(
            '<p style="color: #2E7D32; font-weight: 600;">✅ すべて解決済み</p>'
        )

    def _label(q: dict) -> str:
        qid = str(q.get("id") or "")
        return f"Q{qid[1:]}" if qid.startswith("Q") and qid[1:].isdigit() else qid

    def _body(q: dict) -> str:
        topic = q.get("topic") or ""
        why = q.get("why") or ""
        if topic and why:
            return f"{topic} — {why}"
        return topic or why

    for q in open_qs:
        parts.append(
            f'<div class="question"><strong>{esc(_label(q))}.</strong> {esc(_body(q))}</div>'
        )
    for q in closed_qs:
        suffix = ""
        did = q.get("decision_id")
        if did:
            suffix = f' <code style="color: #2E7D32; margin-left: 6px;">→ {esc(did)}</code>'
        parts.append(
            f'<div class="question" style="background: #E8F5E9; border-left-color: #2E7D32;">'
            f'<strong>[CLOSED] {esc(_label(q))}.</strong> {esc(_body(q))}{suffix}</div>'
        )

    return "\n  ".join(parts)


def render_actions(actions: list[dict], status: str) -> str:
    """`actions[]`（旧 .md §4）を次のアクションとして描画。

    新スキーマ: { id, text, owner?, done? }。done=true は取り消し線で表示。
    """
    if not actions:
        return '<div class="todo-placeholder">未定</div>'
    items: list[str] = []
    for a in actions:
        text = a.get("text") or ""
        done = bool(a.get("done"))
        owner = a.get("owner") or ""
        owner_html = f' <em style="color: #607D8B;">[{esc(owner)}]</em>' if owner else ""
        if done:
            items.append(
                f'<li style="text-decoration: line-through; color: #9E9E9E;">{esc(text)}{owner_html}</li>'
            )
        else:
            items.append(f"<li>{esc(text)}{owner_html}</li>")
    items_html = "\n      ".join(items)
    return f'<div class="next-actions">\n    <ul>\n      {items_html}\n    </ul>\n  </div>'


def render_dml(dml: str, errors: list[str] | None = None) -> str:
    banner = render_dml_banner(dml, errors)
    if not dml.strip():
        return banner + '<div class="todo-placeholder">TODO</div>'
    return banner + f'<pre class="code">{highlight_dml(dml)}</pre>'


def render_dml_banner(dml: str, errors: list[str] | None) -> str:
    """JSON Schema 検証結果のバナー。違反があれば一覧、無ければ ✅、未記述は何も出さない。"""
    if not dml.strip():
        return ""
    if errors:
        items = "\n".join(f"<li>{esc(e)}</li>" for e in errors)
        return (
            '<div class="dml-banner dml-banner-error">'
            f"⚠ DML スキーマ違反 {len(errors)} 件（構文のみ検証）"
            f"<ul>{items}</ul></div>"
        )
    return '<div class="dml-banner dml-banner-ok">✅ DML スキーマ OK（構文検証）</div>'


# ============================================================
# シンタックスハイライト
# ============================================================

# DML（YAML）の値を「キー名」に応じて付箋色クラスへ割り当てる
DML_VALUE_CLASS_BY_KEY = {
    "actor": "v-actor",
    "agg": "v-actor",
    "cmd": "v-cmd",
    "evt": "v-evt",
    # trg / trgs.evts は「POL が購読するトリガ参照」。発生したイベント (evt/emits) と
    # 同じ橙にすると因果連鎖が読みづらいので Amber (v-trg) で区別する。
    "trg": "v-trg",
    "emits": "v-evt",
    "evts": "v-trg",        # v2: trgs の join イベント（trg と同等の購読側）
    "qry": "v-qry",
    "pol": "v-pol",
    "err": "v-err",
    # v2 メタ（CML 由来の任意フィールド）
    "type": "v-meta",
    "vision": "v-meta",
    "sub": "v-meta",
    "resp": "v-meta",
    "tech": "v-meta",
    "purpose": "v-meta",
    "brMode": "v-meta",
    "mode": "v-meta",
    # v3: AGG トップレベル化（aggregates[].{transitions, attrs, events}）
    "via": "v-cmd",         # transition のトリガー CMD
    "from": "v-meta",       # 状態遷移の起点（upperSnake）
    "to": "v-meta",         # 状態遷移の終点
}

_YAML_KEY_RE = re.compile(r"^([\w-]+):(\s*)(.*)$")
_YAML_BLOCK_KEY_RE = re.compile(r"^([\w-]+):\s*$")


def _split_yaml_comment(s: str) -> tuple[str, str | None]:
    """行末コメント `# ...` を分離する（クォート内の # は無視）。"""
    in_single = in_double = False
    for i, ch in enumerate(s):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and (i == 0 or s[i - 1] == " "):
            return s[:i].rstrip(), s[i:]
    return s, None


def _yaml_value_class(key: str, section: str) -> str:
    """key（と所属セクション）から値の色クラスを決める。"""
    if key == "name" and section == "policies":
        return "v-pol"
    return DML_VALUE_CLASS_BY_KEY.get(key, "v-str")


def _render_yaml_body(body: str, stack: list[tuple[int, str]], section: str) -> str:
    """list マーカー除去後の本体（`key: value` / 裸スカラー）を span 化する。"""
    if not body:
        return ""
    m = _YAML_KEY_RE.match(body)
    if m:
        key, gap, value = m.group(1), m.group(2), m.group(3)
        key_html = f'<span class="yk">{esc(key)}</span>:'
        if value == "":
            return key_html
        cls = _yaml_value_class(key, section)
        return f'{key_html}{gap}<span class="{cls}">{esc(value)}</span>'
    # 裸スカラー（リスト項目）: 直近の親キーで色付け（qry → 緑、pol → 紫 等）
    parent = stack[-1][1] if stack else ""
    cls = DML_VALUE_CLASS_BY_KEY.get(parent, "v-str")
    return f'<span class="{cls}">{esc(body)}</span>'


def highlight_dml(dml: str) -> str:
    """DML（YAML）を役割ベースの意味色でシンタックスハイライトする。

    値の色はキー名に対応（evt/trigger/emits=橙, cmd=青, actor/agg=黄,
    qry=緑, pol/policy=紫, error=赤）。キー名は淡色、コメントは灰イタリック。
    付箋フロー図と同じカラーパレットで DML を読めるようにする。
    """
    out: list[str] = []
    stack: list[tuple[int, str]] = []  # (列, ブロックキー名)
    section = ""  # トップレベル contexts / scenarios / policies
    for raw in dml.split("\n"):
        if not raw.strip():
            out.append("")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        indent_str = raw[:indent]
        stripped = raw[indent:]

        # コメント専用行
        if stripped.startswith("#"):
            out.append(f'{indent_str}<span class="cm">{esc(stripped)}</span>')
            continue

        content, comment = _split_yaml_comment(stripped)

        marker = ""
        body = content
        if body.startswith("- "):
            marker, body = "- ", body[2:]
        elif body == "-":
            marker, body = "-", ""
        col = indent + len(marker)

        # スタック整理（同列以上のブロックキーを破棄）
        while stack and stack[-1][0] >= col:
            stack.pop()

        if indent == 0:
            mb = _YAML_BLOCK_KEY_RE.match(body)
            if mb and mb.group(1) in ("contexts", "aggregates", "scenarios", "policies"):
                section = mb.group(1)

        body_html = _render_yaml_body(body, stack, section)

        mb = _YAML_BLOCK_KEY_RE.match(body)
        if mb:
            stack.append((col, mb.group(1)))

        line = indent_str + (esc(marker) if marker else "") + body_html
        if comment is not None:
            sep = " " if (marker or body_html) else ""
            line += f'{sep}<span class="cm">{esc(comment)}</span>'
        out.append(line)
    return "\n".join(out)


# ============================================================
# テンプレ処理
# ============================================================


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render_html(doc: DMLDocument) -> str:
    template = load_template()

    session_dict = doc.session or {}
    title = session_dict.get("domain") or session_dict.get("id") or "EventStorming"
    session_id = session_dict.get("id") or ""
    goal = session_dict.get("goal") or ""
    status = session_dict.get("status") or ""
    phase = session_dict.get("phase")

    html = template

    # テンプレ冒頭の編集ガイド用コメント（v5 以前のワークフロー説明）を出力から除去する。
    # <!DOCTYPE html> の直後・<html> の前にある最初の HTML コメントブロックが対象。
    html = re.sub(
        r"(<!DOCTYPE html>\s*)<!--.*?-->\s*",
        r"\1",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # <title>（<head> 内）のプレースホルダーを差し替える
    html = re.sub(
        r"<title>EventStorming — \{\{ドメイン名\}\}</title>",
        f"<title>EventStorming — {esc(title)}</title>",
        html,
    )

    # ヘッダー（テンプレのプレースホルダーを差し替える）
    html = re.sub(
        r"<h1>EventStorming — \{\{ドメイン名\}\}</h1>",
        f"<h1>EventStorming — {esc(title)}</h1>",
        html,
    )
    html = re.sub(
        r"Session:\s*<code>\{\{eventstorming-YYYYMMDD-HHMM\}\}</code>\s*·\s*\n\s*Goal:\s*\{\{ゴール\}\}",
        f"Session: <code>{esc(session_id)}</code> · Goal: {esc(goal)}",
        html,
    )

    body_html = build_body_html(doc, title, session_id, goal, status, phase)
    html = re.sub(
        r"<body>.*?</body>",
        f"<body>\n{body_html}\n</body>",
        html,
        flags=re.DOTALL,
    )

    return html


def build_body_html(
    doc: DMLDocument, title: str, session: str, goal: str, status: str,
    phase: str | None = None,
) -> str:
    progress_html = render_progress(status, phase)
    narratives_html = render_narratives(doc.narratives)
    # glossary_index は DML `contexts[].lang` を全 BC 走査して機械的に生成する。
    # フロー図ラベルや §6 意思決定ログの affects 表示で英語識別子を日本語に置換する。
    glossary_index = build_glossary_index_from_dml(doc.model)

    decisions_html = ""
    if doc.model is not None:
        flows = build_flows_from_dml(doc.model, glossary_index)
        flows_html = render_flows(flows)
        agg_cards_html = render_agg_cards_from_dml(doc.model, glossary_index)
        decisions_html = render_decisions(doc.model, glossary_index)
    else:
        flows_html = (
            '<div class="todo-placeholder">'
            "DML 解析不可（PyYAML 不在 / 未記述）— §10 を参照"
            "</div>"
        )
        agg_cards_html = (
            '<div class="todo-placeholder">DML 解析不可 — §10 を参照</div>'
        )

    bc_cards = bc_cards_from_dml(doc.model)
    context_map_html = render_context_map(bc_cards)
    bc_cards_html = render_bc_cards(bc_cards)
    qry_cards_html = render_qry_cards(doc.qrys)
    questions_html = render_questions(doc.questions)
    actions_html = render_actions(doc.actions, status)
    dml_html = render_dml(doc.dml_text, doc.dml_errors)

    # §5 意思決定ログ（v8 で §1/§2 統合・全体繰り上げ後の番号）。
    # decisions[] が空なら見出しごと非表示
    decisions_block = (
        f"\n  <h2>5. 意思決定ログ</h2>\n  {decisions_html}\n"
        if decisions_html else ""
    )

    return f"""
  <h1>EventStorming — {esc(title)}</h1>
  <div class="meta">
    Session: <code>{esc(session)}</code> ·
    Status: <strong>{esc(status)}</strong> ·
    Goal: {esc(goal)}
  </div>

  <div class="progress">
    {progress_html}
  </div>

  <h2>1. ストーリー</h2>
  {narratives_html}

  <h2>2. Event Walkthrough</h2>
  {flows_html}

  <h2>3. 次のアクション</h2>
  {actions_html}

  <h2>4. オープンクエスチョン</h2>
  {questions_html}
{decisions_block}
  <h2>6. コンテキスト候補</h2>
  {context_map_html}
  {bc_cards_html}

  <h2>7. 集約候補</h2>
  {agg_cards_html}

  <h2>8. リードモデル候補</h2>
  {qry_cards_html}

  <details class="dml-details">
    <summary><h2>9. DML</h2></summary>
    {dml_html}
  </details>
""".strip()


# ============================================================
# ビルド本体
# ============================================================


def _validate_dml_warn(dml_text: str, dml_path: Path) -> list[str]:
    """DML を JSON Schema で検証し、違反を stderr に警告出力して一覧を返す。

    検証は **非ブロッキング**。validate_dml が import できない / スキーマが無い等は
    静かに空リストを返し、ビルドを止めない。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from validate_dml import validate_dml_text

        errors = validate_dml_text(dml_text)
    except Exception as e:  # 検証基盤の不在・想定外は警告のみでスキップ
        print(f"⚠ DML 検証スキップ: {e}", file=sys.stderr)
        return []
    for e in errors:
        print(f"⚠ DML schema: {dml_path.name}: {e}", file=sys.stderr)
    return errors


def _session_stem(yaml_path: Path) -> str:
    """`*.dml.yaml` からセッション識別子（`.dml.yaml` を剥がした名前）を取り出す。"""
    name = yaml_path.name
    if name.endswith(".dml.yaml"):
        return name[: -len(".dml.yaml")]
    return yaml_path.stem


def build(
    yaml_path: Path,
    out_dir: Path,
    *,
    artifact: bool = False,
) -> Path:
    """`*.dml.yaml` 1 つから HTML を生成する（YAML-only パイプライン）。"""
    if not yaml_path.name.endswith(".dml.yaml"):
        raise ValueError(
            f"入力は *.dml.yaml である必要があります（received: {yaml_path.name}）。"
            " v5 以降 `.md` 入力はサポートされません。"
        )
    yaml_text = yaml_path.read_text(encoding="utf-8")
    doc = load_dml_document(yaml_text)
    # JSON Schema 検証（警告のみ・non-blocking）。違反は §10 バナーと stderr に出すが
    # ビルドは止めない（編集途中の不完全 DML でも HTML プレビューを保つ）。
    doc.dml_errors = _validate_dml_warn(yaml_text, yaml_path)
    html = render_html(doc)

    if artifact:
        html = strip_for_artifact(html)
        suffix = "-artifact.html"
    else:
        suffix = ".html"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (_session_stem(yaml_path) + suffix)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def strip_for_artifact(html: str) -> str:
    """Claude Artifact 互換に整形する。

    - `<meta http-equiv="refresh">` を除去（Artifact 内でのリロードを防ぐ）
    - `.reload-note` の案内 div を除去（自動更新は Artifact では機能しない）
    """
    html = re.sub(
        r'[ \t]*<meta http-equiv="refresh"[^>]*>\s*\n',
        "",
        html,
    )
    html = re.sub(
        r'[ \t]*<div class="reload-note">.*?</div>\s*\n',
        "",
        html,
    )
    return html


def copy_to_clipboard(path: Path) -> bool:
    """生成済み HTML を pbcopy でクリップボードに送る（macOS 限定）。"""
    if sys.platform != "darwin":
        print("⚠ --copy は macOS の pbcopy のみ対応", file=sys.stderr)
        return False
    try:
        with path.open("rb") as f:
            subprocess.run(["pbcopy"], stdin=f, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError, OSError) as e:
        print(f"⚠ クリップボードへのコピー失敗: {e}", file=sys.stderr)
        return False
    print(f"📋 クリップボードへコピー: {path.name}")
    return True


def build_all(in_dir: Path, out_dir: Path, *, artifact: bool = False) -> list[Path]:
    results = []
    for yaml_path in sorted(in_dir.glob("*.dml.yaml")):
        try:
            out = build(yaml_path, out_dir, artifact=artifact)
            results.append(out)
            print(f"✅ {yaml_path.name} → {out.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"❌ {yaml_path.name}: {e}", file=sys.stderr)
    return results


def watch(in_dir: Path, out_dir: Path, interval: float = 1.0) -> None:
    print(f"👀 監視中: {in_dir} (Ctrl-C で停止)")
    mtimes: dict[Path, float] = {
        p: p.stat().st_mtime for p in in_dir.glob("*.dml.yaml")
    }
    try:
        while True:
            for yaml_path in in_dir.glob("*.dml.yaml"):
                mtime = yaml_path.stat().st_mtime
                prev = mtimes.get(yaml_path)
                if prev is None or mtime > prev:
                    mtimes[yaml_path] = mtime
                    try:
                        out = build(yaml_path, out_dir)
                        print(f"♻️  {yaml_path.name} → {out.relative_to(PROJECT_ROOT)}")
                    except Exception as e:
                        print(f"❌ {yaml_path.name}: {e}", file=sys.stderr)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 停止しました")


# ============================================================
# CLI
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EventStorming DML → HTML ビルダー（YAML-only）",
    )
    parser.add_argument("path", nargs="?", help="*.dml.yaml ファイルパス（省略時は --all か --watch）")
    parser.add_argument("--all", action="store_true", help="全 *.dml.yaml をビルド")
    parser.add_argument("--watch", action="store_true", help="ファイル変更を監視して自動ビルド")
    parser.add_argument(
        "--artifact",
        action="store_true",
        help="Claude Artifact 互換 HTML を生成（meta-refresh 除去 / <session>-artifact.html）",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="生成した HTML をクリップボード(pbcopy)へコピー（macOS 限定）",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"出力ディレクトリ (default: {DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)})",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)

    if args.watch:
        in_dir = Path(args.path) if args.path else DEFAULT_INPUT_DIR
        if not in_dir.is_dir():
            print(f"❌ ディレクトリではありません: {in_dir}", file=sys.stderr)
            return 1
        watch(in_dir, out_dir)
        return 0

    if args.all:
        build_all(DEFAULT_INPUT_DIR, out_dir, artifact=args.artifact)
        if args.copy:
            print("⚠ --copy は単一ファイル指定時のみ有効です", file=sys.stderr)
        return 0

    if not args.path:
        parser.print_help()
        return 1

    yaml_path = Path(args.path)
    # hook が `.md` を渡してきた場合は兄弟 `.dml.yaml` を入力として解決する。
    if yaml_path.suffix == ".md":
        sibling = yaml_path.with_name(yaml_path.stem + ".dml.yaml")
        if sibling.exists():
            yaml_path = sibling
        else:
            print(
                f"❌ v5 以降 `.md` 入力は廃止されました。{sibling.name} を作成してください",
                file=sys.stderr,
            )
            return 1
    if not yaml_path.exists():
        print(f"❌ ファイルが見つかりません: {yaml_path}", file=sys.stderr)
        return 1

    try:
        out = build(yaml_path, out_dir, artifact=args.artifact)
        print(f"✅ {yaml_path.name} → {out.relative_to(PROJECT_ROOT)}")
        if args.copy:
            copy_to_clipboard(out)
        return 0
    except Exception as e:
        print(f"❌ ビルド失敗: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
