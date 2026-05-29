# saga-completeness

EVENTUAL-TX（POLICY 連鎖）の **Saga が業務的に完結しているか** を LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=flow-causality
```

すべての `narratives[]`（entry 付き）から派生する各フローと、各ステップに紐づく scenarios/policies の cmd/evt/trg/ctx を抽出したスライスを取得。

補助的に、`dmlctl view --view=policies` も評価対象に追加すると POL チェーンの全貌が見える。

## LLM へのプロンプト

```
あなたは Saga パターンに精通した DDD レビュアーです。以下のフロー（時系列の steps）と
policies を読み、各フローの **Saga が完結しているか** を評価してください。

「Saga が完結している」とは:
1. ハッピーパスの flow は **最終的な業務イベント** で終端する（例: 注文完了 / 配送完了）
2. 代替シナリオの flow は **業務的にも処理が止まっていい状態**（中断 / 補償完了）で終端する
3. POLICY 連鎖の途中で **オーバーラップ・抜け** がない（同じ EVT で複数 POLICY が起動する場合、
   業務的に独立しているか・併発で問題ないかを検証）
4. **補償 transactions** が定義されているか（例: タイムアウト時の与信解放）

入力 (YAML):
{{flow_causality_yaml}}
{{policies_yaml}}

出力フォーマット:
[
  {
    "flow": "<flow.id>",
    "verdict": "complete" | "open-ended" | "broken",
    "terminus": "<最後の業務イベント or 業務的に未完結な理由>",
    "compensation_gaps": ["<不足している補償フローの説明>"],
    "policy_overlaps": ["<競合しうる POLICY 起動の説明>"]
  }
]
```

## 期待される所見

- ✅ complete: happy フロー終端が `配送業者が新品を届ける` 等の業務終端 EVT
- ⚠ open-ended: 代替フローが POLICY 起動で終わっているが、最終的な業務状態（cancelled / refunded）の宣言が無い
- ❌ broken: 中間の POLICY 連鎖でトリガー EVT が宣言されていない（先に `unknown_evt_in_policy` 検出済みのケース）

## 連携する構造チェック

- `flow_chain_resolution` — 解決できない next / terminal を排除してから本観点を実行
- `unknown_evt_in_policy` — 未宣言トリガーが残っているとここで誤判定するので先に修正

## POLICY のガード条件はどこに書くか

policy schema には `rules[]` が無い（v8 時点）。「この POLICY を skip するべき業務条件」は、
**policy の `note` に簡潔に書きつつ、policy が起動する CMD を実行する SCENARIO の `rules[]` /
`errs[]` にガードを書く**。

典型的な暴発リスク:
- `bulk:true` の POLICY が cascade 発火するとき、後続 POLICY を意図せず起動する
  - 例: `NotifyParticipantsOnEventCancelled` (bulk Cancel) → `ParticipationCancelled` evt 連発
    → `PromoteOnCancelled` が「次の WAITLISTED を繰上」しようとする
    → しかし Event 自体が CANCELLED なので業務矛盾

書き方:
```yaml
policies:
  - name: NotifyParticipantsOnEventCancelled
    note: bulk Cancel が PromoteOnCancelled を連鎖発火しないよう、繰上 scenario 側に EventAlreadyCancelled ガード

scenarios:
  - name: システムが繰上を実行する
    cmd: PromoteFromWaitlist
    rules:
      - { rule: Skip promotion when Event itself is CANCELLED, why: alt-cancel フロー連鎖中の暴発防止 }
    errs:
      - { cond: 対応する Event が CANCELLED, err: EventAlreadyCancelled, when: alt-cancel 連鎖中の繰上試行 }
```

LLM レビューでは「`bulk:true` policy が連鎖させる evt が、他 policy の trg と一致する」ケースで
ガード rule/errs の有無を必ず確認する。
