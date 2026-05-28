# 因果整合性サブエージェント起動プロンプト（観点別フィルタ → LLM 方式）

ユーザーが「フロー整合性チェック」「因果チェーンチェック」「causal check」を求めたら以下を実行する。

---

## ステップ 1 — 構造チェック（LLM 不要）

```bash
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=flow_step_resolution
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=unknown_evt_in_policy
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=dangling_cmd
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=state_reachability
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=orphan_event
```

違反があれば DML を修正してから次へ（意味判定のノイズを減らす）。

---

## ステップ 2 — 意味チェック Agent 起動

```
Agent(
  description: "DML因果整合性検査",
  prompt: """
EventStorming セッションの因果連鎖の業務的整合性を検査してください。

1. `python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py view \
   <session>.dml.yaml --view=flow-causality` を Bash で実行し、フロー全件スライスを取得
2. 同コマンドで `--view=policies` も取得
3. `.claude/skills/eventstorming-facilitator/references/checks/causal-chain-completeness.md` を Read
4. `.claude/skills/eventstorming-facilitator/references/checks/saga-completeness.md` を Read
5. 各 .md の「LLM へのプロンプト」と「出力フォーマット」に従い、それぞれ評価
6. 評価結果をマージし、業務的に途切れている箇所・補償フローが必要な箇所を
   **ビジネス言語**（CMD/POLICY/TRIGGER などの技術用語を使わない）で列挙する
"""
)
```

---

## ステップ 3 — 所見を questions[] に昇格

Agent の所見のうち、業務判断が必要なものは `questions[]` に追加する：

```bash
python3 scripts/dmlctl.py add <session>.dml.yaml --to=questions --item='
  id: Q13
  topic: "<業務的に未解決な事項>"
  why: "<決まると何が変わるか>"
  status: open
'
```

`### 因果チェーン（自動検出）` セクションは廃止。`questions[]` に直接追記し、HTML §5 に反映する。
**技術用語（CMD / POLICY / TRIGGER / SCENARIO 等）を使わず、ビジネス言語で書くこと**。

---

## 結果報告

ファシリテーター本体への返答：

- 問題なし: 「因果チェック完了：問題なし」
- 問題あり: 追加した Q 番号と要約（1 行）
