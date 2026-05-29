#!/usr/bin/env python3
"""dmlctl — DML（YAML）に対する観点別 I/O CLI。

AI ファシリテーターが `.dml.yaml` 全文を Read/Edit する代わりに、本 CLI 経由で
**観点別スライス**だけを読み書きするための薄い API。LLM コンテキストの圧迫を抑えつつ、
構造化された編集を可能にする。

## サブコマンド

    dmlctl view  <file> --view=<name> [--out yaml|json] [--name <id>]
        観点別 YAML スライスを stdout に出力する（Read 代替）。

    dmlctl set   <file> --path=<a.b.c> --value=<yaml-literal>
        単一フィールドを更新する。コメントを保つため ruamel.yaml が必要。

    dmlctl add   <file> --to=<list-path> --item=<yaml-literal>
        リストに要素を 1 件追加する。ruamel.yaml が必要。

    dmlctl remove <file> --path=<a.b.c>
        フィールド/要素を削除する。ruamel.yaml が必要。

    dmlctl check <file> --check=<name>
        構造チェック観点を実行し、違反を JSON で stdout に出力する。

## view / check 一覧

    dmlctl views      # 利用可能な view 名を列挙
    dmlctl checks     # 利用可能な check 名を列挙

## ruamel.yaml について

set/add/remove は `pip install ruamel.yaml` が必要。未導入時は明示的にエラー終了する。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    print("❌ PyYAML が必要です（`pip install pyyaml`）", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dml_filters.views import VIEWS  # noqa: E402
from dml_filters.checks import CHECKS, finding_to_dict  # noqa: E402


# ============================================================
# 共通: YAML 読み込み（read-only / PyYAML）
# ============================================================


def load_model(yaml_path: Path) -> dict:
    text = yaml_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"❌ YAML 解析失敗: {e}", file=sys.stderr)
        sys.exit(2)
    return loaded if isinstance(loaded, dict) else {}


# ============================================================
# 共通: 編集用 ruamel.yaml round-trip
# ============================================================


def _require_ruamel():
    """ruamel.yaml をロードし、未導入時は friendly error で終了。"""
    try:
        from ruamel.yaml import YAML  # type: ignore
    except ImportError:
        print(
            "❌ set/add/remove には ruamel.yaml が必要です（`pip install ruamel.yaml`）。\n"
            "   コメント・引用形式・キー順を保ったまま編集するためです。",
            file=sys.stderr,
        )
        sys.exit(3)
    yml = YAML(typ="rt")
    yml.preserve_quotes = True
    yml.indent(mapping=2, sequence=4, offset=2)
    yml.width = 4096
    return yml


def _parse_path(path: str) -> list:
    """ドット区切りパスをセグメント列に変換する。

    数値インデックスは `users.0.name` のように記述する。引用付き
    （`contexts[name="store-front"].lang.cmds.PlaceOrder`）には未対応で、
    まずは単純な `key.0.key` 形式のみサポート。
    """
    segments = []
    for seg in path.split("."):
        if seg.isdigit():
            segments.append(int(seg))
        else:
            segments.append(seg)
    return segments


def _resolve_parent(data, segments: list):
    """セグメント列の親要素と最終キーを返す。"""
    if not segments:
        raise ValueError("path は空にできません")
    cursor = data
    for seg in segments[:-1]:
        cursor = cursor[seg]
    return cursor, segments[-1]


def _parse_value(text: str):
    """`--value` に渡された YAML リテラルを Python 値に変換する。"""
    return yaml.safe_load(text)


# ============================================================
# サブコマンド: view
# ============================================================


def cmd_view(args) -> int:
    if args.view not in VIEWS:
        print(f"❌ 未知の view: {args.view}\n   利用可能: {', '.join(VIEWS)}", file=sys.stderr)
        return 1
    model = load_model(Path(args.file))
    kwargs = {}
    if args.name is not None:
        kwargs["name"] = args.name
    if args.id is not None:
        kwargs["id"] = args.id
    if args.ctx is not None:
        kwargs["ctx"] = args.ctx
    result = VIEWS[args.view](model, **kwargs)

    if args.out == "json":
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        yaml.safe_dump(
            result,
            sys.stdout,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    return 0


# ============================================================
# サブコマンド: set / add / remove（ruamel.yaml で round-trip）
# ============================================================


def cmd_set(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        data = {}
    segments = _parse_path(args.path)
    value = _parse_value(args.value)
    parent, last = _resolve_parent(data, segments)
    parent[last] = value
    with path.open("w", encoding="utf-8") as f:
        yml.dump(data, f)
    return 0


def cmd_add(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        data = {}
    segments = _parse_path(args.to)
    target = data
    for seg in segments:
        target = target[seg]
    if not isinstance(target, list):
        print(f"❌ {args.to} はリストではありません", file=sys.stderr)
        return 1
    item = _parse_value(args.item)
    target.append(item)
    with path.open("w", encoding="utf-8") as f:
        yml.dump(data, f)
    return 0


def cmd_remove(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        print(f"⚠ {args.file} は空です", file=sys.stderr)
        return 0
    segments = _parse_path(args.path)
    parent, last = _resolve_parent(data, segments)
    del parent[last]
    with path.open("w", encoding="utf-8") as f:
        yml.dump(data, f)
    return 0


# ============================================================
# サブコマンド: check
# ============================================================


def cmd_check(args) -> int:
    if args.check not in CHECKS:
        print(f"❌ 未知の check: {args.check}\n   利用可能: {', '.join(CHECKS)}", file=sys.stderr)
        return 1
    model = load_model(Path(args.file))
    findings = CHECKS[args.check](model)
    payload = {
        "check": args.check,
        "count": len(findings),
        "findings": [finding_to_dict(f) for f in findings],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0 if not findings else 1


# ============================================================
# サブコマンド: views / checks（一覧表示）
# ============================================================


def cmd_list_views(_args) -> int:
    for name in VIEWS:
        print(name)
    return 0


def cmd_list_checks(_args) -> int:
    for name in CHECKS:
        print(name)
    return 0


# ============================================================
# CLI 配線
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dmlctl", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_view = sub.add_parser("view", help="観点別 YAML スライスを表示する")
    p_view.add_argument("file")
    p_view.add_argument("--view", required=True, help="view 名（dmlctl views で一覧）")
    p_view.add_argument("--out", choices=["yaml", "json"], default="yaml")
    p_view.add_argument("--name", help="agg-detail / bc-language で対象を絞る name")
    p_view.add_argument("--id", help="flow-causality で対象を絞る id")
    p_view.add_argument("--ctx", help="scenarios / policies で対象を絞る ctx 名")
    p_view.set_defaults(func=cmd_view)

    p_set = sub.add_parser("set", help="単一フィールドを更新する（ruamel.yaml）")
    p_set.add_argument("file")
    p_set.add_argument("--path", required=True, help="例: session.status")
    p_set.add_argument("--value", required=True, help="YAML リテラル")
    p_set.set_defaults(func=cmd_set)

    p_add = sub.add_parser("add", help="リストに要素を追加する（ruamel.yaml）")
    p_add.add_argument("file")
    p_add.add_argument("--to", required=True, help="例: questions")
    p_add.add_argument("--item", required=True, help="YAML リテラル")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="フィールド/要素を削除する（ruamel.yaml）")
    p_remove.add_argument("file")
    p_remove.add_argument("--path", required=True)
    p_remove.set_defaults(func=cmd_remove)

    p_check = sub.add_parser("check", help="構造チェック観点を実行する")
    p_check.add_argument("file")
    p_check.add_argument("--check", required=True, help="check 名（dmlctl checks で一覧）")
    p_check.set_defaults(func=cmd_check)

    p_views = sub.add_parser("views", help="利用可能な view 名を列挙する")
    p_views.set_defaults(func=cmd_list_views)

    p_checks = sub.add_parser("checks", help="利用可能な check 名を列挙する")
    p_checks.set_defaults(func=cmd_list_checks)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
