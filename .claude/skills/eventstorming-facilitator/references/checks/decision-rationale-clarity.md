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

## `affects[]` の粒度ガイドライン

スキーマは `affects[]` を自由文字列リストとしてしか定義していないが、レビュー時の参照
可能性を保つため以下の粒度を推奨：

| 必須 | AGG 名（PascalCase） | 必ず含める |
|---|---|---|
| 推奨 | Policy 名（PascalCase） | 決定が EVENTUAL-TX 連鎖に影響する場合 |
| 任意 | Event 名（PascalCase） | 決定が特定 evt の発火条件に影響する場合 |
| 任意 | BC 名（lowercase-with-hyphen） | 決定が BC 境界・依存方向に影響する場合 |

書き方の規範:
- ❌ `affects: [Event]` のみ — Policy 連鎖が影響を受けるなら抜けがある
- ❌ `affects: [Attendance, ParticipantCheckedIn]` — Event は粒度が低すぎる（Policy / BC は本当に無関係か？）
- ✅ `affects: [Participation, PromoteOnCancelled, NotifyParticipantsOnEventCancelled]` — AGG + 影響を受ける Policy
- ✅ `affects: [Event, participation]` — AGG + 関係する BC（依存方向に影響する決定）

複数 decision で粒度が揃わない場合は LLM レビューで `incomplete` 判定にする。

## ストローマン論法を避ける

`why_not` で同じ文言を複数 decision に使い回している場合、選択肢の固有性を語れていない
可能性が高い。例: 「主催者の運営負荷を増やす（本サービスの目的に逆行）」が D2 と D4 の
別オプションで重複していたら、各オプションの **固有の不利点**（公平性論争・選定基準の
説明責任・例外対応コスト等）に書き換える。

## 連携する構造チェック

- `question_decision_link` — closed question の decision_id 参照を先に確認
- `decision_chosen_adopted` — 観点 4（chosen ⇔ adopted: true の整合）は構造チェックに降格済み
- `decision_affects_presence` — 観点 3 のうち affects[] の有無判定は構造チェックに降格済み
  （粒度の適切さ＝Policy 連鎖の漏れ等は引き続き本観点＝LLM の責務）
