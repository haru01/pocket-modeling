# scenario-rules-quality

シナリオの `rules[]` / `errs[]` が **業務語彙で正しく書かれているか** を LLM で評価する観点。

## 抽出条件

事前に DML から該当スライスを取得する：

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=scenarios [--ctx <bc-name>]
```

返り値の `scenarios[]` の各要素を 1 件ずつ評価対象とする。LLM へは **rules[] / errs[] を持つ scenario のみ**
を抽出して渡す（rules/errs 空のものはチェック対象外）。

## LLM へのプロンプト

```
あなたは DDD と EventStorming のレビュアーです。以下の scenario の rules[] と errs[] を読み、
業務語彙として適切かを評価してください。

評価観点:
1. rule は **不変条件**（CMD 実行可能性の事前条件・状態遷移後の事後条件）になっているか。
   実装詳細（SQL / API / DB 制約）ではなく、業務ルールとして読めるか。
2. err.cond は **業務的に意味のある違反条件** になっているか。`null check failed` のような
   実装エラーではなく、`Quote already consumed`（業務状態の違反）になっているか。
3. err.err は PascalCase の業務エラー名（CamelCase / 業務用語）になっているか。
4. rule.why と err.when が省略されている場合、補強の余地があるか提案する。

入力 scenario (YAML):
{{scenario_yaml}}

出力フォーマット:
[
  {
    "scenario": "<scenario.name>",
    "verdict": "ok" | "needs-revision" | "critical",
    "findings": [
      { "kind": "rule"|"err", "index": N, "issue": "<日本語の指摘>", "suggestion": "<日本語の改善案>" }
    ]
  }
]
```

## 期待される所見

- ✅ 合格: `rule: Quote must be in CALCULATED state when consumed`、`err.cond: Quote already consumed`
- ❌ 不合格例:
  - `rule: SELECT * FROM quotes WHERE id = ?`（実装詳細）
  - `err.cond: pointer is null`（実装エラー）
  - `err.err: ERR_001`（業務用語でない）
- 補強推奨: `why` 不在の rule、`when` 不在の err

## 根拠となるルール（正典は playbook §3）

rule=不変条件か・err=業務エラーか（実装エラー除外）・`errs[]` に `why` は無く `when` に書く、
の各ルールの**正典は [`../ddd-playbook.md`](../ddd-playbook.md) §3 不変条件・エラー**。
業務エラー vs 実装エラーの判別表（スケジューラ誤発火・null pointer・API タイムアウト・並行制御の衝突を
除外する基準）と NG/OK の書き換え例も playbook §3 にある。本観点の LLM は、その基準に照らして
実際の rules/errs が業務語彙になっているかを評価する。

## 連携する構造チェック

- 先に `dmlctl check <file> --check=dangling_cmd` で参照整合性を確認すること
- 命名規約（PascalCase）違反は JSON Schema 検証が拾うため、ここでは扱わない
- `err_name_quality` — 観点 3 のうち機械判定できる部分（数字入りコード風 / 1 語のみの汎用語）は
  構造チェックに降格済み。LLM は業務語彙としての適切さ（観点 1・2・4）に集中する
