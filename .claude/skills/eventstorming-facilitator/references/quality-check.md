# DML 品質チェック（観点別フィルタ → LLM 方式）

DML 品質チェックは **2 段階**で行う：

1. **構造チェック（Python のみ）** — `dmlctl check <file> --all` で全観点を一括判定（参照整合性・
   命名・到達可能性）。個別に見るときは `--check=<name>`。LLM は使わない。
2. **意味チェック（観点別フィルタ + LLM）** — `dmlctl view <file> --view=<name>` で必要な
   スライスだけを切り出し、それを `references/checks/<name>.md` のプロンプトで LLM に渡す。

旧運用（DML 全文を 1 件の LLM に投げる）は **廃止**。LLM コンテキスト圧迫と再現性低下のため。

---

## 構造チェック観点（dmlctl check）

| `--check=<name>` | 何を検出するか | 修正先 |
|---|---|---|
| `orphan_agg` | どの scenario からも参照されない AGG | scenarios[].agg を追記 / 不要なら AGG 削除 |
| `dangling_cmd` | `aggregates[].transitions[].via` が scenarios[].cmd に未宣言 | scenarios を追加するか transitions を修正 |
| `unknown_evt_in_policy` | `policies[].trg` / `policies[].trgs.evts` が aggregates[].events[].name に未宣言 | EVT 宣言を補強 |
| `language_coverage` | AGG/CMD/EVT/POL が contexts[].lang に未登録 | contexts[].lang に英→日辞書を追加 |
| `state_reachability` | aggregates[].states に到達可能な transitions が無い状態（初期状態除く） | transitions を補強 |
| `orphan_event` | EVT 宣言済みだが scenarios/policies のいずれからも参照されない | 削除 or 参照追加 |
| `flow_chain_resolution` | `narratives[].entry` / `scenarios[].next` / `brs[].terminal` の参照が解決できない | typo 修正・narratives[].id の存在確認 |
| `narrative_entry_consistency` | 複数 narrative が同一 entry を共有するのに next が dict 分岐していない | scenarios[].next を narrative.id キーの dict に |
| `narrative_happy_unique` | `kind: happy` の narrative が 2 件以上 | happy は 1 本に統合 |
| `dangling_lang_entry` | lang に登録された名前の実体が本体モデルに無い（typo / リネーム漏れ） | lang か本体を修正 |
| `cross_bc_state_name_collision` | 複数 AGG で同名 state が lang.states のラベルで差別化されていない | lang.states を BC ごとに書き分け |
| `question_decision_link` | closed question の `decision_id` が decisions[].id に存在しない | リンク修正 |
| `agg_purpose_minlength` | aggregates[].purpose が欠落 or 30 字未満 | 「何を保証する集約か」を 30 字以上で言語化 |
| `decision_chosen_adopted` | `chosen` と `options[].adopted: true` の不整合（不在 / 0 件 / 複数 / 不一致） | chosen と adopted を対で修正 |
| `decision_affects_presence` | decisions[].affects が欠落 / 空 | 影響を受ける AGG / Policy / BC を記載 |
| `err_name_quality` | errs[].err が数字入りコード風 or 1 語のみの汎用語 | 業務語彙の複合語エラー名に |
| `bc_vocabulary_collision` | lang 辞書の同名異義（同 EN 別ラベル）/ 異名同義（同ラベル別 EN） | 識別子統一 or note で Conformist/ACL 明示 |
| `crud_cmd_naming` | CMD が CRUD 風接頭辞（Create/Add/Update/Delete/Get/Set 等） | 業務行為の動詞に言い換え |
| `subdomain_classification` | コアドメイン蒸留の未実施（domains[].subs 未定義・contexts[].sub 未設定/参照切れ・CORE 0 件・全件 CORE） | domains[].subs に CORE/SUPPORTING/GENERIC を定義し contexts[].sub で割り当て |

実行例：

```bash
python3 scripts/dmlctl.py check docs/eventstorming/<session>.dml.yaml --all         # 全観点を一括
python3 scripts/dmlctl.py check docs/eventstorming/<session>.dml.yaml --check=orphan_agg  # 個別観点
python3 scripts/dmlctl.py checks  # 観点名の一覧
```

個別チェックは JSON で `{ "check": ..., "count": N, "findings": [...] }` を stdout に出す。
`--all` は `{ "mode": "all", "checks_run", "checks_with_findings", "total_findings", "clean": [...], "results": [...] }`
（違反ゼロの観点は `clean` に名前だけ、違反ありは `results` に詳細）。
exit code はいずれも違反 0 件＝0、それ以外＝1。

---

## 意味チェック観点（観点別フィルタ → LLM）

`references/checks/<name>.md` を 1 観点 1 ファイルで持つ。各 .md は次を含む：

- 抽出条件（呼ぶべき `dmlctl view --view=<...>` コマンド）
- LLM へのプロンプト（評価観点・出力フォーマット）
- 期待される所見（合格 / 不合格の具体例）

現在の観点一覧：

| 観点ファイル | 評価対象 | 対応する dmlctl view |
|---|---|---|
| `checks/scenario-rules-quality.md` | rules/errs の業務語彙適切性 | `scenarios` |
| `checks/saga-completeness.md` | POLICY 連鎖と Saga 完結性 | `flow-causality`（brs 分岐・sidetracks 込み）+ `policies` |
| `checks/bc-vocabulary-consistency.md` | BC 間の同義語/異義語 | `bc-language` |
| `checks/agg-purpose-quality.md` | AGG の purpose 30 字以上・単一責任 | `agg-detail` |
| `checks/causal-chain-completeness.md` | フローの因果連鎖の途切れ | `flow-causality`（brs 分岐・sidetracks 込み） |
| `checks/decision-rationale-clarity.md` | 意思決定の why/why_not の明瞭さ | `decisions` |

実行手順：

1. 構造チェックを先に走らせて違反 0 にする（意味チェックが誤判定するのを防ぐ）
2. Agent tool で 1 観点ずつ起動。Agent への入力は **`dmlctl view` の出力 + 当該 .md の指示**
3. Agent の返した所見を AI / 人間が確認し、修正が必要なら DML を編集（`dmlctl set/add/remove` 経由）

---

## チェック起動の標準フロー

```bash
# 1) 構造チェック（全観点を一括実行。違反があれば exit 1 + results に詳細）
python3 scripts/dmlctl.py check <session>.dml.yaml --all

# 2) 意味チェック（Agent 起動）— quality-check-agent.md / causal-check-agent.md 参照
```

意味チェック起動の詳細は `quality-check-agent.md` を参照。
