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
    return "\n".join([
        render_header(session),
        render_banner(errors),
        render_summary(model),
        "<h2>1. 分析シナリオ（答えたい問い・KPI）</h2>",
        render_narratives(model.get("narratives") or []),
        "<h2>2. バスマトリクス</h2>",
        render_bus_matrix(model),
        "<h2>3. スタースキーマ</h2>",
        render_stars(model),
        "<h2>4. ファクト詳細（グレイン・測定値）</h2>",
        render_fact_details(model),
        "<h2>5. ディメンション詳細（SCD・階層・属性）</h2>",
        render_dimension_details(model),
        "<h2>6. オープンクエスチョン</h2>",
        render_questions(model),
        "<h2>7. 意思決定ログ</h2>",
        render_decisions(model),
        "<h2>8. DimML ソース</h2>",
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
