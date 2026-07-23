#!/usr/bin/env python3
"""DimML (.dimml.yaml) → 単一 HTML（バスマトリクス＋スタースキーマ）ビルダー。

セクション:
  1. 分析シナリオ（narratives：答えたい問い・KPI）
  2. バスマトリクス（processes/facts × dimensions。● = 使用、conformed dimension を強調）
  3. スタースキーマ（fact ごとに Mermaid erDiagram。role-playing dimension は複数リレーションで表現）
  4. ファクト詳細（グレイン・grainType・measure の加法性・degenerate dimension）
  5. ディメンション詳細（SCD・階層・属性）
  6. 検証状態サマリ（verified / unverified 件数）
  7. オープンクエスチョン
  8. 意思決定ログ
  9. DimML ソース全文

使い方:
  python3 dimml_build.py <file.dimml.yaml>            # 単体ビルド
  python3 dimml_build.py --all                        # docs/dimensional/*.dimml.yaml を全ビルド
  python3 dimml_build.py <file> --out dist/dimensional

HTML は派生物。手で編集しない（DimML 側を直す → 再ビルド）。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_ROOT / "templates" / "star-schema.html"

# リポジトリルートからの既定入出力（EventStorming と対称）
REPO_ROOT = SKILL_ROOT.parent.parent.parent  # .claude/skills/<skill>/scripts -> repo root
DEFAULT_INPUT_DIR = REPO_ROOT / "docs" / "dimensional"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "dimensional"

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from validate_dimml import validate_dimml_text  # type: ignore
except Exception:  # pragma: no cover
    def validate_dimml_text(_text: str) -> list[str]:  # type: ignore
        return []


# ---------- helpers ----------

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def ident(s) -> str:
    """Mermaid エンティティ/リレーション識別子用に英数字と _ 以外を除去する。

    DimML の識別子はスキーマで PascalCase/columnName/slug に制約されるため実害は無いが、
    <pre class="mermaid"> からの要素脱出（</pre> 注入）を根絶するための保険。
    """
    return re.sub(r"[^A-Za-z0-9_]", "", str(s or "")) or "X"


def badge(text: str, cls: str) -> str:
    return f'<span class="badge b-{esc(cls)}">{esc(text)}</span>'


def status_badge(status) -> str:
    """status は省略時 unverified 扱い（grill 規律）。"""
    s = status if status in ("verified", "unverified") else "unverified"
    label = "検証済" if s == "verified" else "未検証"
    return f'<span class="badge b-{s}">{label}</span>'


# ---------- 解説ブロック（図解の意図・読み方・データ連動の気づき） ----------

def render_explain(lead: str, howto: str = "", read: str = "",
                   legend: str = "", hint: str = "") -> str:
    """各セクションの h2 直下に差し込む解説カードを生成する。

    lead   = このセクションが何を示すか（意図・1 文。プレーンテキスト → エスケープ）
    howto  = どう読むか（凡例の言葉・任意）※安全な HTML を渡す（<b>/<code> 可）
    read   = 読み下し例（任意）※安全な HTML を渡す
    legend = 記号/バッジ凡例（.legend の中身・任意）
    hint   = モデルに即した気づき（データ連動・空なら省略）※安全な HTML を渡す
    """
    parts = [f'<span class="lead">{esc(lead)}</span>']
    if howto:
        parts.append(f'<span class="howto">{howto}</span>')
    if read:
        parts.append(f'<span class="read">{read}</span>')
    if legend:
        parts.append(f'<div class="legend">{legend}</div>')
    if hint:
        parts.append(f'<span class="hint">{hint}</span>')
    return '<div class="explain">' + "".join(parts) + "</div>"


def badge_legend() -> str:
    """冒頭オリエンテーション用の全バッジ凡例。"""
    g = lambda t, c, gloss: f'<span>{badge(t, c)} {esc(gloss)}</span>'
    return "".join([
        '<span class="k">grainType:</span>',
        g("transaction", "transaction", "出来事1件=1行"),
        g("periodic-snapshot", "periodic-snapshot", "定期の残高"),
        g("accumulating-snapshot", "accumulating-snapshot", "工程を更新"),
        '<span class="k">加法性:</span>',
        g("additive", "additive", "全軸で合計可"),
        g("semi-additive", "semi-additive", "一部で合計不可"),
        g("non-additive", "non-additive", "合計不可"),
        '<span class="k">SCD:</span>',
        g("none", "none", "不変"),
        g("TYPE_1", "TYPE_1", "上書き"),
        g("TYPE_2", "TYPE_2", "履歴保持"),
        '<span class="k">検証:</span>',
        g("検証済", "verified", "裏取り済み"),
        g("未検証", "unverified", "推測・要確認"),
    ])


# ---------- データ連動の気づきを計算するヘルパー ----------

def _facts(model: dict) -> list[dict]:
    return [f for f in (model.get("facts") or []) if isinstance(f, dict)]


def _dims(model: dict) -> list[dict]:
    return [d for d in (model.get("dimensions") or []) if isinstance(d, dict)]


def _conformed_names(model: dict) -> list[str]:
    """2 ファクト以上で使われる or conformed: true の dimension 名。"""
    usage: dict[str, int] = {}
    for f in _facts(model):
        for d in _fact_dims(f):
            dn = d.get("dimension")
            if dn:
                usage[dn] = usage.get(dn, 0) + 1
    conf = {d.get("name") for d in _dims(model) if d.get("conformed")}
    names = {dn for dn, c in usage.items() if c >= 2} | conf
    # dimensions[] の並び順を保つ
    return [d.get("name") for d in _dims(model) if d.get("name") in names]


def _roleplaying(model: dict) -> list[str]:
    """role-playing しているファクトと役割の説明文リスト。"""
    out = []
    for f in _facts(model):
        roles: dict[str, list[str]] = {}
        for d in _fact_dims(f):
            if d.get("role"):
                roles.setdefault(d.get("dimension"), []).append(d.get("role"))
        for dim, rs in roles.items():
            if len(rs) >= 2:
                out.append(f"{f.get('name')} は {dim} を {'/'.join(rs)} の{len(rs)}役で参照")
            elif rs:
                out.append(f"{f.get('name')} は {dim} を {rs[0]} として参照")
    return out


def _grain_type_dist(model: dict) -> dict[str, int]:
    dist: dict[str, int] = {}
    for f in _facts(model):
        gt = f.get("grainType")
        if gt:
            dist[gt] = dist.get(gt, 0) + 1
    return dist


def _semi_additive_facts(model: dict) -> list[str]:
    out = []
    for f in _facts(model):
        for m in f.get("msrs") or []:
            if isinstance(m, dict) and m.get("additivity") == "semi-additive":
                out.append(f.get("name"))
                break
    return out


def _type2_dims(model: dict) -> list[str]:
    return [d.get("name") for d in _dims(model) if d.get("scd") == "TYPE_2"]


def _unverified_total(model: dict) -> int:
    n = 0
    for key in ("processes", "facts", "dimensions", "narratives"):
        for x in (model.get(key) or []):
            if isinstance(x, dict) and x.get("status") != "verified":
                n += 1
    return n


# ---------- section renderers ----------

def render_header(session: dict) -> str:
    title = session.get("domain") or session.get("id") or "Dimensional Model"
    parts = [f"<h1>DimML — {esc(title)}</h1>"]
    meta_bits = []
    if session.get("id"):
        meta_bits.append(f"Session: <code>{esc(session['id'])}</code>")
    if session.get("phase"):
        meta_bits.append(f"Phase: <strong>{esc(session['phase'])}</strong>")
    if session.get("goal"):
        meta_bits.append(f"Goal: {esc(session['goal'])}")
    if meta_bits:
        parts.append(f'<div class="meta">{" · ".join(meta_bits)}</div>')
    if session.get("status"):
        parts.append(f'<div class="meta">{esc(session["status"])}</div>')
    return "\n".join(parts)


def render_banner(errors: list[str]) -> str:
    if not errors:
        return '<div class="banner ok">✅ schema OK · 構文/参照エラーなし</div>'
    items = "".join(f"<li>{esc(e)}</li>" for e in errors)
    return (
        '<div class="banner err">⚠ 検証エラー（DimML を修正して再ビルド）:'
        f"<ul>{items}</ul></div>"
    )


def render_narratives(narratives: list[dict]) -> str:
    if not narratives:
        return '<p class="muted">（分析シナリオ未記述）</p>'
    out = []
    for n in narratives:
        if not isinstance(n, dict):
            continue
        title = n.get("title") or n.get("id") or ""
        kind = n.get("kind")
        kb = badge(kind, kind) if kind in ("question", "kpi", "story") else ""
        out.append(
            f'<div class="card"><h3>{esc(title)} {kb} {status_badge(n.get("status"))}</h3>'
            f'<div class="prose">{esc(n.get("prose", ""))}</div></div>'
        )
    return "\n".join(out)


def _fact_dims(fact: dict) -> list[dict]:
    return [d for d in (fact.get("dims") or []) if isinstance(d, dict)]


def render_bus_matrix(model: dict) -> str:
    facts = [f for f in (model.get("facts") or []) if isinstance(f, dict)]
    dims = [d for d in (model.get("dimensions") or []) if isinstance(d, dict)]
    if not facts or not dims:
        return '<p class="muted">（ファクトまたはディメンション未記述。バスマトリクスは両方が揃うと描画）</p>'

    dim_names = [d.get("name") for d in dims]
    # 使用回数（≥2 プロセス/ファクトで使われる or conformed:true → conformed 扱い）
    usage: dict[str, int] = {dn: 0 for dn in dim_names}
    for f in facts:
        for d in _fact_dims(f):
            dn = d.get("dimension")
            if dn in usage:
                usage[dn] += 1
    conformed_flag = {d.get("name"): bool(d.get("conformed")) for d in dims}

    def header_cell(dn: str) -> str:
        is_conf = usage.get(dn, 0) >= 2 or conformed_flag.get(dn)
        cls = ' class="conformed"' if is_conf else ""
        mark = " ◆" if is_conf else ""
        return f"<th{cls}>{esc(dn)}{mark}</th>"

    head = "".join(header_cell(dn) for dn in dim_names)
    rows = []
    for f in facts:
        used = {}
        for d in _fact_dims(f):
            dn = d.get("dimension")
            used.setdefault(dn, []).append(d.get("role"))
        cells = []
        for dn in dim_names:
            if dn in used:
                roles = [r for r in used[dn] if r]
                if roles:
                    cell = '●<br><span class="role">' + esc(", ".join(roles)) + "</span>"
                else:
                    cell = "●"
                cells.append(f'<td class="cell used">{cell}</td>')
            else:
                cells.append('<td class="cell muted">·</td>')
        proc = f.get("process") or ""
        gt = f.get("grainType")
        gtb = badge(gt, gt) if gt else ""
        rows.append(
            f"<tr><td><strong>{esc(f.get('name',''))}</strong> {gtb}"
            f'<br><span class="muted">{esc(proc)}</span></td>' + "".join(cells) + "</tr>"
        )
    return (
        '<table class="matrix"><thead><tr><th>ファクト / プロセス</th>'
        f"{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        '<p class="muted">◆ = conformed dimension（複数ファクトで共有 or conformed: true）。'
        "セル内の紫字は role-playing の役割名。</p>"
    )


def _key_attr(dim: dict, kind: str) -> str | None:
    for a in dim.get("attrs") or []:
        if isinstance(a, dict) and a.get("key") == kind:
            return a.get("name")
    return None


def render_star(fact: dict, dims_by_name: dict[str, dict]) -> str:
    fname = ident(fact.get("name"))
    lines = ["erDiagram"]
    # ファクトエンティティ（FK + 測定値）
    fact_attrs = []
    for d in _fact_dims(fact):
        dn = dims_by_name.get(d.get("dimension"))
        role = d.get("role")
        key = (_key_attr(dn, "surrogate") if dn else None) or (
            (d.get("dimension") or "dim").lower() + "Key"
        )
        col = ident(role) + "_key" if role else ident(key)
        fact_attrs.append(f"    int {col} FK")
    for m in fact.get("msrs") or []:
        if isinstance(m, dict) and m.get("name"):
            fact_attrs.append(f"    measure {ident(m['name'])}")
    for dg in fact.get("degen") or []:
        if isinstance(dg, dict) and dg.get("name"):
            fact_attrs.append(f"    degenerate {ident(dg['name'])}")
    lines.append(f"  {fname} {{")
    lines.extend(fact_attrs or ["    measure count"])
    lines.append("  }")
    # ディメンションエンティティ（PK + 主要属性）＋リレーション
    seen_entities: set[str] = set()
    for d in _fact_dims(fact):
        dname_raw = d.get("dimension")
        dim = dims_by_name.get(dname_raw)
        ent = ident(dname_raw)
        if ent not in seen_entities:
            seen_entities.add(ent)
            pk = (_key_attr(dim, "surrogate") if dim else None) or (str(dname_raw).lower() + "Key")
            nat = _key_attr(dim, "natural") if dim else None
            attrs = [f"    int {ident(pk)} PK"]
            if nat:
                attrs.append(f"    string {ident(nat)}")
            scd = dim.get("scd") if dim else None
            if scd and scd != "none":
                attrs.append(f"    scd {ident(scd)}")
            lines.append(f"  {ent} {{")
            lines.extend(attrs)
            lines.append("  }")
        rel_label = ident(d.get("role")) if d.get("role") else "has"
        lines.append(f"  {ent} ||--o{{ {fname} : {rel_label}")
    body = "\n".join(lines)
    grain = fact.get("grain") or "（グレイン未宣言）"
    gt = fact.get("grainType")
    gtb = badge(gt, gt) if gt else ""
    return (
        f'<h3>{esc(fact.get("name",""))} {gtb} {status_badge(fact.get("status"))}</h3>'
        f'<div class="grain">グレイン: {esc(grain)}</div>'
        f'<pre class="mermaid">\n{body}\n</pre>'
    )


def render_stars(model: dict) -> str:
    facts = [f for f in (model.get("facts") or []) if isinstance(f, dict)]
    dims_by_name = {
        d.get("name"): d for d in (model.get("dimensions") or []) if isinstance(d, dict)
    }
    if not facts:
        return '<p class="muted">（ファクト未記述）</p>'
    return "\n".join(render_star(f, dims_by_name) for f in facts)


def render_fact_details(model: dict) -> str:
    facts = [f for f in (model.get("facts") or []) if isinstance(f, dict)]
    if not facts:
        return '<p class="muted">（ファクト未記述）</p>'
    out = []
    for f in facts:
        gt = f.get("grainType")
        gtb = badge(gt, gt) if gt else ""
        rows = []
        for m in f.get("msrs") or []:
            if not isinstance(m, dict):
                continue
            add = m.get("additivity")
            ab = badge(add, add) if add else '<span class="muted">—</span>'
            extra = m.get("formula") or m.get("note") or ""
            if m.get("semiAdditiveAcross"):
                extra = f"合算不可: {m['semiAdditiveAcross']}. " + extra
            rows.append(
                f"<tr><td><code>{esc(m.get('name',''))}</code></td>"
                f"<td>{esc(m.get('label',''))}</td><td>{ab}</td>"
                f"<td>{esc(m.get('unit',''))}</td><td>{esc(extra)}</td></tr>"
            )
        msr_table = (
            "<table><thead><tr><th>measure</th><th>名称</th><th>加法性</th>"
            f"<th>単位</th><th>備考</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
            if rows else '<p class="muted">（測定値未記述）</p>'
        )
        degen = ", ".join(
            f"<code>{esc(d.get('name',''))}</code>"
            for d in (f.get("degen") or []) if isinstance(d, dict)
        )
        degen_html = f"<p>degenerate dimension: {degen}</p>" if degen else ""
        out.append(
            f'<div class="card"><h3>{esc(f.get("name",""))} {gtb} '
            f'{status_badge(f.get("status"))}</h3>'
            f'<div class="grain">グレイン: {esc(f.get("grain") or "（未宣言）")}</div>'
            f'<p class="muted">process: {esc(f.get("process",""))}</p>'
            f"{msr_table}{degen_html}</div>"
        )
    return "\n".join(out)


def render_dimension_details(model: dict) -> str:
    dims = [d for d in (model.get("dimensions") or []) if isinstance(d, dict)]
    if not dims:
        return '<p class="muted">（ディメンション未記述）</p>'
    out = []
    for d in dims:
        scd = d.get("scd") or "none"
        scdb = badge(f"SCD {scd}", scd)
        conf = ' <span class="conformed">◆ conformed</span>' if d.get("conformed") else ""
        rows = []
        for a in d.get("attrs") or []:
            if not isinstance(a, dict):
                continue
            k = a.get("key")
            kb = f" <strong>[{esc(k)}]</strong>" if k else ""
            rows.append(
                f"<tr><td><code>{esc(a.get('name',''))}</code>{kb}</td>"
                f"<td>{esc(a.get('type',''))}</td><td>{esc(a.get('note',''))}</td></tr>"
            )
        attr_table = (
            "<table><thead><tr><th>属性</th><th>型</th><th>備考</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            if rows else ""
        )
        hier = ""
        for h in d.get("hierarchies") or []:
            if isinstance(h, dict) and h.get("levels"):
                lv = " → ".join(esc(x) for x in h["levels"])
                hier += f"<p>階層 <em>{esc(h.get('name',''))}</em>: {lv}</p>"
        out.append(
            f'<div class="card"><h3>{esc(d.get("name",""))} {scdb}{conf} '
            f'{status_badge(d.get("status"))}</h3>'
            f'<div class="grain">グレイン: {esc(d.get("grain") or "（未宣言）")}</div>'
            f"{hier}{attr_table}</div>"
        )
    return "\n".join(out)


def render_summary(model: dict) -> str:
    cats = {
        "processes": "業務プロセス",
        "facts": "ファクト",
        "dimensions": "ディメンション",
        "narratives": "分析シナリオ",
    }
    stats = []
    total_v = total_u = 0
    for key, label in cats.items():
        items = [x for x in (model.get(key) or []) if isinstance(x, dict)]
        v = sum(1 for x in items if x.get("status") == "verified")
        u = len(items) - v
        total_v += v
        total_u += u
        stats.append(
            f'<div class="stat"><div class="muted">{esc(label)}</div>'
            f'<div class="num">{len(items)}</div>'
            f'<div class="muted">検証済 {v} / 未検証 {u}</div></div>'
        )
    total = total_v + total_u
    pct = round(100 * total_v / total) if total else 0
    stats.insert(
        0,
        f'<div class="stat"><div class="muted">検証進捗</div>'
        f'<div class="num">{pct}%</div>'
        f'<div class="muted">{total_v} / {total} 検証済</div></div>',
    )
    return f'<div class="summary">{"".join(stats)}</div>'


def render_questions(model: dict) -> str:
    qs = [q for q in (model.get("questions") or []) if isinstance(q, dict)]
    open_qs = [q for q in qs if q.get("status") != "closed"]
    if not open_qs:
        return '<p class="muted">（オープンクエスチョンなし）</p>'
    items = []
    for q in open_qs:
        why = f' <span class="muted">— {esc(q["why"])}</span>' if q.get("why") else ""
        items.append(f'<li><strong>{esc(q.get("id",""))}</strong>: {esc(q.get("topic",""))}{why}</li>')
    return f"<ul>{''.join(items)}</ul>"


def render_decisions(model: dict) -> str:
    ds = [d for d in (model.get("decisions") or []) if isinstance(d, dict)]
    if not ds:
        return '<p class="muted">（意思決定ログなし）</p>'
    out = []
    for d in ds:
        opts = []
        for o in d.get("options") or []:
            if not isinstance(o, dict):
                continue
            mark = "✅" if o.get("adopted") else "▫️"
            name = o.get("label") or o.get("name")
            reason = o.get("why") if o.get("adopted") else o.get("why_not")
            opts.append(
                f'<li>{mark} <strong>{esc(name)}</strong>'
                + (f' — {esc(reason)}' if reason else "")
                + "</li>"
            )
        out.append(
            f'<div class="card"><h3>{esc(d.get("id",""))}: {esc(d.get("topic",""))}</h3>'
            f'<p class="muted">採用: <code>{esc(d.get("chosen",""))}</code></p>'
            f"<ul>{''.join(opts)}</ul></div>"
        )
    return "\n".join(out)


def render_source(dml_text: str) -> str:
    return f'<pre class="src">{esc(dml_text)}</pre>'


# ---------- assembly ----------

def build_body(model: dict, dml_text: str, errors: list[str]) -> str:
    session = model.get("session") or {}

    # --- データ連動の気づきを事前計算 ---
    unv = _unverified_total(model)
    unv_narr = sum(
        1 for n in (model.get("narratives") or [])
        if isinstance(n, dict) and n.get("status") != "verified"
    )
    conformed = _conformed_names(model)
    roleplay = _roleplaying(model)
    gtd = _grain_type_dist(model)
    semi = _semi_additive_facts(model)
    type2 = _type2_dims(model)

    orient_hint = f"未検証は {unv} 件（推測のまま＝要裏取り）。上のサマリで検証進捗を確認できます。"
    narr_hint = (
        f"未検証の分析シナリオが {unv_narr} 件（問いの定義がまだ固まっていない）。"
        if unv_narr else ""
    )
    matrix_hint = (
        "◆ conformed: " + esc("・".join(conformed)) + " — この軸で複数プロセスを横断比較(drill-across)できます。"
        if conformed else "共有(conformed)ディメンションはまだありません。"
    )
    star_hint = (
        "role-playing: " + esc("；".join(roleplay)) + "（同じ軸を役割違いで複数回使用）。"
        if roleplay else ""
    )
    fact_hint = ""
    if gtd:
        dist_str = "・".join(f"{k}×{v}" for k, v in gtd.items())
        fact_hint = f"ファクト種別: {esc(dist_str)}。"
        if semi:
            fact_hint += f" semi-additive を含む: {esc('・'.join(semi))}（時間軸で合計しないよう注意）。"
    dim_hint = ""
    if type2 or conformed:
        bits = []
        if type2:
            bits.append("履歴保持(TYPE_2): " + esc("・".join(type2)))
        if conformed:
            bits.append(f"conformed: {len(conformed)} 軸")
        dim_hint = "。".join(bits) + "。"

    er_legend = (
        '<span><span class="k">FK</span>=軸への外部キー</span>'
        '<span><span class="k">measure</span>=測定値</span>'
        '<span><span class="k">degenerate</span>=表を持たない伝票番号</span>'
        '<span><span class="k">PK</span>=主キー(サロゲート)</span>'
        '<span><span class="k">scd</span>=履歴方式</span>'
        '<span><span class="k">||--o{</span>=1対多</span>'
    )

    return "\n".join([
        render_header(session),
        render_banner(errors),
        render_summary(model),
        render_explain(
            "このページは 1 つの分析モデルを複数の視点で見せます。上から「何を知りたい(§1)"
            "→どの粒度で(§4 グレイン)→どの軸で(§2/§5)→どの数値で(§4 測定値)」と具体化します。",
            howto="下のバッジの色で種別が一目で分かります。各章の ▶ が「何を示すか・どう読むか」です。",
            legend=badge_legend(),
            hint=orient_hint,
        ),
        "<h2>1. 分析シナリオ（答えたい問い・KPI）</h2>",
        render_explain(
            "このモデルで最終的に答えたい業務の問い・KPI。全設計の出発点で、以降のファクト/"
            "ディメンションはこの問いに答えるために選ばれます。",
            howto="<b>question</b>=まだ確定していない問い / <b>kpi</b>=定義済みの指標 / "
                  "<b>story</b>=背景。各カードの検証バッジで裏取り済みか分かります。",
            hint=narr_hint,
        ),
        render_narratives(model.get("narratives") or []),
        "<h2>2. バスマトリクス</h2>",
        render_explain(
            "「どの業務プロセス(行)が、どの共有ディメンション(列)を使うか」の全体地図。"
            "データウェアハウス全体の設計図です。",
            howto="<b>●</b>=そのファクトがその軸を使う / <b>·</b>=使わない / "
                  "<b>◆</b>=conformed(複数ファクトで共有) / 紫字=role-playing の役割名。"
                  "同じ列に ● が縦に並ぶほど、その軸で複数プロセスを突き合わせできます。",
            hint=matrix_hint,
        ),
        render_bus_matrix(model),
        "<h2>3. スタースキーマ</h2>",
        render_explain(
            "ファクト 1 つを中心に、それを取り囲むディメンションを星形で示します(1 ファクト=1 スター)。",
            howto="箱=表。線 <code>||--o{</code> は「1 対多」(ディメンション 1 件にファクトが多数"
                  "ぶら下がる)、線のラベルは結合の役割です。",
            read="読み下し例: <code>Date ||--o{ Sales : has</code> = 「1 つの日付に販売明細が"
                 "多数ぶら下がる」。同じ軸への線が複数あれば role-playing。",
            legend=er_legend,
            hint=star_hint,
        ),
        render_stars(model),
        "<h2>4. ファクト詳細（グレイン・測定値）</h2>",
        render_explain(
            "各ファクトのグレイン(1 行が表す実体)と測定値の一覧。グレインが全設計の土台です。",
            howto="黄枠=グレイン宣言。加法性: <b>additive</b>=どの軸でも合計可 / "
                  "<b>semi-additive</b>=一部(通常は時間)で合計不可(残高など) / "
                  "<b>non-additive</b>=そもそも合計不可(比率・単価。分子分母で持つ)。",
            hint=fact_hint,
        ),
        render_fact_details(model),
        "<h2>5. ディメンション詳細（SCD・階層・属性）</h2>",
        render_explain(
            "各軸(ディメンション)の属性・階層・変化の扱い(SCD)。",
            howto="SCD: <b>none</b>=不変 / <b>TYPE_1</b>=上書き(履歴なし) / "
                  "<b>TYPE_2</b>=変更時に履歴行を追加(過去を「当時の姿」で残せる)。"
                  "属性の <b>[surrogate]</b>=内部連番キー / <b>[natural]</b>=業務キー。"
                  "階層=ドリルダウン経路(粗→細)。",
            hint=dim_hint,
        ),
        render_dimension_details(model),
        "<h2>6. オープンクエスチョン</h2>",
        render_explain(
            "まだ裏取りできていない・決めきれていない論点。未検証(推測)を潰すための宿題リストです。",
            howto="各行の id で追跡し、決着したら意思決定ログ(§7)に紐付けてクローズします。",
        ),
        render_questions(model),
        "<h2>7. 意思決定ログ</h2>",
        render_explain(
            "後から効く設計判断(グレイン粒度・SCD 選択など)の「採用/不採用の理由」の記録。",
            howto="<b>✅</b>=採用した選択肢 / <b>▫️</b>=見送った選択肢。各行に業務語で理由が付きます。",
        ),
        render_decisions(model),
        "<h2>8. DimML ソース</h2>",
        render_explain(
            "この HTML の生成元＝唯一の真実源(source of truth)。HTML は派生物です。",
            howto="内容を変えるときは <code>.dimml.yaml</code> を編集して再ビルドします。"
                  "HTML を直接編集しないでください。",
        ),
        render_source(dml_text),
    ])


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render_html(dml_text: str) -> str:
    model = yaml.safe_load(dml_text) if yaml else None
    if not isinstance(model, dict):
        model = {}
    errors = validate_dimml_text(dml_text)
    session = model.get("session") or {}
    title = session.get("domain") or session.get("id") or "Dimensional Model"
    body = build_body(model, dml_text, errors)
    tpl = load_template()
    tpl = tpl.replace("{{TITLE}}", esc(title))
    tpl = tpl.replace("{{BODY}}", body)
    return tpl


def _session_stem(path: Path) -> str:
    name = path.name
    for suffix in (".dimml.yaml", ".dimml.yml", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def build(yaml_path: Path, out_dir: Path) -> Path:
    if yaml is None:
        raise RuntimeError("PyYAML が必要です（pip install pyyaml）")
    dml_text = yaml_path.read_text(encoding="utf-8")
    html_out = render_html(dml_text)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (_session_stem(yaml_path) + ".html")
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def build_all(in_dir: Path, out_dir: Path) -> list[Path]:
    outs = []
    for yaml_path in sorted(in_dir.glob("*.dimml.yaml")):
        outs.append(build(yaml_path, out_dir))
    return outs


def main() -> int:
    parser = argparse.ArgumentParser(description="DimML → HTML（バスマトリクス＋スタースキーマ）")
    parser.add_argument("path", nargs="?", help="*.dimml.yaml ファイルパス（省略時は --all）")
    parser.add_argument("--all", action="store_true", help="docs/dimensional/*.dimml.yaml を全ビルド")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="出力ディレクトリ")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if args.all:
        outs = build_all(DEFAULT_INPUT_DIR, out_dir)
        for o in outs:
            print(f"✅ built {o}")
        if not outs:
            print(f"⚠ {DEFAULT_INPUT_DIR} に *.dimml.yaml が見つかりません", file=sys.stderr)
        return 0
    if not args.path:
        parser.print_help(sys.stderr)
        return 2
    out = build(Path(args.path), out_dir)
    print(f"✅ built {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
