# bc-vocabulary-consistency

複数の BC で **同じ業務概念に異なる名前** が当てられていないか、または **異なる概念に同じ名前** が
当てられていないかを LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=bc-language
```

全 BC の `lang` 辞書（カテゴリ別 EN→JP 対応）を取得。

## LLM へのプロンプト

```
あなたは Ubiquitous Language を整える DDD レビュアーです。以下の各 BC の lang 辞書を読み、
語彙の一貫性を評価してください。

評価観点:
1. **異名同義**: 同じ日本語ラベルが複数 BC で異なる英語識別子に対応していないか
   （例: `注文` が store-front では `Order` だが trade-in では `Purchase` になっているなど）
2. **同名異義**: 同じ英語識別子が複数 BC で異なる日本語ラベルに対応していないか
   （Conformist や Anti-Corruption Layer が必要なら note 推奨）
3. **業務語彙の質**: 英語識別子が業務語彙として自然か（CRUD 風の Add/Update/Delete ではないか）

入力（BC 毎の lang 辞書）:
{{bc_language_yaml}}

出力フォーマット:
[
  {
    "kind": "synonym" | "homonym" | "naming",
    "identifier": "<英語識別子 or 日本語ラベル>",
    "ctxs": ["<bc-1>", "<bc-2>"],
    "issue": "<日本語で何が問題か>",
    "suggestion": "<日本語で改善案>"
  }
]
```

## 期待される所見

- ✅ 異名同義の正当例: store-front `Order` / trade-in `TradeIn` — 別概念なので OK
- ❌ 異名同義の不正例: 両 BC が「注文」を扱うのに `Order` / `Purchase` で分かれている
- ⚠ 同名異義: `Quote` が store-front では「概算見積」、別 BC では「引用」になっているなど

## 連携する構造チェック

- `language_coverage` — まず未登録識別子を解決
