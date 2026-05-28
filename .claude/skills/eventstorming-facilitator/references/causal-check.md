# DML フロー因果整合性チェック（観点別フィルタ → LLM 方式）

DML（`<session>.dml.yaml`）の `scs` / `pols` / `flows` のつながりを辿り、**因果連鎖の切れ・
孤立・循環** を検出する。`quality-check.md` と同じ「構造→意味」の 2 段階を踏む。

---

## 構造チェック（Python のみ）

| `--check=<name>` | 何を検出するか |
|---|---|
| `flow_step_resolution` | `flows[].steps[]` が scs/pols に解決できない（typo / 未追加） |
| `unknown_evt_in_policy` | `pols[].trg` / `pols[].trgs.evts` の EVT が宣言されていない |
| `dangling_cmd` | `aggs[].transitions[].via` が scs[].cmd に未宣言 |
| `state_reachability` | aggs[].states に到達可能な transitions が無い状態 |
| `orphan_event` | EVT 宣言済みだが scs/pols のどこからも参照されない |

実行：

```bash
python3 scripts/dmlctl.py check <session>.dml.yaml --check=flow_step_resolution
python3 scripts/dmlctl.py check <session>.dml.yaml --check=unknown_evt_in_policy
```

これらが 0 件になってから意味チェックを走らせる（ノイズを減らすため）。

---

## 意味チェック（観点別フィルタ → LLM）

因果整合性に特化した観点：

| 観点ファイル | 評価対象 |
|---|---|
| `checks/causal-chain-completeness.md` | flows[] のステップ間で業務的な飛躍がないか |
| `checks/saga-completeness.md` | POLICY 連鎖の Saga が完結しているか・補償フロー有無 |

呼び出しは `causal-check-agent.md` の Agent 起動フローに従う。

---

## ステップ別の対応（旧 C 系チェックとの対応）

| 旧 ID | 旧チェック内容 | 新方式での対応 |
|---|---|---|
| C1 | scs[].agg が aggs[] に宣言されているか | `dangling_cmd` + `orphan_agg` |
| C2 | scs[].cmd が aggs[].transitions[].via と整合 | `dangling_cmd` |
| C3 | scs[].evt が aggs[].events[] に宣言されているか | `unknown_evt_in_policy` + `orphan_event` |
| C4 | pols[].trg が EVT として宣言されているか | `unknown_evt_in_policy` |
| C5 | flows[].steps[] が scs/pols に解決できるか | `flow_step_resolution` |
| C6 | フローの因果連鎖に飛躍がないか | `causal-chain-completeness.md`（LLM） |
| C7 | Saga / 補償フローの完結性 | `saga-completeness.md`（LLM） |
| C8 | aggs[].states の到達可能性 | `state_reachability` |
| C9 | Quote/Order の初期状態生成 transitions の明示 | `state_reachability`（要 LLM 補強） |

---

## なぜ 2 段階に分けたか

- 構造は **再現性高く・低コストで** 検出できる（Python の論理判定で十分）
- 意味は **LLM の業務文脈理解** が必要だが、全 YAML を渡すとコンテキストが圧迫されノイズが多い
- 観点別に最小スライスを切り出すことで、**LLM の判定精度と再現性** を保ちつつ context を節約する
