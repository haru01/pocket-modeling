#!/usr/bin/env python3
"""dmlctl — DML（YAML）に対する観点別 I/O CLI。

AI ファシリテーターが `.dml.yaml` 全文を Read/Edit する代わりに、本 CLI 経由で
**観点別スライス**だけを読み書きするための薄い API。LLM コンテキストの圧迫を抑えつつ、
構造化された編集を可能にする。

PreToolUse hook（block_direct_dml.py）と組み合わせると、AI からは本 CLI が
DML ファイルへの **唯一の I/O 経路** になる。

## サブコマンド

    dmlctl view  <file> --view=<name> [--out yaml|json] [--name <id>]
        観点別 YAML スライスを stdout に出力する（Read 代替）。
        `--view=full` は全文を返す（安全弁）。`--view=top-level-keys` は構造概要のみ。

    dmlctl init  <file> --session-id=<id> --domain=<name> [--goal=...] [--started-at=...]
        テンプレートから新規 DML ファイルを作成する（Write 代替）。
        既存ファイルがあれば拒否する（上書き事故防止）。

    dmlctl set   <file> --path=<a.b.c> (--value=<lit> | --value-file=<path>)
        単一フィールドを更新する。長文は --value-file で渡す（シェル引数上限回避）。

    dmlctl add   <file> --to=<list-path> (--item=<lit> | --item-file=<path>)
        リストに要素を 1 件追加する。

    dmlctl update <file> --path=<list-path> --where=<key=value> \
                  (--set-key=<k> --value=<v> | --merge-yaml=<dict-lit>)
        リスト内の特定要素を find & update する。

    dmlctl remove <file> --path=<a.b.c> [--where=<key=value>]
        フィールド/要素を削除する。--where 指定時はリスト内検索で削除。

    dmlctl check <file> --check=<name>
        構造チェック観点を実行し、違反を JSON で stdout に出力する。

    dmlctl validate <file>
        JSON Schema 全体検証を実行する（validate_dml.py のラッパー）。

    dmlctl build <file> [--all]
        HTML を再生成する（eventstorming_build.py のラッパー）。

## view / check 一覧

    dmlctl views      # 利用可能な view 名を列挙
    dmlctl checks     # 利用可能な check 名を列挙

## ruamel.yaml について

set/add/remove/update/init は `pip install ruamel.yaml` が必要。未導入時は明示的にエラー終了する。

## 書き込み後の自動処理

set/add/remove/update/init は成功後に build + validate を自動実行する
（PreToolUse で Write/Edit がブロックされて PostToolUse hook が走らないため）。
`--no-postprocess` で抑止可能（主にテスト用途）。
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
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


TEMPLATE_PATH = SCRIPT_DIR.parent / "references" / "template.dml.yaml"
BUILD_SCRIPT = SCRIPT_DIR / "eventstorming_build.py"
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_dml.py"

DML_HEADER = (
    "# ⚠ This file is managed by dmlctl (.claude/skills/eventstorming-facilitator/scripts/dmlctl.py).\n"
    "# AI agents must use `dmlctl view/init/set/add/remove/update` and MUST NOT edit this file directly\n"
    "# (PreToolUse hook blocks direct Read/Edit/Write). Humans may edit outside Claude Code.\n"
    "\n"
)


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
            "❌ set/add/remove/update/init には ruamel.yaml が必要です（`pip install ruamel.yaml`）。\n"
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


def _resolve_list(data, path: str) -> list:
    """path 先のオブジェクトがリストであることを保証して返す。"""
    segments = _parse_path(path)
    target = data
    for seg in segments:
        target = target[seg]
    if not isinstance(target, list):
        raise ValueError(f"{path} はリストではありません")
    return target


def _parse_value(text: str):
    """`--value` に渡された YAML リテラルを Python 値に変換する。"""
    return yaml.safe_load(text)


def _deep_merge(dst, patch: dict) -> None:
    """patch（素の dict）を dst（ruamel map）へ **再帰的に** マージする。

    - `patch[k]` が dict かつ `dst[k]` も dict → 中へ降りて再帰マージ
      （例: `{lang: {states: {...}}}` を渡すと `lang.actors` 等を壊さず
       `lang.states` だけ追加・更新できる）
    - それ以外（スカラー・リスト・新規キー）→ `dst[k] = patch[k]` で置換

    ネストした dict は残し、リーフ（スカラー/リスト）は丸ごと差し替える
    という直感的な merge セマンティクス。dict 全体を置き換えたい場合は
    merge ではなく `update --set-key` を使う。"""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def _read_value_or_file(args, value_attr: str, file_attr: str):
    """`--value` と `--value-file` の排他処理。値を Python 値で返す。

    long-prose の安全な書き込みのため、--value-file は **生テキスト** として
    読み込み、文字列値として埋め込む（YAML literal 評価しない）。
    """
    value = getattr(args, value_attr, None)
    file_path = getattr(args, file_attr, None)
    if value is None and file_path is None:
        raise SystemExit(
            f"❌ --{value_attr.replace('_', '-')} か --{file_attr.replace('_', '-')} のいずれかが必須"
        )
    if value is not None and file_path is not None:
        raise SystemExit(
            f"❌ --{value_attr.replace('_', '-')} と --{file_attr.replace('_', '-')} は排他"
        )
    if file_path is not None:
        text = Path(file_path).read_text(encoding="utf-8")
        return text
    return _parse_value(value)


def _parse_where(where: str) -> tuple[str, object]:
    """`key=value` 文字列を (key, value) に分解する。value は YAML literal として評価。"""
    if "=" not in where:
        raise SystemExit(f"❌ --where は key=value 形式で指定してください: 受信={where}")
    key, _, raw = where.partition("=")
    key = key.strip()
    return key, _parse_value(raw.strip())


def _save_and_postprocess(path: Path, yml, data, *, no_postprocess: bool = False) -> None:
    """ruamel YAML を保存し、必要なら build + validate を実行する。"""
    with path.open("w", encoding="utf-8") as f:
        yml.dump(data, f)
    if no_postprocess:
        return
    _run_postprocess(path)


def _run_postprocess(path: Path) -> None:
    """build + validate を順に実行する。失敗は stderr に出すが exit code は引き継がない。"""
    try:
        subprocess.run(["python3", str(BUILD_SCRIPT), str(path)], check=False)
    except FileNotFoundError:
        print(f"⚠ build スクリプトが見つかりません: {BUILD_SCRIPT}", file=sys.stderr)
    try:
        result = subprocess.run(
            ["python3", str(VALIDATE_SCRIPT), str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stderr:
            sys.stderr.write(result.stderr)
        if result.returncode != 0:
            print(
                f"⚠ validate_dml.py が違反を報告しました（exit {result.returncode}）",
                file=sys.stderr,
            )
    except FileNotFoundError:
        print(f"⚠ validate スクリプトが見つかりません: {VALIDATE_SCRIPT}", file=sys.stderr)


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

    if args.view == "full":
        try:
            line_count = Path(args.file).read_text(encoding="utf-8").count("\n")
            if line_count > 500:
                print(
                    f"⚠ full view: {line_count} 行と大きい DML です。観点別 view（dmlctl views）の利用を推奨します。",
                    file=sys.stderr,
                )
        except OSError:
            pass

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
# サブコマンド: init（新規ファイル作成）
# ============================================================


def cmd_init(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    if path.exists():
        print(
            f"❌ {path} はすでに存在します。上書き事故防止のため init は拒否されました。\n"
            f"   既存ファイルを編集するには dmlctl set/add/update を使ってください。",
            file=sys.stderr,
        )
        return 2

    if not TEMPLATE_PATH.exists():
        print(f"❌ テンプレートが見つかりません: {TEMPLATE_PATH}", file=sys.stderr)
        return 2

    with TEMPLATE_PATH.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None or not isinstance(data, dict):
        data = {}

    session = {
        "id": args.session_id,
        "domain": args.domain,
        "phase": "1",
        "status": "Phase 1 (スコープ確認中)",
    }
    if args.goal:
        session["goal"] = args.goal
    if args.started_at:
        session["started_at"] = args.started_at
    session["html_link"] = f"../../dist/eventstorming/{args.session_id}.html"

    data["session"] = session

    path.parent.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    yml.dump(data, buf)
    body = buf.getvalue()
    path.write_text(DML_HEADER + body, encoding="utf-8")

    print(f"✅ {path} を作成しました（session id={args.session_id}）")
    if not args.no_postprocess:
        _run_postprocess(path)
    return 0


# ============================================================
# サブコマンド: set / add / remove / update（ruamel.yaml で round-trip）
# ============================================================


def cmd_set(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        data = {}
    segments = _parse_path(args.path)
    value = _read_value_or_file(args, "value", "value_file")
    parent, last = _resolve_parent(data, segments)
    parent[last] = value
    _save_and_postprocess(path, yml, data, no_postprocess=args.no_postprocess)
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

    if args.item is None and args.item_file is None:
        print("❌ --item か --item-file のいずれかが必須", file=sys.stderr)
        return 1
    if args.item is not None and args.item_file is not None:
        print("❌ --item と --item-file は排他", file=sys.stderr)
        return 1
    if args.item_file is not None:
        text = Path(args.item_file).read_text(encoding="utf-8")
        item = yaml.safe_load(text)
    else:
        item = _parse_value(args.item)
    target.append(item)
    _save_and_postprocess(path, yml, data, no_postprocess=args.no_postprocess)
    return 0


def cmd_remove(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        print(f"⚠ {args.file} は空です", file=sys.stderr)
        return 0

    if args.where:
        target_list = _resolve_list(data, args.path)
        key, expected = _parse_where(args.where)
        matched_indices = [
            i
            for i, elem in enumerate(target_list)
            if isinstance(elem, dict) and elem.get(key) == expected
        ]
        if not matched_indices:
            print(f"❌ {args.path} に {key}={expected!r} の要素が見つかりません", file=sys.stderr)
            return 2
        for idx in reversed(matched_indices):
            del target_list[idx]
        print(
            f"✅ {args.path}[{key}={expected!r}] を {len(matched_indices)} 件削除しました",
            file=sys.stderr,
        )
    else:
        segments = _parse_path(args.path)
        parent, last = _resolve_parent(data, segments)
        del parent[last]
    _save_and_postprocess(path, yml, data, no_postprocess=args.no_postprocess)
    return 0


def cmd_update(args) -> int:
    yml = _require_ruamel()
    path = Path(args.file)
    with path.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    if data is None:
        print(f"❌ {args.file} は空です", file=sys.stderr)
        return 2

    target_list = _resolve_list(data, args.path)
    key, expected = _parse_where(args.where)
    matched_indices = [
        i
        for i, elem in enumerate(target_list)
        if isinstance(elem, dict) and elem.get(key) == expected
    ]
    if not matched_indices:
        print(f"❌ {args.path} に {key}={expected!r} の要素が見つかりません", file=sys.stderr)
        return 2
    if len(matched_indices) > 1 and not args.allow_multiple:
        print(
            f"❌ {args.path} に {key}={expected!r} の要素が {len(matched_indices)} 件見つかりました。\n"
            f"   複数件への適用を許可するには --allow-multiple を指定してください。",
            file=sys.stderr,
        )
        return 2

    if args.set_key is not None:
        value = _read_value_or_file(args, "value", "value_file")
        patch = {args.set_key: value}
    elif args.merge_yaml is not None:
        patch = _parse_value(args.merge_yaml)
        if not isinstance(patch, dict):
            print(f"❌ --merge-yaml は dict を期待: 受信={patch!r}", file=sys.stderr)
            return 2
    else:
        print("❌ --set-key + --value(-file) もしくは --merge-yaml が必須", file=sys.stderr)
        return 2

    for idx in matched_indices:
        elem = target_list[idx]
        _deep_merge(elem, patch)
    print(
        f"✅ {args.path}[{key}={expected!r}] を {len(matched_indices)} 件更新しました",
        file=sys.stderr,
    )
    _save_and_postprocess(path, yml, data, no_postprocess=args.no_postprocess)
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
# サブコマンド: validate / build（既存スクリプトのラッパー）
# ============================================================


def cmd_validate(args) -> int:
    result = subprocess.run(["python3", str(VALIDATE_SCRIPT), args.file], check=False)
    return result.returncode


def cmd_build(args) -> int:
    cmd = ["python3", str(BUILD_SCRIPT)]
    if args.all:
        cmd.append("--all")
    elif args.file:
        cmd.append(args.file)
    else:
        print("❌ build には <file> または --all が必要", file=sys.stderr)
        return 2
    if args.watch:
        cmd.append("--watch")
    result = subprocess.run(cmd, check=False)
    return result.returncode


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

    p_init = sub.add_parser("init", help="新規 DML ファイルをテンプレートから作成する")
    p_init.add_argument("file")
    p_init.add_argument("--session-id", required=True, help="session.id（例: eventstorming-20260530-1430）")
    p_init.add_argument("--domain", required=True, help="session.domain（例: trivago-hotel-search）")
    p_init.add_argument("--goal", help="session.goal（任意）")
    p_init.add_argument("--started-at", help="session.started_at（ISO8601）")
    p_init.add_argument("--no-postprocess", action="store_true", help="build + validate を抑止（テスト用）")
    p_init.set_defaults(func=cmd_init)

    p_set = sub.add_parser("set", help="単一フィールドを更新する（ruamel.yaml）")
    p_set.add_argument("file")
    p_set.add_argument("--path", required=True, help="例: session.status")
    p_set.add_argument("--value", help="YAML リテラル")
    p_set.add_argument("--value-file", help="長文値を含むファイル（生テキストとして埋め込む）")
    p_set.add_argument("--no-postprocess", action="store_true")
    p_set.set_defaults(func=cmd_set)

    p_add = sub.add_parser("add", help="リストに要素を追加する（ruamel.yaml）")
    p_add.add_argument("file")
    p_add.add_argument("--to", required=True, help="例: questions")
    p_add.add_argument("--item", help="YAML リテラル")
    p_add.add_argument("--item-file", help="大型 YAML 要素を含むファイル")
    p_add.add_argument("--no-postprocess", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="リスト内の特定要素を find & update する（ruamel.yaml）")
    p_update.add_argument("file")
    p_update.add_argument("--path", required=True, help="リストへのパス（例: scenarios）")
    p_update.add_argument("--where", required=True, help="key=value の絞り込み式")
    p_update.add_argument("--set-key", help="単一キー更新時のキー名")
    p_update.add_argument("--value", help="--set-key と組で使う YAML リテラル")
    p_update.add_argument("--value-file", help="--set-key と組で使う長文ファイル")
    p_update.add_argument("--merge-yaml", help="dict を YAML リテラルで指定し対象要素に再帰マージする（nested dict は保持、リーフは置換）")
    p_update.add_argument("--allow-multiple", action="store_true", help="複数マッチを許容して全件更新")
    p_update.add_argument("--no-postprocess", action="store_true")
    p_update.set_defaults(func=cmd_update)

    p_remove = sub.add_parser("remove", help="フィールド/要素を削除する（ruamel.yaml）")
    p_remove.add_argument("file")
    p_remove.add_argument("--path", required=True)
    p_remove.add_argument("--where", help="リスト内検索 key=value")
    p_remove.add_argument("--no-postprocess", action="store_true")
    p_remove.set_defaults(func=cmd_remove)

    p_check = sub.add_parser("check", help="構造チェック観点を実行する")
    p_check.add_argument("file")
    p_check.add_argument("--check", required=True, help="check 名（dmlctl checks で一覧）")
    p_check.set_defaults(func=cmd_check)

    p_validate = sub.add_parser("validate", help="JSON Schema 検証を実行する（validate_dml.py のラッパー）")
    p_validate.add_argument("file")
    p_validate.set_defaults(func=cmd_validate)

    p_build = sub.add_parser("build", help="HTML を再生成する（eventstorming_build.py のラッパー）")
    p_build.add_argument("file", nargs="?", help="対象 DML（--all 指定時は省略可）")
    p_build.add_argument("--all", action="store_true", help="全 DML を一括ビルド")
    p_build.add_argument("--watch", action="store_true", help="監視モード")
    p_build.set_defaults(func=cmd_build)

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
