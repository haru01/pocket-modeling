"""DML パスの期待型ヒント（dmlctl hint）の実装。

`set/add/update` の最大の摩擦は型非対称（`queries[].users` は文字列 /
`queries[].sources` は配列 / `brs[].pol` は文字列・配列どちらも可 ...）による
書き込みリトライ。本モジュールは `references/dml.schema.yaml`（JSON Schema
Draft 2020-12）を歩いて、指定パスの **期待型・enum・pattern・必須キー** と
`--value` に渡すリテラル例を **書き込み前に** 提示する。

`--dry-run`（書いてから検証）に対する「書く前の案内」。

パス文法は dmlctl の set/add と同じドット区切り。数値インデックス
（`scenarios.3.cmd`）・セレクタ（`contexts[name=billing].lang`）・明示 `[]`
（`scenarios[].brs[].pol`）はいずれも「配列の要素へ降りる」と解釈する。
リスト名の直後にキーを書いた場合（`queries.users`）は items へ自動で降りる。
"""

from __future__ import annotations

import re
from typing import Any

# 「配列の要素へ降りる」ことを表す内部マーカー
_ITEM = object()

_SELECTOR_RE = re.compile(r"^([^\[\].]+)\[[^\[\]]*\]$")  # base[...] / base[]


def parse_hint_path(path: str) -> list:
    """ドット区切りパスをセグメント列（str | _ITEM）に変換する。"""
    segments: list = []
    for seg in path.split("."):
        if not seg:
            continue
        m = _SELECTOR_RE.match(seg)
        if m:
            segments.append(m.group(1))
            segments.append(_ITEM)
        elif seg.isdigit():
            segments.append(_ITEM)
        else:
            segments.append(seg)
    return segments


def _resolve(schema: dict, node: dict) -> tuple[dict, str | None]:
    """$ref チェーンを解決し、(実体ノード, 最後の $defs 名 or None) を返す。"""
    ref_name = None
    seen = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if ref in seen:
            break  # 循環ガード
        seen.add(ref)
        if not ref.startswith("#/$defs/"):
            break
        ref_name = ref.split("/")[-1]
        node = (schema.get("$defs") or {}).get(ref_name) or {}
    return node, ref_name


def _children(schema: dict, node: dict, seg) -> list[dict]:
    """1 セグメント分降りた先の候補スキーマノードを返す（oneOf は全分岐を試す）。"""
    node, _ = _resolve(schema, node)
    if "oneOf" in node:
        out: list[dict] = []
        for alt in node["oneOf"]:
            out.extend(_children(schema, alt, seg))
        return out
    if seg is _ITEM:
        items = node.get("items")
        return [items] if isinstance(items, dict) else []
    # seg はキー名
    if isinstance(node.get("items"), dict):
        # リスト名の直後にキー → items へ自動で降りる（`queries.users` 許容）
        return _children(schema, node["items"], seg)
    props = node.get("properties") or {}
    if seg in props:
        return [props[seg]]
    ap = node.get("additionalProperties")
    if isinstance(ap, dict):
        return [ap]  # 任意キーの辞書（lang.cmds.<EnId> など）
    return []


def _valid_keys(schema: dict, nodes: list[dict]) -> list[str]:
    """候補ノード群で受け付けられるキー名の一覧（エラーメッセージ用）。"""
    keys: set[str] = set()
    for node in nodes:
        node, _ = _resolve(schema, node)
        if "oneOf" in node:
            keys.update(_valid_keys(schema, node["oneOf"]))
            continue
        if isinstance(node.get("items"), dict):
            keys.update(_valid_keys(schema, [node["items"]]))
            continue
        keys.update((node.get("properties") or {}).keys())
    return sorted(keys)


