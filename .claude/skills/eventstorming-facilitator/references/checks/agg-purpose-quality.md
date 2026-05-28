# agg-purpose-quality

AGG の `purpose` が **単一責任で 30 字以上の業務言語** で書かれているかを LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=agg-detail [--name <AggName>]
```

`--name` 省略時は全 AGG を返す。1 件ずつ評価する。

## LLM へのプロンプト

```
あなたは DDD の戦術的設計レビュアーです。以下の AGG の purpose / background / constraints を
読み、単一責任の明確化として十分な記述か評価してください。

評価観点:
1. **purpose は 30 字以上か**（短すぎないか）
2. **単一責任の言語化** になっているか（複数の責務が混在していないか）
3. **業務語彙** で書かれているか（実装詳細・データモデル詳細ではないか）
4. **background が WHY** を答えているか（「なぜ今この AGG を切り出すか」が伝わるか）
5. **constraints が業務 / 法令 / プラットフォームの制約** であり、技術スタック制約に偏っていないか

入力 (YAML):
{{agg_detail_yaml}}

出力フォーマット:
[
  {
    "agg": "<AggName>",
    "purpose_len": N,
    "verdict": "ok" | "needs-revision" | "critical",
    "issues": [
      { "field": "purpose"|"background"|"constraints", "issue": "<指摘>", "suggestion": "<改善案>" }
    ]
  }
]
```

## 期待される所見

- ✅ 合格: `purpose: 旧機種の引き受けから売買成立まで状態を所有し、各遷移の根拠を法令準拠で明示する`
- ❌ 不合格例:
  - `purpose: 下取を扱う`（短すぎる・単一責任が見えない）
  - `purpose: テーブル trade_in を CRUD する`（実装詳細）
  - `background:` 空 — WHY が不明
  - `constraints: PostgreSQL を使う`（業務制約ではない）

## 連携する構造チェック

- なし（純粋に LLM による意味評価）
