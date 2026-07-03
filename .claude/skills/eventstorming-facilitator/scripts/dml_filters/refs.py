"""DML 識別子の横断検索（refs）と一括リネーム（rename）の実装。

識別子（AGG / CMD / EVT / POL / QRY / VO / state / actor / ctx 名 / scenario 名 /
narrative id / decision id ...）は lang 辞書・scenarios・policies・aggregates・
transitions.via・next 連鎖など十数箇所に散在するため、手作業リネームは漏れが必発。
本モジュールは YAML ツリーを走査して:

- **occurrences**: 識別子と **完全一致** する dict キー / 文字列値（rename の置換対象）
- **mentions**: 散文・formula 等の文字列に識別子が **部分一致** で現れる箇所
  （rename では触らず報告のみ。英数字境界で判定するので `Event` は `EventId` にマッチしない）

を収集する。walker は PyYAML の素の dict/list と ruamel.yaml の
CommentedMap/CommentedSeq の両方で動く（rename は ruamel 側で呼びコメントを保持）。
"""

from __future__ import annotations

import re
from typing import Any, Callable

# 値が enum / 関係コードであり識別子参照ではないキー。この配下の「値」は
# 完全一致しても置換・検出の対象にしない（例: narrative id 'happy' のリネームで
# `kind: happy` を壊さない。up/dn の rel/roles/prRoles も DDD 関係コード）。
# キー自体のリネームは通常発生しないため、subtree ごとスキップする。
EXCLUDED_VALUE_KEYS = {"kind", "status", "brMode", "phase", "rel", "roles", "prRoles"}

# mentions の excerpt 最大長（散文全文を JSON に流さない）
_EXCERPT_LEN = 60


def _boundary_re(name: str) -> re.Pattern:
    """英数字境界つきの部分一致パターン。`Event` が `EventId` / `PublishEvent` に
    マッチしないよう、前後が [A-Za-z0-9] でないことを要求する（日本語識別子は
    前後が非英数字なのでそのまま部分一致になる）。"""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])")


def _walk(node, path: str, visit: Callable[[str, Any, Any, str], None]) -> None:
    """ツリーを走査し、dict キーと文字列リーフごとに visit を呼ぶ。

    visit(kind, container, key_or_index, path):
      - kind="key":   dict のキー（container[key] が対応値）
      - kind="value": dict 値の文字列
      - kind="item":  list 要素の文字列
    """
    if isinstance(node, dict):
        for k in list(node.keys()):
            v = node[k]
            kp = f"{path}.{k}" if path else str(k)
            visit("key", node, k, kp)
            if isinstance(k, str) and k in EXCLUDED_VALUE_KEYS:
                continue  # enum / 関係コードの値は対象外
            if isinstance(v, str):
                visit("value", node, k, kp)
            else:
                _walk(v, kp, visit)
    elif isinstance(node, list):
        for i in range(len(node)):
            v = node[i]
            ip = f"{path}[{i}]"
            if isinstance(v, str):
                visit("item", node, i, ip)
            else:
                _walk(v, ip, visit)


def _scoped_roots(model: dict, ctx: str) -> list[tuple[Any, str]]:
    """--ctx 指定時の走査ルート: contexts[name=ctx] 本体と、
    ctx 属性がその BC を指す aggregates/scenarios/policies/queries 要素。"""
    roots: list[tuple[Any, str]] = []
    for i, c in enumerate(model.get("contexts") or []):
        if isinstance(c, dict) and c.get("name") == ctx:
            roots.append((c, f"contexts[{i}]"))
    for sec in ("aggregates", "scenarios", "policies", "queries"):
        for i, item in enumerate(model.get(sec) or []):
            if isinstance(item, dict) and item.get("ctx") == ctx:
                roots.append((item, f"{sec}[{i}]"))
    return roots


def _iter_roots(model: dict, ctx: str | None) -> list[tuple[Any, str]]:
    if ctx:
        return _scoped_roots(model, ctx)
    return [(model, "")]


def collect_refs(model: dict, name: str, *, ctx: str | None = None) -> dict:
    """識別子 name の出現箇所を収集する（読み取り専用）。

    Returns: {"occurrences": [{"path", "kind"}], "mentions": [{"path", "excerpt"}]}
    """
    pattern = _boundary_re(name)
    occurrences: list[dict] = []
    mentions: list[dict] = []

    def visit(kind: str, container, key, path: str) -> None:
        if kind == "key":
            if key == name:
                occurrences.append({"path": path, "kind": "key"})
            return
        val = container[key]
        if val == name:
            occurrences.append({"path": path, "kind": kind})
        elif isinstance(val, str) and pattern.search(val):
            excerpt = val if len(val) <= _EXCERPT_LEN else val[:_EXCERPT_LEN] + "…"
            mentions.append({"path": path, "excerpt": excerpt.replace("\n", " ")})

    for node, prefix in _iter_roots(model, ctx):
        _walk(node, prefix, visit)
    return {"occurrences": occurrences, "mentions": mentions}


def _rename_key(mapping, old: str, new: str) -> None:
    """dict / CommentedMap のキーを位置・コメントを保ってリネームする。"""
    if hasattr(mapping, "insert"):  # ruamel CommentedMap
        pos = list(mapping.keys()).index(old)
        value = mapping.pop(old)
        mapping.insert(pos, new, value)
        ca = getattr(mapping, "ca", None)
        if ca is not None and old in ca.items:
            ca.items[new] = ca.items.pop(old)
    else:  # 素の dict（挿入順維持で再構築）
        items = [(new if k == old else k, v) for k, v in mapping.items()]
        mapping.clear()
        mapping.update(items)


def apply_rename(
    data, old: str, new: str, *, ctx: str | None = None
) -> tuple[list[str], list[str], list[str]]:
    """data（ruamel round-trip オブジェクト推奨）内の識別子 old を new に置換する。

    完全一致の dict キー / 文字列値のみ置換。散文中の部分一致は触らず mentions で返す。

    Returns: (replaced_paths, mention_paths, conflict_paths)
      - conflict_paths: キーリネーム先 new が同じ mapping に既存で、リネームすると
        キー重複になる箇所。**衝突があると置換は一切行わない**（呼び出し側で中断する）。
    """
    pattern = _boundary_re(old)
    key_renames: list[tuple[Any, str]] = []   # (mapping, path)
    value_sets: list[tuple[Any, Any, str]] = []  # (container, key_or_index, path)
    mentions: list[str] = []
    conflicts: list[str] = []

    def visit(kind: str, container, key, path: str) -> None:
        if kind == "key":
            if key == old:
                if new in container:
                    conflicts.append(path)
                else:
                    key_renames.append((container, path))
            return
        val = container[key]
        if val == old:
            value_sets.append((container, key, path))
        elif isinstance(val, str) and pattern.search(val):
            mentions.append(path)

    for node, prefix in _iter_roots(data, ctx):
        _walk(node, prefix, visit)

    if conflicts:
        return [], mentions, conflicts

    replaced: list[str] = []
    for mapping, path in key_renames:
        _rename_key(mapping, old, new)
        replaced.append(path)
    for container, key, path in value_sets:
        container[key] = new
        replaced.append(path)
    return replaced, mentions, []
