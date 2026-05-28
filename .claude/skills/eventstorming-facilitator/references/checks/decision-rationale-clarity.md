# decision-rationale-clarity

意思決定ログの `options[].why` / `why_not` が **判断根拠として明瞭か** を LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=decisions
```

`decisions[]` 全件を取得（数が少ないので全件処理が現実的）。

## LLM へのプロンプト

```
あなたは設計判断のレビュアーです。以下の各 decision を読み、採用 / 不採用理由が将来の読者
（半年後の自分・新メンバー・監査人）に判断根拠として十分伝わるかを評価してください。

評価観点:
1. **chosen の why が "業務制約" または "トレードオフ" の言語化** になっているか
   （「採用したから」「OK だったから」のような循環的説明でないか）
2. **棄却 option の why_not が、その option を選んだ場合の具体的なデメリット** を語っているか
   （「不適切」だけでなく、何が起きるか）
3. **affects[]** に影響範囲が記載されているか（AGG / BC / シナリオへの波及）
4. **chosen と options[].adopted: true** が整合しているか

入力 (YAML):
{{decisions_yaml}}

出力フォーマット:
[
  {
    "id": "<D{n}>",
    "verdict": "clear" | "vague" | "incomplete",
    "issues": [
      { "field": "why"|"why_not"|"affects", "option": "<option.name>", "issue": "<指摘>", "suggestion": "<改善案>" }
    ]
  }
]
```

## 期待される所見

- ✅ clear: `why: タイムアウト 10 日は与信有効期限内に査定確定する業務制約に基づく`
- ⚠ vague: `why_not: 適切でない` — 何が起きるか語っていない
- ❌ incomplete: `affects: []` — 採用判断の影響範囲が不明

## 連携する構造チェック

- `question_decision_link` — closed question の decision_id 参照を先に確認
