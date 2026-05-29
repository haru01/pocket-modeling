# 品質チェックサブエージェント起動プロンプト（観点別フィルタ → LLM 方式）

`.dml.yaml` を編集したら以下の順序でチェックを走らせる。**全文を LLM に渡さない**：
構造チェックは Python、意味チェックは観点別フィルタで切り出した最小スライスのみ。

---

## ステップ 1 — 構造チェック（LLM 不要）

```bash
python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py <session>.dml.yaml

for c in orphan_agg dangling_cmd unknown_evt_in_policy language_coverage \
         state_reachability orphan_event flow_chain_resolution \
         narrative_entry_consistency question_decision_link; do
    python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <session>.dml.yaml --check=$c
done
```

違反があれば対応する DML フィールドを `dmlctl set/add/remove` で修正してから次へ。

---

## ステップ 2 — 意味チェック（観点別 Agent 起動）

意味観点ごとに 1 件ずつ Agent を起動する。例：`scenario-rules-quality.md` の場合：

```
Agent(
  description: "EventStorming意味チェック (scenario-rules-quality)",
  prompt: """
以下の手順で評価してください。

1. `python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py view \
   <session>.dml.yaml --view=scenarios` を Bash で実行し、scenarios[] スライスを得る
2. `.claude/skills/eventstorming-facilitator/references/checks/scenario-rules-quality.md` を Read
3. 同 .md の「LLM へのプロンプト」と「出力フォーマット」に従って、上記 1 のスライスを評価
4. 出力フォーマットに沿った JSON で所見を返す
"""
)
```

ステップ 3 で観点 .md を差し替えれば、他観点（`saga-completeness` / `agg-purpose-quality` 等）
にも同じパターンで適用できる。

---

## ステップ 3 — 所見への対応

各 Agent が返した所見を受けて：

- **`verdict: ok` / `complete` / `clear`** — 何もしない
- **`needs-revision` / `gap` / `vague`** — 該当 DML 要素を `dmlctl set/add/remove` で修正
- **`critical` / `broken` / `incomplete`** — チャットに ホットスポット候補として列挙し、ユーザーに 1 問 1 答で確認

ホットスポットの提示フォーマット例：

```
### 意味チェック所見
[scenario-rules-quality]
- [?] scenarios「会員が下取をキャンセルする」 — rule に why 不足。
      推奨: why: "...（業務文脈で言語化）"

[saga-completeness]
- [?] flow `alt-significant-reduction` — open-ended (社内承認後の終端 EVT が無い)
      推奨: SupervisorApprovalGranted を追加し scenarios[].next 連鎖の末尾につなぐ
```

---

## 意味チェック観点と対応 view の早見表

| 観点（Agent に渡す .md） | 取得すべき view |
|---|---|
| `checks/scenario-rules-quality.md` | `dmlctl view --view=scenarios [--ctx <bc>]` |
| `checks/saga-completeness.md` | `dmlctl view --view=flow-causality` + `--view=policies` |
| `checks/bc-vocabulary-consistency.md` | `dmlctl view --view=bc-language` |
| `checks/agg-purpose-quality.md` | `dmlctl view --view=agg-detail [--name <AggName>]` |
| `checks/causal-chain-completeness.md` | `dmlctl view --view=flow-causality [--id <flow-id>]` |
| `checks/decision-rationale-clarity.md` | `dmlctl view --view=decisions` |

---

## なぜ全文を渡さないか

- セッション成熟期の `.dml.yaml` は 40 KB 超になり、毎ターン全文を LLM に渡すと **コンテキストが圧迫** される
- LLM への入力が大きいほど **判定の再現性が落ちる**（前回 OK だった項目が今回 NG になるなど）
- 観点別フィルタで「何を評価するか」を絞ると、**LLM のフォーカスが鋭くなり所見の精度が向上** する
