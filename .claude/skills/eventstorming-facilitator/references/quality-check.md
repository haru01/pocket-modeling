# DML 品質チェック（観点別フィルタ → LLM 方式）

各チェックが根拠にする**モデリングルールの正典は [`ddd-playbook.md`](./ddd-playbook.md)**（DDD 概念軸）。
本書は「どの観点を構造/意味のどちらで検証するか」のカタログで、ルールそのものは playbook §各概念「検証観点」を参照。

DML 品質チェックは **2 段階**で行う：

1. **構造チェック（Python のみ）** — `dmlctl check <file> --all` で全観点を一括判定（参照整合性・
   命名・到達可能性）。個別に見るときは `--check=<name>`。LLM は使わない。
2. **意味チェック（観点別フィルタ + LLM）** — `dmlctl view <file> --view=<name>` で必要な
   スライスだけを切り出し、それを `references/checks/<name>.md` のプロンプトで Agent に渡す。

**DML 全文を LLM に渡さない**：成熟期の `.dml.yaml` は 40 KB 超になりコンテキストを圧迫するうえ、
入力が大きいほど判定の再現性が落ちる。構造は Python で再現性高く・低コストに検出し、
意味は観点別の最小スライスに絞ることで LLM のフォーカスと精度を保つ。

---

## 構造チェック観点（dmlctl check）

| `--check=<name>` | 何を検出するか | 修正先 |
|---|---|---|
| `orphan_agg` | どの scenario からも参照されない AGG | scenarios[].agg を追記 / 不要なら AGG 削除 |
| `dangling_cmd` | `aggregates[].transitions[].via` が scenarios[].cmd に未宣言 | scenarios を追加するか transitions を修正 |
| `unknown_evt_in_policy` | `policies[].trg` / `policies[].trgs.evts` が aggregates[].events[].name に未宣言 | EVT 宣言を補強 |
| `language_coverage` | AGG/CMD/EVT/POL が contexts[].lang に未登録 | contexts[].lang に英→日辞書を追加 |
| `state_reachability` | aggregates[].states に到達可能な transitions が無い状態（初期状態除く） | transitions を補強 |
| `orphan_event` | EVT 宣言済みだが scenarios/policies のいずれからも参照されない | 削除 or 参照追加（意図的な終端 EVT は `events[].terminal: true` で除外） |
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

`references/checks/<name>.md` を 1 観点 1 ファイルで持つ。各 .md は
抽出条件（呼ぶべき view）・LLM へのプロンプト・期待される所見（合格/不合格の具体例）を含む。

| 観点ファイル | 評価対象 | 取得すべき view |
|---|---|---|
| `checks/scenario-rules-quality.md` | rules/errs の業務語彙適切性 | `--view=scenarios [--ctx=<bc>]` |
| `checks/saga-completeness.md` | POLICY 連鎖と Saga 完結性 | `--view=flow-causality` + `--view=policies` |
| `checks/bc-vocabulary-consistency.md` | BC 間の同義語/異義語 | `--view=bc-language` |
| `checks/agg-purpose-quality.md` | AGG の purpose 30 字以上・単一責任 | `--view=agg-detail [--name=<AggName>]` |
| `checks/causal-chain-completeness.md` | フローの因果連鎖の途切れ | `--view=flow-causality [--id=<flow-id>]` |
| `checks/decision-rationale-clarity.md` | 意思決定の why/why_not の明瞭さ | `--view=decisions` |

---

## 標準フロー（書き出し後に必ず実行）

1. **構造チェック** — `dmlctl check <file> --all`。違反があれば `dmlctl set/add/remove` で修正して
   再走（意味チェックの誤判定ノイズを防ぐため、0 件にしてから次へ）
2. **意味チェック** — 観点ごとに Agent を 1 件ずつ起動。入力は **view スライス + 当該 .md の指示**：

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

観点 .md と view を差し替えれば他観点にも同じパターンで適用できる（上の早見表を参照）。

3. **所見への対応**：
   - `verdict: ok` / `complete` / `clear` — 何もしない
   - `needs-revision` / `gap` / `vague` — 該当 DML 要素を `dmlctl set/add/remove` で修正
   - `critical` / `broken` / `incomplete` — チャットにホットスポット候補として列挙し、ユーザーに 1 問 1 答で確認

ホットスポットの提示フォーマット例：

```
### 意味チェック所見
[scenario-rules-quality]
- [?] scenarios「会員が下取をキャンセルする」 — rule に why 不足。
      推奨: why: "...（業務文脈で言語化）"
```

---

## 因果チェック（フロー整合性のサブセット起動）

ユーザーが「フロー整合性チェック」「因果チェーンチェック」「causal check」を求めたら、
因果連鎖に関わる観点だけを抜き出して実行する：

1. **構造** — `--check=` で `flow_chain_resolution` / `unknown_evt_in_policy` / `dangling_cmd` /
   `state_reachability` / `orphan_event` の 5 観点（`--all` で代替可）。0 件にしてから次へ
2. **意味** — `checks/causal-chain-completeness.md` と `checks/saga-completeness.md` の 2 観点を
   1 Agent でまとめて起動してよい（view は `flow-causality` + `policies`）。所見は
   **ビジネス言語**（CMD / POLICY / TRIGGER 等の技術用語を使わない）で列挙させる
3. **questions[] への昇格** — 業務判断が必要な所見は `questions[]` に open で追加する：

```bash
python3 scripts/dmlctl.py add <session>.dml.yaml --to=questions \
  --item='{id: Q13, topic: "<業務的に未解決な事項>", why: "<決まると何が変わるか>", status: open}'
```

4. **結果報告** — ファシリテーター本体への返答は 1 行。
   問題なし:「因果チェック完了：問題なし」／問題あり: 追加した Q 番号と要約
