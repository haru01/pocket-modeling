#!/usr/bin/env python3
"""EventStorming MD → HTML ビルダー

使い方:
    python3 scripts/eventstorming_build.py <md_path>              # 個別ビルド
    python3 scripts/eventstorming_build.py --all                  # 全件ビルド
    python3 scripts/eventstorming_build.py --watch [<md_dir>]     # 監視モード
    python3 scripts/eventstorming_build.py <md_path> --artifact   # Artifact 互換 HTML
    python3 scripts/eventstorming_build.py <md_path> --artifact --copy
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

# このスクリプトは .claude/skills/eventstorming-facilitator/scripts/ に配置されている想定
# SCRIPT_DIR = scripts/ なので SCRIPT_DIR.parents:
#   [0]=eventstorming-facilitator, [1]=skills, [2]=.claude, [3]=プロジェクトルート
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "docs" / "eventstorming"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist" / "eventstorming"
TEMPLATE_PATH = SKILL_ROOT / "templates" / "event-flow.html"

DSL_PREFIX_TO_KIND = {"@": "actor", "!": "command", "$": "policy", "?": "readmodel"}
KIND_LABEL = {
    "actor": "Actor",
    "command": "Command",
    "event": "Event",
    "policy": "Policy",
    "readmodel": "Read Model",
}
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
class MDSections:
    header: dict = field(default_factory=dict)
    story: str = ""
    scenarios: list[dict] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    bc_cards: list[dict] = field(default_factory=list)
    agg_cards: list[dict] = field(default_factory=list)
    qry_cards: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    hotspots: list[dict] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    dml: str = ""
    dml_errors: list[str] = field(default_factory=list)
    glossary: dict = field(default_factory=dict)


# ============================================================
# MD パーサ
# ============================================================


def parse_md(md_text: str) -> MDSections:
    s = MDSections()

    title_match = re.search(r"^# (.+)$", md_text, re.MULTILINE)
    if title_match:
        s.header["title"] = title_match.group(1).strip()

    # ヘッダーパターンを複数受け付ける(値側に**…** / キー側に**…** の両方)
    header_patterns = {
        "session": [
            r"^-?\s*Session:\s*(.+?)$",
            r"^-?\s*\*\*Session\*\*:\s*(.+?)$",
        ],
        "domain": [
            r"^-?\s*Domain:\s*(.+?)$",
            r"^-?\s*\*\*Domain\*\*:\s*(.+?)$",
        ],
        "status": [
            r"^-?\s*Status:\s*\*\*(.+?)\*\*",
            r"^-?\s*\*\*Status\*\*:\s*(.+?)$",
        ],
        "goal": [
            r"^-?\s*Goal:\s*(.+?)$",
            r"^-?\s*\*\*Goal\*\*:\s*(.+?)$",
        ],
    }
    for key, patterns in header_patterns.items():
        for pattern in patterns:
            m = re.search(pattern, md_text, re.MULTILINE)
            if m:
                s.header[key] = m.group(1).strip()
                break

    # セクション見出し: `## N) 名前` / `## N. 名前` / `## N 名前` のいずれも受付
    section_re = re.compile(r"^## \d+[).]?\s+(.+)$", re.MULTILINE)
    matches = list(section_re.finditer(md_text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()
        # セクション区切り `---` の行を除去（行単位で確実に処理）
        body = "\n".join(line for line in body.split("\n") if line.strip() != "---").strip()
        sections[name] = body

    # セクション名のエイリアス(英語名・日本語名どちらでも取得可能)
    def get_section(*names):
        for n in names:
            if n in sections:
                return sections[n]
        return ""

    s.story = get_section("Happy Path Story", "ハッピーパスストーリー")
    s.scenarios = parse_scenarios(
        get_section("代替シナリオ", "Alternative Scenarios")
    )
    s.flows = parse_flows(
        get_section("Event Walkthrough", "イベントフロー")
    )
    s.bc_cards = parse_bc_cards(
        get_section("コンテキスト候補", "BC Candidates", "Context Candidates")
    )
    s.agg_cards = parse_agg_cards(
        get_section("集約候補", "Aggregate Candidates")
    )
    s.qry_cards = parse_qry_cards(
        get_section("リードモデル候補", "Read Models")
    )
    s.questions, s.hotspots = parse_questions_hotspots(
        get_section("オープンクエスチョン", "Open Questions")
    )
    s.actions = parse_actions(
        get_section("次のアクション", "Next Actions")
    )
    s.dml = parse_dml(get_section("DML"))
    s.glossary = parse_glossary(get_section("用語集", "Glossary"))

    return s


def parse_scenarios(text: str) -> list[dict]:
    """代替シナリオを解析する。

    対応フォーマット:
    1. `### シナリオ名` 形式（テンプレート準拠）
    2. `1. **シナリオ名** — 散文` の番号付きリスト形式（自然な MD）
    """
    result = []
    # 形式 1: ### 見出しがある場合
    if re.search(r"^### ", text, re.MULTILINE):
        parts = re.split(r"^### ", text, flags=re.MULTILINE)
        for part in parts[1:]:
            lines = part.strip().split("\n", 1)
            name = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            body = re.split(r"^---\s*$", body, maxsplit=1, flags=re.MULTILINE)[0].strip()
            result.append({"name": name, "text": body})
        return result

    # 形式 2: 番号付きリスト `1. **名称** — 散文` (em-dash / en-dash / hyphen 対応)
    list_re = re.compile(
        r"^\s*\d+\.\s*\*\*(.+?)\*\*\s*[—–\-]\s*(.+?)(?=^\s*\d+\.|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for m in list_re.finditer(text):
        name = m.group(1).strip()
        body = m.group(2).strip()
        result.append({"name": name, "text": body})
    return result


def parse_flows(text: str) -> list[Flow]:
    flows = []
    # ### サブタイトル のすぐ後の event-flow-svg を 1 つの Flow に紐付ける
    fence_re = re.compile(r"```event-flow-svg\n(.*?)\n```", re.DOTALL)
    for match in fence_re.finditer(text):
        dsl = match.group(1)
        flow = parse_flow_dsl(dsl)
        if flow:
            flows.append(flow)
    return flows


def parse_flow_dsl(dsl: str) -> Flow | None:
    flow = Flow(title="")
    lines = dsl.split("\n")

    current_lane: Lane | None = None
    in_flow_section = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.strip().startswith("#"):
            continue

        m = re.match(r"^title:\s*(.+)$", line.strip())
        if m:
            flow.title = m.group(1).strip()
            continue

        if line.strip() == "flow:":
            in_flow_section = True
            continue

        lane_match = re.match(r"^\|([^|]+)\|:\s*(.*)$", line.strip())
        if lane_match:
            current_lane = Lane(
                bc_name=lane_match.group(1).strip(),
                description=lane_match.group(2).strip(),
            )
            flow.lanes.append(current_lane)
            continue

        if current_lane is None:
            continue

        notes, joins_into_next = parse_flow_line(line)
        current_lane.notes.extend(notes)
        if joins_into_next:
            # 行末 &>> は最後に書かれた行のみが next-lane 遷移に効く
            current_lane.joins_into_next = True

    return flow if flow.lanes else None


def parse_flow_line(line: str) -> tuple[list[Note], bool]:
    """1 行をパース → (Note リスト, 行末が &>> で次レーンへ Join 遷移するか)

    オペレータの優先順位:
    1. 行末 `&>>` (Join + 非同期遷移) > `>>` (通常の非同期遷移)
    2. `*>` で分割し、2 つ目以降のセグメント内 Note は is_fanout=True にマーク
    3. 各セグメント内は `>` で分割（既存の同期フロー）
    """
    line = line.strip()
    if not line:
        return [], False

    joins_into_next = line.endswith("&>>")
    if joins_into_next:
        line = line[:-3].rstrip()
        has_async_end = True
    else:
        has_async_end = line.endswith(">>")
        if has_async_end:
            line = line[:-2].rstrip()

    notes: list[Note] = []
    for seg_idx, seg in enumerate(re.split(r"\*>", line)):
        in_fanout = seg_idx > 0
        parts = [p.strip() for p in seg.split(">") if p.strip()]
        for part in parts:
            note = parse_dsl_item(part)
            if note:
                note.is_fanout = in_fanout
                notes.append(note)
    if notes and has_async_end:
        notes[-1].is_async = True
    return notes, joins_into_next


def parse_dsl_item(item: str) -> Note | None:
    item = item.strip()
    if not item:
        return None
    if item.startswith("[") and item.endswith("]"):
        return Note(kind="event", label=item[1:-1].strip())
    if item[0] in DSL_PREFIX_TO_KIND:
        return Note(kind=DSL_PREFIX_TO_KIND[item[0]], label=item[1:].strip())
    return Note(kind="command", label=item)


def parse_bc_cards(text: str) -> list[dict]:
    cards = []
    parts = re.split(r"^### ", text, flags=re.MULTILINE)
    for part in parts[1:]:
        lines = part.strip().split("\n")
        name_line = lines[0].strip()
        slug_match = re.match(r"^([\w-]+)", name_line)
        slug = slug_match.group(1) if slug_match else name_line
        body = "\n".join(lines[1:]).strip()

        reason = ""
        upstream = ""
        downstream = ""
        languages = []
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("- 境界の理由:"):
                reason = line.split(":", 1)[1].strip()
            elif "UPSTREAM:" in line:
                upstream = line.split("UPSTREAM:", 1)[1].strip()
            elif "DOWNSTREAM:" in line:
                downstream = line.split("DOWNSTREAM:", 1)[1].strip()
            elif line.startswith("- LANGUAGE:"):
                languages.append(line.split(":", 1)[1].strip())

        cards.append(
            {
                "slug": slug,
                "name": name_line,
                "reason": reason,
                "upstream": upstream,
                "downstream": downstream,
                "languages": languages,
                "purpose": extract_prose_subsection(body, "目的"),
                "background": extract_prose_subsection(body, "背景"),
                "constraints": extract_subsection(body, "制約"),
            }
        )
    return cards


def parse_agg_cards(text: str) -> list[dict]:
    cards = []
    parts = re.split(r"^### ", text, flags=re.MULTILINE)
    for part in parts[1:]:
        lines = part.strip().split("\n")
        name = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        zod_match = re.search(r"```ts\n(.*?)\n```", body, re.DOTALL)
        zod_code = zod_match.group(1).strip() if zod_match else ""

        ctx_match = re.search(r"^- コンテキスト:\s*`([^`]+)`", body, re.MULTILINE)
        ctx = ctx_match.group(1) if ctx_match else ""
        rel_match = re.search(r"^- 関連シナリオ:\s*(.+)$", body, re.MULTILINE)
        rel = rel_match.group(1).strip() if rel_match else ""

        cards.append(
            {
                "name": name,
                "context": ctx,
                "related": rel,
                "zod": zod_code,
                "purpose": extract_prose_subsection(body, "目的"),
                "background": extract_prose_subsection(body, "背景"),
                "constraints": extract_subsection(body, "制約"),
                "invariants": extract_subsection(body, "不変条件"),
                "errors": extract_subsection(body, "エラーケース"),
                "transitions": extract_subsection(body, "状態遷移"),
                "derived": extract_subsection(body, "派生イベント"),
                "notes": extract_subsection(body, "備考"),
            }
        )
    return cards


def extract_subsection(text: str, heading: str) -> list[str]:
    pattern = (
        rf"^####\s+{re.escape(heading)}\s*\n(.+?)"
        r"(?=^####|^---|^###\s|\Z)"
    )
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = m.group(1).strip()
    items = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
    return items


def extract_prose_subsection(text: str, heading: str) -> str:
    """`#### 見出し` の本文を散文として返す。bullet 行は除外して連結。

    `extract_subsection` の散文版。テンプレ準拠の `#### 目的` / `#### 背景`
    のように散文 1〜3 文を持つサブセクションのために用意。

    bullet (`- ...`) 行は除外する（bullet 主体のサブセクションは
    `extract_subsection` を使う）。複数行の散文は半角スペースで連結する。
    見出しが無い場合は空文字を返す（パース成功扱い・後方互換）。
    """
    pattern = (
        rf"^####\s+{re.escape(heading)}\s*\n(.+?)"
        r"(?=^####|^---|^###\s|\Z)"
    )
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    lines: list[str] = []
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith("- "):
            continue
        lines.append(s)
    return " ".join(lines)


def parse_qry_cards(text: str) -> list[dict]:
    cards = []
    parts = re.split(r"^### ", text, flags=re.MULTILINE)
    for part in parts[1:]:
        lines = part.strip().split("\n")
        name = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        fields = {}
        for line in body.split("\n"):
            m = re.match(r"^- \*\*(.+?)\*\*:\s*(.+)$", line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip()
        cards.append(
            {
                "name": name,
                "user": fields.get("利用者", ""),
                "purpose": fields.get("目的", ""),
                "source": fields.get("ソース", ""),
                "calc": fields.get("算出", ""),
            }
        )
    return cards


def parse_questions_hotspots(text: str) -> tuple[list[dict], list[dict]]:
    """オープンクエスチョン/ホットスポット解析。

    対応フォーマット:
    1. `[CLOSED] Q1. 内容`  (テンプレート準拠の解消形)
    2. `Q1. 内容` (未解消)
    3. `~~Q1. 見出し~~ → 結論`  (取り消し線で解消を表現する自然な MD)
    """
    questions: list[dict] = []
    hotspots: list[dict] = []
    seen: set[tuple[str, str]] = set()  # (kind, num) で重複防止

    # 形式 3: 取り消し線形式
    strikethrough_re = re.compile(
        r"^-?\s*~~([QH])(\d+)\.\s*(.+?)~~\s*(?:→\s*(.+))?$",
        re.MULTILINE,
    )
    for m in strikethrough_re.finditer(text):
        kind = m.group(1)
        num = m.group(2)
        body = m.group(3).strip()
        conclusion = m.group(4).strip() if m.group(4) else ""
        full = f"{body} → {conclusion}" if conclusion else body
        key = (kind, num)
        if key in seen:
            continue
        seen.add(key)
        entry = {"num": num, "text": full, "closed": True}
        (questions if kind == "Q" else hotspots).append(entry)

    # 形式 1/2: [CLOSED] 接頭辞または通常形式
    line_re = re.compile(
        r"^-?\s*(\[CLOSED\]\s+)?([QH])(\d+)\.\s*(.+?)$", re.MULTILINE
    )
    for m in line_re.finditer(text):
        kind = m.group(2)
        num = m.group(3)
        key = (kind, num)
        if key in seen:
            continue
        seen.add(key)
        closed = bool(m.group(1))
        body = m.group(4).strip()
        entry = {"num": num, "text": body, "closed": closed}
        (questions if kind == "Q" else hotspots).append(entry)
    return questions, hotspots


def parse_actions(text: str) -> list[str]:
    return [
        line.strip()[2:].strip()
        for line in text.split("\n")
        if line.strip().startswith("- ")
    ]


def parse_dml(text: str) -> str:
    m = re.search(r"```dml\n(.*?)\n```", text, re.DOTALL)
    return m.group(1) if m else ""


def parse_glossary(text: str) -> dict:
    """用語集解析。

    対応フォーマット:
    1. `### カテゴリ名` でカテゴリ別テーブル（テンプレート準拠）
    2. カテゴリ無し単一テーブル（種別列で自動分類: Actor/Command/Event/Policy/Query）
    """
    # 種別列の値 → 表示カテゴリ名（自動分類用）
    kind_to_category = {
        "Actor": "アクター",
        "Command": "コマンド",
        "Event": "イベント",
        "Policy": "ポリシー",
        "Query": "リードモデル",
        "Read Model": "リードモデル",
    }

    def parse_row(line: str) -> tuple[str, str, str] | None:
        line = line.strip()
        if not line.startswith("|"):
            return None
        # ヘッダー行・区切り行を除外
        if line.startswith("|---") or line.startswith("|--") or line.startswith("|:"):
            return None
        # 日本語ヘッダ・英語ヘッダ・カテゴリ名どれも除外
        lower = line.lower()
        if "日本語" in line or "英語" in line or "種別" in line or "備考" in line:
            return None
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or not cells[0] or cells[0] == "—":
            return None
        return (
            cells[0],
            cells[1],
            cells[2] if len(cells) > 2 else "",
        )

    result: dict[str, list[dict]] = {}
    cat_re = re.compile(r"^### (.+?)$", re.MULTILINE)
    matches = list(cat_re.finditer(text))

    if matches:
        # 形式 1: カテゴリ別テーブル
        for i, m in enumerate(matches):
            cat = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            rows = []
            for line in body.split("\n"):
                row = parse_row(line)
                if row:
                    rows.append({"jp": row[0], "en": row[1], "note": row[2]})
            result[cat] = rows
        return result

    # 形式 2: カテゴリ無し単一テーブル — 種別列で自動分類
    for line in text.split("\n"):
        row = parse_row(line)
        if not row:
            continue
        jp, en, note = row
        category = kind_to_category.get(note, "その他")
        # 単一テーブルでは note 列が種別なので、備考は空にする
        if category not in result:
            result[category] = []
        result[category].append({"jp": jp, "en": en, "note": ""})

    # 表示順を整える(アクター/コマンド/イベント/ポリシー/リードモデル/その他)
    if result:
        ordered = {}
        for cat in ["アクター", "コマンド", "イベント", "ポリシー", "リードモデル", "その他"]:
            if cat in result:
                ordered[cat] = result[cat]
        return ordered
    return result


# ============================================================
# HTML レンダラ
# ============================================================


def esc(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_progress(status: str) -> str:
    phases = [
        "1. スコープ",
        "2. ストーリー",
        "3. イベント発見",
        "4. CMD-EVT-POLICY",
        "4.5. BC 境界",
        "5. RULE-ERR",
        "6. 整合性チェック",
    ]
    done_count = 0
    if re.search(r"フェーズ6.*完了", status):
        done_count = 7
    elif re.search(r"フェーズ5", status):
        done_count = 6
    elif re.search(r"フェーズ4\.5", status):
        done_count = 5
    elif re.search(r"フェーズ4", status):
        done_count = 4
    elif re.search(r"フェーズ3", status):
        done_count = 3
    elif re.search(r"フェーズ2", status):
        done_count = 2
    elif re.search(r"フェーズ1", status):
        done_count = 1

    items = []
    for i, name in enumerate(phases):
        if i < done_count:
            cls = "phase done"
            label = name + (" ✅" if i == 6 else "")
        elif i == done_count:
            cls = "phase current"
            label = name
        else:
            cls = "phase"
            label = name
        items.append(f'<div class="{cls}">{esc(label)}</div>')
    return "\n    ".join(items)


def render_story(story: str) -> str:
    if not story.strip():
        return '<div class="todo-placeholder">TODO: フェーズ2完了後に追記</div>'
    paragraphs = [p.strip() for p in story.split("\n\n") if p.strip()]
    inner = "\n    ".join(f"<p>{esc(p)}</p>" for p in paragraphs)
    return f'<div class="story">\n    {inner}\n  </div>'


def render_scenarios(scenarios: list[dict]) -> str:
    if not scenarios:
        return '<div class="todo-placeholder">代替シナリオなし</div>'
    cards = []
    for s in scenarios:
        text_html = "\n".join(
            f"<p>{esc(line.strip())}</p>"
            for line in s["text"].split("\n")
            if line.strip()
        )
        cards.append(
            f'<div class="scenario-card">\n'
            f'    <h3>{esc(s["name"])}</h3>\n'
            f"    {text_html}\n"
            f"  </div>"
        )
    return "\n  ".join(cards)


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


def render_bc_cards(cards: list[dict]) -> str:
    if not cards:
        return '<div class="todo-placeholder">TODO: フェーズ4完了後に追記</div>'
    out = []
    for c in cards:
        lang_html = ""
        if c["languages"]:
            lang_items = "<br>".join(esc(lang) for lang in c["languages"])
            lang_html = f'<div class="dep" style="margin-top: 6px;"><strong>LANGUAGE:</strong> {lang_items}</div>'
        intent_html = render_intent_blocks(c)
        out.append(
            f'<div class="bc-card">\n'
            f'    <h3>{esc(c["name"])}</h3>\n'
            f"    <p>{esc(c['reason'])}</p>\n"
            f'    <div class="dep"><strong>UPSTREAM:</strong> {esc(c["upstream"])} · '
            f'<strong>DOWNSTREAM:</strong> {esc(c["downstream"])}</div>\n'
            f"    {lang_html}\n"
            f"    {intent_html}\n"
            f"  </div>"
        )
    return "\n  ".join(out)


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
        boxes.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="6" '
            f'fill="#90CAF9" stroke="#1565C0" stroke-width="2"/>'
            f'<text x="{cx}" y="{y + box_h // 2 + 5}" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="#0D47A1">{esc(c["slug"])}</text>'
        )

    arrows = []
    for c in cards:
        ds = c["downstream"]
        # `kitchen (...)` の形式から slug を抽出
        m = re.match(r"^([\w-]+)", ds)
        if not m:
            continue
        target_slug = m.group(1)
        if target_slug == "(none)" or target_slug not in bc_y:
            continue
        y1 = bc_y[c["slug"]]
        y2 = bc_y[target_slug]
        if y1 == y2:
            continue
        # 縦の矢印
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


_ERR_CODE_RE = re.compile(r"`([^`]+)`")


def _render_err_item(text: str) -> str:
    return _ERR_CODE_RE.sub(r'<code class="err-code">\1</code>', esc(text))


# 集約サブセクションの表示スタイル: (CSS クラス, ラベル接頭辞, 1 項目あたりのレンダラ)
AGG_SUBSECTION_STYLE: dict[str, tuple[str, str, "object"]] = {
    "不変条件":   ("inv-section", "✓ ", esc),
    "エラーケース": ("err-section", "⚠ ", _render_err_item),
}
AGG_SUBSECTION_DEFAULT = ("agg-subsection", "", esc)


def render_agg_cards(cards: list[dict]) -> str:
    if not cards:
        return '<div class="todo-placeholder">TODO: フェーズ5完了後に追記</div>'
    out = []
    for c in cards:
        meta = f'<div class="dep"><strong>コンテキスト:</strong> {esc(c["context"])} · <strong>関連シナリオ:</strong> {esc(c["related"])}</div>'
        intent_html = render_intent_blocks(c)
        zod_html = ""
        if c["zod"]:
            zod_html = f'<pre class="code">{highlight_zod(c["zod"])}</pre>'

        bullets = []
        for label, items in [
            ("不変条件", c["invariants"]),
            ("エラーケース", c["errors"]),
            ("状態遷移", c["transitions"]),
            ("派生イベント", c["derived"]),
            ("備考", c["notes"]),
        ]:
            if not items:
                continue
            css, prefix, render_item = AGG_SUBSECTION_STYLE.get(label, AGG_SUBSECTION_DEFAULT)
            items_html = "\n      ".join(f"<li>{render_item(x)}</li>" for x in items)
            bullets.append(
                f'<div class="{css}">'
                f"<strong>{prefix}{label}:</strong>"
                f"<ul>\n      {items_html}\n    </ul>"
                f"</div>"
            )

        sections = [meta, intent_html, zod_html] + bullets
        out.append(
            f'<div class="bc-card">\n'
            f'    <h3>{esc(c["name"])}</h3>\n'
            "    " + "\n    ".join(s for s in sections if s)
            + "\n  </div>"
        )
    return "\n  ".join(out)


def render_qry_cards(cards: list[dict]) -> str:
    if not cards:
        return '<div class="todo-placeholder">TODO: フェーズ4〜5完了後に追記</div>'
    out = []
    for c in cards:
        out.append(
            f'<div class="bc-card" style="border-left: 4px solid #2E7D32;">\n'
            f'    <h3 style="color: #2E7D32;">{esc(c["name"])}</h3>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>利用者:</strong> {esc(c["user"])}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>目的:</strong> {esc(c["purpose"])}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>ソース:</strong> {esc(c["source"])}</p>\n'
            f'    <p style="font-size: 14px; color: #455A64; margin: 4px 0;"><strong>算出:</strong> {esc(c["calc"])}</p>\n'
            f"  </div>"
        )
    return "\n  ".join(out)


def render_questions_hotspots(questions: list[dict], hotspots: list[dict]) -> str:
    parts = []
    open_q = [q for q in questions if not q["closed"]]
    closed_q = [q for q in questions if q["closed"]]
    open_h = [h for h in hotspots if not h["closed"]]
    closed_h = [h for h in hotspots if h["closed"]]

    if not open_q and not open_h and (closed_q or closed_h):
        parts.append(
            '<p style="color: #2E7D32; font-weight: 600;">✅ すべて解決済み</p>'
        )

    for q in open_q:
        parts.append(
            f'<div class="question"><strong>Q{q["num"]}.</strong> {esc(q["text"])}</div>'
        )
    for q in closed_q:
        parts.append(
            f'<div class="question" style="background: #E8F5E9; border-left-color: #2E7D32;">'
            f'<strong>[CLOSED] Q{q["num"]}.</strong> {esc(q["text"])}</div>'
        )

    if hotspots:
        parts.append('<h3 style="margin-top:16px;">ホットスポット</h3>')
    for h in open_h:
        parts.append(
            f'<div class="hotspot"><strong>H{h["num"]}.</strong> {esc(h["text"])}</div>'
        )
    for h in closed_h:
        parts.append(
            f'<div class="hotspot" style="background: #E8F5E9; border-left-color: #2E7D32;">'
            f'<strong>[CLOSED] H{h["num"]}.</strong> {esc(h["text"])}</div>'
        )

    if not parts:
        return '<div class="todo-placeholder">未確認事項なし</div>'
    return "\n  ".join(parts)


def render_actions(actions: list[str], status: str) -> str:
    if not actions:
        return '<div class="todo-placeholder">未定</div>'
    items = "\n      ".join(f"<li>{esc(a)}</li>" for a in actions)
    return f'<div class="next-actions">\n    <ul>\n      {items}\n    </ul>\n  </div>'


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


def render_glossary(glossary: dict) -> str:
    if not glossary:
        return '<div class="todo-placeholder">TODO</div>'
    sections = []
    for cat, rows in glossary.items():
        if not rows:
            continue
        body_rows = "\n        ".join(
            f"<tr><td>{esc(r['jp'])}</td>"
            f"<td class=\"code-cell\">{esc(r['en'])}</td>"
            f"<td>{esc(r['note'])}</td></tr>"
            for r in rows
        )
        sections.append(
            f'<div class="glossary-section">\n'
            f"    <h3>{esc(cat)}</h3>\n"
            f'    <table class="glossary">\n'
            f"      <thead><tr><th>日本語</th><th>英語</th><th>備考</th></tr></thead>\n"
            f"      <tbody>\n        {body_rows}\n      </tbody>\n"
            f"    </table>\n"
            f"  </div>"
        )
    return "\n  ".join(sections)


# ============================================================
# シンタックスハイライト
# ============================================================

ZOD_KEYWORDS = {"export", "const", "type", "typeof", "import", "from"}

# DML（YAML）の値を「キー名」に応じて付箋色クラスへ割り当てる
DML_VALUE_CLASS_BY_KEY = {
    "actor": "v-actor",
    "agg": "v-actor",
    "cmd": "v-cmd",
    "evt": "v-evt",
    "trigger": "v-evt",
    "emits": "v-evt",
    "events": "v-evt",      # v2: triggers の join イベント
    "qry": "v-qry",
    "pol": "v-pol",
    "error": "v-err",
    # v2 メタ（CML 由来の任意フィールド）
    "type": "v-meta",
    "vision": "v-meta",
    "subdomain": "v-meta",
    "responsibilities": "v-meta",
    "implementationTechnology": "v-meta",
    "purpose": "v-meta",
    "branchMode": "v-meta",
    "mode": "v-meta",
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
            if mb and mb.group(1) in ("contexts", "scenarios", "policies"):
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


def highlight_zod(zod: str) -> str:
    out = []
    for line in zod.split("\n"):
        result = ""
        i = 0
        while i < len(line):
            matched = False
            for kw in ZOD_KEYWORDS:
                if line[i:].startswith(kw) and (
                    i + len(kw) == len(line) or not line[i + len(kw)].isalnum()
                ):
                    if i == 0 or not line[i - 1].isalnum():
                        result += f'<span class="kw">{kw}</span>'
                        i += len(kw)
                        matched = True
                        break
            if matched:
                continue
            # 文字列リテラル
            if line[i] == "'":
                end = line.find("'", i + 1)
                if end > i:
                    result += f'<span class="cm">{esc(line[i:end + 1])}</span>'
                    i = end + 1
                    continue
            result += esc(line[i])
            i += 1
        out.append(result)
    return "\n".join(out)


# ============================================================
# テンプレ処理
# ============================================================


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render_html(sections: MDSections) -> str:
    template = load_template()

    title = sections.header.get("domain") or sections.header.get("title", "EventStorming")
    session = sections.header.get("session", "")
    goal = sections.header.get("goal", "")
    status = sections.header.get("status", "")

    # テンプレ全体をリプレース。テンプレ内のサンプル本文は丸ごと差し替える
    html = template

    # ヘッダー
    html = re.sub(
        r"<h1>EventStorming — \{\{ドメイン名\}\}</h1>",
        f"<h1>EventStorming — {esc(title)}</h1>",
        html,
    )
    html = re.sub(
        r"Session:\s*<code>\{\{eventstorming-YYYYMMDD-HHMM\}\}</code>\s*·\s*\n\s*Goal:\s*\{\{ゴール\}\}",
        f"Session: <code>{esc(session)}</code> · Goal: {esc(goal)}",
        html,
    )

    # ボディ全体を構築して、テンプレの <body>...</body> 間を差し替える
    body_html = build_body_html(sections, title, session, goal, status)
    html = re.sub(
        r"<body>.*?</body>",
        f"<body>\n{body_html}\n</body>",
        html,
        flags=re.DOTALL,
    )

    return html


def build_body_html(
    sections: MDSections, title: str, session: str, goal: str, status: str
) -> str:
    progress_html = render_progress(status)
    story_html = render_story(sections.story)
    scenarios_html = render_scenarios(sections.scenarios)
    flows_html = render_flows(sections.flows)
    context_map_html = render_context_map(sections.bc_cards)
    bc_cards_html = render_bc_cards(sections.bc_cards)
    agg_cards_html = render_agg_cards(sections.agg_cards)
    qry_cards_html = render_qry_cards(sections.qry_cards)
    questions_html = render_questions_hotspots(sections.questions, sections.hotspots)
    actions_html = render_actions(sections.actions, status)
    dml_html = render_dml(sections.dml, sections.dml_errors)
    glossary_html = render_glossary(sections.glossary)

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

  <h2>1. ハッピーパスストーリー</h2>
  {story_html}

  <h2>2. 代替シナリオ</h2>
  {scenarios_html}

  <h2>3. Event Walkthrough</h2>
  {flows_html}

  <h2>4. コンテキスト候補</h2>
  {context_map_html}
  {bc_cards_html}

  <h2>5. 集約候補</h2>
  {agg_cards_html}

  <h2>6. リードモデル候補</h2>
  {qry_cards_html}

  <h2>7. オープンクエスチョン</h2>
  {questions_html}

  <h2>8. 次のアクション</h2>
  {actions_html}

  <h2>9. DML</h2>
  {dml_html}

  <h2>10. 用語集</h2>
  {glossary_html}
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


def build(
    md_path: Path,
    out_dir: Path,
    *,
    artifact: bool = False,
) -> Path:
    md_text = md_path.read_text(encoding="utf-8")
    sections = parse_md(md_text)
    # DML はサイドカー `<session>.dml.yaml`（純 YAML）を優先。
    # 無ければ parse_md が §9 の埋め込み ```dml フェンスから抽出した値にフォールバック。
    dml_path = md_path.with_name(md_path.stem + ".dml.yaml")
    if dml_path.exists():
        sections.dml = dml_path.read_text(encoding="utf-8").strip()
    # JSON Schema 検証（警告のみ・non-blocking）。違反は §9 バナーと stderr に出すが
    # ビルドは止めない（編集途中の不完全 DML でも HTML プレビューを保つ）。
    sections.dml_errors = _validate_dml_warn(sections.dml, dml_path)
    html = render_html(sections)

    if artifact:
        html = strip_for_artifact(html)
        suffix = "-artifact.html"
    else:
        suffix = ".html"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (md_path.stem + suffix)
    out_path.write_text(html, encoding="utf-8")

    # 自動リロードは廃止（meta refresh / AppleScript reload とも撤去済み）。
    # ブラウザ側で手動リロードしてください。
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
    for md_path in sorted(in_dir.glob("*.md")):
        try:
            out = build(md_path, out_dir, artifact=artifact)
            results.append(out)
            print(f"✅ {md_path.name} → {out.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"❌ {md_path.name}: {e}", file=sys.stderr)
    return results


def watch(in_dir: Path, out_dir: Path, interval: float = 1.0) -> None:
    print(f"👀 監視中: {in_dir} (Ctrl-C で停止)")
    # 起動時の既存ファイルは reload を抑止するため事前にスキャンしておく
    mtimes: dict[Path, float] = {p: p.stat().st_mtime for p in in_dir.glob("*.md")}
    try:
        while True:
            for md_path in in_dir.glob("*.md"):
                mtime = md_path.stat().st_mtime
                prev = mtimes.get(md_path)
                if prev is None or mtime > prev:
                    mtimes[md_path] = mtime
                    try:
                        out = build(md_path, out_dir)
                        print(f"♻️  {md_path.name} → {out.relative_to(PROJECT_ROOT)}")
                    except Exception as e:
                        print(f"❌ {md_path.name}: {e}", file=sys.stderr)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 停止しました")


# ============================================================
# CLI
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EventStorming MD → HTML ビルダー",
    )
    parser.add_argument("path", nargs="?", help="MD ファイルパス（省略時は --all か --watch）")
    parser.add_argument("--all", action="store_true", help="全 MD をビルド")
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

    md_path = Path(args.path)
    # hook が `.dml.yaml` を渡した場合は兄弟 `.md` をセッション本体として解決
    # （HTML 命名・他セクションは `.md` 由来、DML は build() がサイドカーから読む）。
    # 二重拡張子 `.dml.yaml` は with_suffix では剥がせないので name から除去する。
    if md_path.name.endswith(".dml.yaml"):
        md_path = md_path.with_name(md_path.name[: -len(".dml.yaml")] + ".md")
    if not md_path.exists():
        print(f"❌ ファイルが見つかりません: {md_path}", file=sys.stderr)
        return 1

    try:
        out = build(md_path, out_dir, artifact=args.artifact)
        print(f"✅ {md_path.name} → {out.relative_to(PROJECT_ROOT)}")
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
