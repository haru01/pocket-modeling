"""DML 観点別フィルタ群（view と check）。

`dmlctl.py` から呼び出される。各関数は yaml.safe_load 済みの model（dict）を入力に取り、
LLM への入力サイズを最小化するために必要な観点だけを切り出す。

- views.py — `dmlctl view --view=<name>` 用。観点別 YAML スライスを返す。
- checks.py — `dmlctl check --check=<name>` 用。構造チェックを実行し違反一覧を返す。
"""