def _short(schema: dict, node: dict, depth: int = 0) -> str:
    """プロパティ一覧用の短い型ラベル。

    depth=0 の object は 1 階層だけプロパティ名を展開する
    （`object{name, type, vision}` のように）。depth>=1 では名前だけに潰して
    無限再帰を防ぐ。array の要素も depth を引き継ぐ。
    """
    node, ref = _resolve(schema, node)
    if "oneOf" in node:
        return " | ".join(_short(schema, alt, depth) for alt in node["oneOf"])
    if "enum" in node:
        return f"enum[{', '.join(map(str, node['enum']))}]"
    t = node.get("type")
    if t == "array":
        items = node.get("items")
        inner = _short(schema, items, depth) if isinstance(items, dict) else "any"
        return f"array<{inner}>"
    if t == "object" or "properties" in node:
        props = node.get("properties") or {}
        if depth < 1 and props:
            inner = ", ".join(props.keys())
            base = ref or "object"
            return f"{base}{{{inner}}}"
        return ref or "object"
    if ref:
        return f"{ref}({t or 'string'})"
    return t or "any"


def _conditional_and_exclusive(node: dict) -> tuple[list[str], list[str]]:
    """object ノードの allOf / node 直下 not から、条件付き必須と排他制約を抽出する。

    - if-then（`{if: {required:[k], properties:{k:{const:v}}}, then:{required:[r,...]}}`）
      → 「k: v のとき r 必須」（例: policy の bulk: true → qry 必須）
    - not.required（`{not: {required:[a, b]}}`。allOf 要素 or node 直下の両方）
      → 「a と b は同時指定不可」（例: policy の trg / trgs 排他）
    """
    conditional: list[str] = []
    exclusive: list[str] = []

    def _add_not(sub: dict) -> None:
        req = ((sub or {}).get("required")) or []
        if len(req) >= 2:
            exclusive.append(" と ".join(req) + " は同時指定不可")

    def _add_if_then(sub: dict) -> None:
        cond = sub.get("if") or {}
        then = sub.get("then") or {}
        cond_req = cond.get("required") or []
        then_req = then.get("required") or []
        if not then_req:
            return
        cond_props = cond.get("properties") or {}
        parts = []
        for k in cond_req:
            const = (cond_props.get(k) or {}).get("const")
            if const is None:
                parts.append(k)
            elif isinstance(const, bool):
                parts.append(f"{k}: {'true' if const else 'false'}")
            else:
                parts.append(f"{k}: {const}")
        trigger = " かつ ".join(parts) if parts else "条件成立時"
        conditional.append(f"{trigger} のとき {', '.join(then_req)} 必須")

    for sub in node.get("allOf") or []:
        if not isinstance(sub, dict):
            continue
        if "not" in sub:
            _add_not(sub["not"])
        if "if" in sub and "then" in sub:
            _add_if_then(sub)
    if isinstance(node.get("not"), dict):
        _add_not(node["not"])
    return conditional, exclusive


def _describe(schema: dict, node: dict) -> dict:
    """ヒント表示用の構造化された型記述を返す。"""
    node, ref = _resolve(schema, node)
    if "oneOf" in node:
        return {"oneOf": [_describe(schema, alt) for alt in node["oneOf"]]}
    d: dict[str, Any] = {}
    if ref:
        d["ref"] = ref
    if "enum" in node:
        d["type"] = node.get("type", "string")
        d["enum"] = list(node["enum"])
        return d
    t = node.get("type")
    if t == "array":
        d["type"] = "array"
        items = node.get("items")
        if isinstance(items, dict):
            d["items"] = _describe(schema, items)
        if "minItems" in node:
            d["minItems"] = node["minItems"]
        return d
    if t == "object" or "properties" in node or isinstance(node.get("additionalProperties"), dict):
        d["type"] = "object"
        if node.get("required"):
            d["required"] = list(node["required"])
        conditional, exclusive = _conditional_and_exclusive(node)
        if conditional:
            d["conditional"] = conditional
        if exclusive:
            d["exclusive"] = exclusive
        props = node.get("properties") or {}
        if props:
            d["properties"] = {k: _short(schema, v) for k, v in props.items()}
        ap = node.get("additionalProperties")
        if isinstance(ap, dict):
            d["additionalProperties"] = _short(schema, ap)
            d.setdefault("note", "任意キーの辞書（キー名は自由、値は上記型）")
        return d
    d["type"] = t or "any"
    if "pattern" in node:
        d["pattern"] = node["pattern"]
    return d


