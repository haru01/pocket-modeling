#!/usr/bin/env python3
"""DML (.dml.yaml) を JSON Schema (references/dml.schema.yaml) で検証する。

- `validate_dml_text(text)` / `validate_dml_file(path)` は **人間可読なエラー文字列のリスト**を返す
  （空リスト = 違反なし）。`eventstorming_build.py` / `parse_eventstorming_md.py` から import して
  「警告のみ（non-blocking）」で使う。
- CLI（`python3 validate_dml.py <path.dml.yaml> ...`）は違反一覧を stderr に出し、
  違反があれば exit code 1 を返す（CI ゲート用）。

空 / None / 非 dict（コメントのみの進行中セッション）は「未記述」とみなし違反なし扱い。
スキーマ自体が読めない場合も静かにスキップ（[] を返す）し、ツールチェーンを止めない。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as e:  # 依存が無い環境では検証スキップ（呼び出し側を止めない）
    yaml = None  # type: ignore
    Draft202012Validator = None  # type: ignore
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "dml.schema.yaml"

# スキーマは1回だけ読み込んでキャッシュする
_SCHEMA_CACHE: dict | None = None


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict | None:
    """スキーマ YAML を読み込む。読めなければ None。"""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    if yaml is None or not schema_path.exists():
        return None
    try:
        _SCHEMA_CACHE = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return _SCHEMA_CACHE


# 条件付き必須（schema の if-then 由来）。欠落プロパティ名 → 発生条件の説明。
# jsonschema の required 違反は allOf/then 経由で schema_path が複雑なため、
# 欠落プロパティ名ベースの簡易ヒントに留める（dml.schema.yaml の if-then と対応）。
_CONDITIONAL_REQUIRED = {
    "qry": "policy に bulk: true があるとき qry が必須です",
    "brs": "scenario に brMode があるとき brs が必須です",
}


def _format_error(err) -> str:
    """jsonschema のエラーを `scenarios/3/cmd: <message>` 形式に整形する。

    type 違反のときは「期待: array / 実際: str」のヒントを添える。
    配列の場所に文字列を渡した等（scenarios[].pol / queries[].sources など、キー名から
    型を推測しづらい非対称）を自己説明的にして書き直しの往復を減らす。
    required 違反が条件付き必須（bulk→qry 等）由来のときは発生条件を添える。
    """
    loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
    hint = ""
    if err.validator == "type":
        exp = err.validator_value
        exp = ", ".join(exp) if isinstance(exp, list) else exp
        hint = f"（期待: {exp} / 実際: {type(err.instance).__name__}）"
    elif err.validator == "required":
        missing = err.validator_value or []
        for prop in missing:
            if prop in _CONDITIONAL_REQUIRED and prop not in (err.instance or {}):
                hint = f"（ヒント: {_CONDITIONAL_REQUIRED[prop]}）"
                break
    return f"{loc}: {err.message}{hint}"


def validate_dml_text(dml_text: str, schema: dict | None = None) -> list[str]:
    """DML（YAML 文字列）を検証し、人間可読なエラー文字列のリストを返す。

    空 / None / 非 dict（コメントのみ）は違反なし扱いで [] を返す。
    依存やスキーマが無い場合も [] を返す（ツールチェーンを止めない）。
    """
    if yaml is None or Draft202012Validator is None:
        return []
    if not dml_text or not dml_text.strip():
        return []
    try:
        data = yaml.safe_load(dml_text)
    except yaml.YAMLError as e:
        return [f"YAML パースエラー: {e}"]
    if not isinstance(data, dict):
        return []  # コメントのみ等（進行中セッション）
    schema = schema if schema is not None else load_schema()
    if schema is None:
        return []
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: (list(e.absolute_path), e.message),
    )
    return [_format_error(e) for e in errors]


def validate_dml_file(path: Path | str, schema: dict | None = None) -> list[str]:
    """DML ファイルを検証する。存在しなければ [] を返す。"""
    p = Path(path)
    if not p.exists():
        return []
    return validate_dml_text(p.read_text(encoding="utf-8"), schema)


def main(argv: list[str]) -> int:
    if _IMPORT_ERROR is not None:
        print(f"⚠ DML 検証スキップ: 依存が見つかりません ({_IMPORT_ERROR})", file=sys.stderr)
        return 0
    if not argv:
        print("usage: validate_dml.py <path.dml.yaml> [<path> ...]", file=sys.stderr)
        return 2
    schema = load_schema()
    if schema is None:
        print(f"⚠ DML 検証スキップ: スキーマを読めません ({SCHEMA_PATH})", file=sys.stderr)
        return 0
    had_error = False
    for arg in argv:
        errs = validate_dml_file(arg, schema)
        if errs:
            had_error = True
            for e in errs:
                print(f"{arg}: {e}", file=sys.stderr)
        else:
            print(f"✅ {arg}: schema OK", file=sys.stderr)
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
