# saga-completeness

EVENTUAL-TX（POLICY 連鎖）の **Saga が業務的に完結しているか** を LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=flow-causality
```

すべての `flows[]` と、各ステップに紐づく scs/pols の cmd/evt/trg/ctx を抽出した
スライスを取得。

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

- `flow_step_resolution` — 解決できない step を排除してから本観点を実行
- `unknown_evt_in_policy` — 未宣言トリガーが残っているとここで誤判定するので先に修正