_REF_EXAMPLES = {
    "pascalCase": "SomeName",
    "contextName": "some-context",
    "upperSnake": "SOME_STATE",
}


def _literal(schema: dict, node: dict, depth: int = 0) -> str:
    """YAML リテラル例（シェルクォート無し）を生成する。ネストは深さ 2 まで。"""
    node, ref = _resolve(schema, node)
    if "oneOf" in node:
        # ネスト内の oneOf は先頭の分岐で代表させる（トップの oneOf は呼び出し側が展開）
        return _literal(schema, node["oneOf"][0], depth)
    if "enum" in node:
        v = node["enum"][0]
        return f'"{v}"' if isinstance(v, str) else str(v)
    if ref in _REF_EXAMPLES:
        return _REF_EXAMPLES[ref]
    t = node.get("type")
    if t == "string":
        # トップレベルのスカラー文字列は「クォートして渡す」を明示（session.phase 型の落とし穴対策）。
        # ネスト内（flow mapping 中）は bare word で十分。
        return '"テキスト"' if depth == 0 else "テキスト"
    if t == "boolean":
        return "true"
    if t in ("integer", "number"):
        return "1"
    if t == "array":
        items = node.get("items")
        if isinstance(items, dict) and depth < 2:
            return f"[{_literal(schema, items, depth + 1)}]"
        return "[...]"
    if t == "object" or "properties" in node:
        req = node.get("required") or []
        props = node.get("properties") or {}
        if req and depth < 2:
            inner = ", ".join(
                f"{k}: {_literal(schema, props.get(k, {}), depth + 1)}" for k in req
            )
            return f"{{{inner}}}"
        return "{key: value}"
    return "..."


def _example(schema: dict, candidates: list[dict], path: str) -> str:
    """最終ノード群からコピペ可能な CLI 例を組み立てる。

    - 配列パス → `add --to=<path> --item='<要素例>'`（要素追加が典型操作）
    - それ以外 → `set --path=<path> --value='<例>'`。oneOf は全分岐を「または」で並記
    """
    resolved = [_resolve(schema, c)[0] for c in candidates]
    if len(resolved) == 1 and "oneOf" not in resolved[0] and resolved[0].get("type") == "array":
        items = resolved[0].get("items")
        item_lit = _literal(schema, items, 1) if isinstance(items, dict) else "..."
        return f"add --to={path} --item='{item_lit}'"

    lits: list[str] = []
    for cand in candidates:
        node, _ = _resolve(schema, cand)
        # oneOf でなければ元ノードを渡す（resolve 済みノードだと $ref 名が落ちて
        # pascalCase 等の例示が汎用文字列に化ける）
        alts = node["oneOf"] if "oneOf" in node else [cand]
        for alt in alts:
            lit = _literal(schema, alt)
            if lit not in lits:
                lits.append(lit)
    return " または ".join(f"set --path={path} --value='{lit}'" for lit in lits)


def resolve_hint(schema: dict, path: str) -> dict:
    """パスの期待型ヒントを返す。解決不能なら {"error", "valid_keys"} を返す。"""
    segments = parse_hint_path(path)
    if not segments:
        return {"error": "path が空です"}
    candidates: list[dict] = [schema]
    walked: list[str] = []
    for seg in segments:
        next_candidates: list[dict] = []
        for cand in candidates:
            next_candidates.extend(_children(schema, cand, seg))
        if not next_candidates:
            label = "[]" if seg is _ITEM else str(seg)
            return {
                "error": f"パス '{path}' の '{label}' が schema に見つかりません"
                + (f"（'{'.'.join(walked)}' まで解決）" if walked else ""),
                "valid_keys": _valid_keys(schema, candidates),
            }
        candidates = next_candidates
        walked.append("[]" if seg is _ITEM else str(seg))

    if len(candidates) == 1:
        hint = _describe(schema, candidates[0])
    else:
        hint = {"oneOf": [_describe(schema, c) for c in candidates]}
    return {"path": path, "hint": hint, "example": _example(schema, candidates, path)}
