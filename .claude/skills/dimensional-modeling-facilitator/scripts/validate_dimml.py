#!/usr/bin/env python3
"""DimML (.dimml.yaml) を JSON Schema (references/dimml.schema.yaml) で検証する。

- `validate_dimml_text(text)` / `validate_dimml_file(path)` は **人間可読なエラー文字列のリスト**を
  返す（空リスト = 違反なし）。`dimml_build.py` から import して「警告のみ（non-blocking）」で使う。
- CLI（`python3 validate_dimml.py <path.dimml.yaml> ...`）は違反一覧を stderr に出し、
  違反があれば exit code 1 を返す（CI ゲート用）。

構文検証（JSON Schema）に加え、軽量な参照整合チェックを行う:
  - facts[].dims[].dimension / decisions[].affects が実在の dimension/fact を指すか
  - facts[].process が実在の process を指すか
  - decisions[].chosen が options[].name のいずれかと一致し、その option が adopted か
これらは「意味 validity」のごく一部。グレインの明確さ・conformed dimension の整合など
本格的な意味チェックは dimensional-playbook.md の検証観点＋ LLM レビューが担う。

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

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "dimml.schema.yaml"

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


def _format_error(err) -> str:
    """jsonschema のエラーを `facts/2/grain: <message>` 形式に整形する。

    type 違反のときは「期待: array / 実際: str」のヒントを添え、書き直しの往復を減らす。
    """
    loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
    hint = ""
    if err.validator == "type":
        exp = err.validator_value
        exp = ", ".join(exp) if isinstance(exp, list) else exp
        hint = f"（期待: {exp} / 実際: {type(err.instance).__name__}）"
    elif err.validator == "enum":
        hint = f"（許可値: {', '.join(map(str, err.validator_value))}）"
    return f"{loc}: {err.message}{hint}"


def _reference_checks(data: dict) -> list[str]:
    """スキーマでは表せない軽量な参照整合チェック。違反文字列のリストを返す。"""
    out: list[str] = []
    dim_names = {d.get("name") for d in (data.get("dimensions") or []) if isinstance(d, dict)}
    fact_names = {f.get("name") for f in (data.get("facts") or []) if isinstance(f, dict)}
    proc_names = {p.get("name") for p in (data.get("processes") or []) if isinstance(p, dict)}

    for i, f in enumerate(data.get("facts") or []):
        if not isinstance(f, dict):
            continue
        proc = f.get("process")
        if proc and proc not in proc_names:
            out.append(f"facts/{i}/process: 未定義の process '{proc}'（processes[] に無い）")
        for j, d in enumerate(f.get("dims") or []):
            if isinstance(d, dict):
                dn = d.get("dimension")
                if dn and dn not in dim_names:
                    out.append(
                        f"facts/{i}/dims/{j}/dimension: 未定義の dimension '{dn}'（dimensions[] に無い）"
                    )

    for i, dec in enumerate(data.get("decisions") or []):
        if not isinstance(dec, dict):
            continue
        opts = dec.get("options") or []
        names = {o.get("name") for o in opts if isinstance(o, dict)}
        chosen = dec.get("chosen")
        if chosen is not None and chosen not in names:
            out.append(
                f"decisions/{i}/chosen: '{chosen}' が options[].name に一致しません（{', '.join(map(str, names))}）"
            )
        else:
            for o in opts:
                if isinstance(o, dict) and o.get("name") == chosen and not o.get("adopted"):
                    out.append(
                        f"decisions/{i}: chosen '{chosen}' の option に adopted: true がありません"
                    )
        for k, aff in enumerate(dec.get("affects") or []):
            if aff not in dim_names and aff not in fact_names:
                out.append(
                    f"decisions/{i}/affects/{k}: '{aff}' が fact/dimension 名に一致しません"
                )
    return out


def validate_dimml_text(dimml_text: str, schema: dict | None = None) -> list[str]:
    """DimML（YAML 文字列）を検証し、人間可読なエラー文字列のリストを返す。

    空 / None / 非 dict（コメントのみ）は違反なし扱いで [] を返す。
    依存やスキーマが無い場合も [] を返す（ツールチェーンを止めない）。
    """
    if yaml is None or Draft202012Validator is None:
        return []
    if not dimml_text or not dimml_text.strip():
        return []
    try:
        data = yaml.safe_load(dimml_text)
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
    out = [_format_error(e) for e in errors]
    # 構文が通っている場合のみ参照整合チェックを足す（型崩れ時の二重報告を避ける）
    if not out:
        out.extend(_reference_checks(data))
    return out


def validate_dimml_file(path: Path | str, schema: dict | None = None) -> list[str]:
    """DimML ファイルを検証する。存在しなければ [] を返す。"""
    p = Path(path)
    if not p.exists():
        return []
    return validate_dimml_text(p.read_text(encoding="utf-8"), schema)


def main(argv: list[str]) -> int:
    if _IMPORT_ERROR is not None:
        print(f"⚠ DimML 検証スキップ: 依存が見つかりません ({_IMPORT_ERROR})", file=sys.stderr)
        return 0
    if not argv:
        print("usage: validate_dimml.py <path.dimml.yaml> [<path> ...]", file=sys.stderr)
        return 2
    schema = load_schema()
    if schema is None:
        print(f"⚠ DimML 検証スキップ: スキーマを読めません ({SCHEMA_PATH})", file=sys.stderr)
        return 0
    had_error = False
    for arg in argv:
        errs = validate_dimml_file(arg, schema)
        if errs:
            had_error = True
            for e in errs:
                print(f"{arg}: {e}", file=sys.stderr)
        else:
            print(f"✅ {arg}: schema OK", file=sys.stderr)
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
