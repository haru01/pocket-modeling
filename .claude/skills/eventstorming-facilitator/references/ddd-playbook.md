# DDD / EventStorming モデリング プレイブック

DDD ドメインモデリングの**ルールの唯一の人間可読な正典**。「集約とは何で／どう書き／何が検証されるか」を概念ごとに 1 セクションで読み通せるように、定義・命名・設計判断・検証観点を横断集約する。

## 0. このプレイブックの役割と読み方

DML（Domain Modeling Language）に関するルールは 3 つの真実源に分かれる。本書は**人間可読なルールとその根拠**を所有し、機械の真実源へはリンクする（重複させない）：

| 何を | 真実源 | 本書の扱い |
|---|---|---|
| **構文 validity**（型・必須・enum・命名 pattern・排他制約） | [`dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12） | $def 名でリンク。pattern/enum の値は転記しない |
| **構造チェックの閾値・語彙**（AGG purpose 30 字、CRUD 接頭辞リスト等） | [`scripts/dml_filters/checks.py`](../scripts/dml_filters/checks.py) | チェック名でリンク。閾値は「§検証観点」で言及するが実体はコード |
| **モデリングルール・設計判断・慣習** | **本書** | 所有。旧 `dml-spec.md` と `term-glossary.md` の定義を統合 |

- **スキーマ通過は必要条件であって十分条件ではない**（§13）。「形が正しい」を schema が、「意味が正しい」を品質チェック（構造＋意味、[`quality-check.md`](./quality-check.md)）が担保する。
- 意味チェック 6 観点の LLM プロンプトと合否例は [`checks/*.md`](./checks/) が持つ。本書は各観点が根拠にするルールを定義し、`checks/*.md` はそこへ委譲する。
- 本書は**現行仕様のみ**を記述する（廃止済み概念 `flows[]` / `story` / `.md` 入力の履歴注記は書かない。履歴はルート `CLAUDE.md` に集約）。

各概念セクションは固定の 4 小見出しで統一する：**定義 / 命名・構文 / 設計判断ルール / 検証観点**。

---

## 1. 記法の原則（横断ルール）

すべての概念に共通する記法の土台。

- **YAML 直書き**: `docs/eventstorming/<session>.dml.yaml` に純 YAML（フェンス不要）で書く。ビルダーはこの 1 ファイルだけから HTML を生成する。コメントによるセクション区切りは使わない（リスト構造で自然に分離される）。
- **識別子は英語 PascalCase**（`cmd` / `evt` / `agg` / `trg` / `qry` の値、`aggregates[].name` 等）。`()` や `<<>>` は付けない。schema pattern は `#/$defs/pascalCase`。
- **`scenarios[].name` のみ日本語**で「アクター＋行為」を書く（例: `主催者がコミュニティを作成する`）。英語識別子だけだと「OrderConfirmFlow」のような形式名に逃げやすい。
- **BC 名は `lowercase-with-hyphen`**、略さずに書く。schema pattern は `#/$defs/contextName`。
- **AGG 状態名は UPPER_SNAKE**（schema pattern `#/$defs/upperSnake`）。属性名は camelCase。
- **日本語の補足は構造化フィールドへ**: `rules[].why` / `errs[].when` / `note` に書く（`#` 行コメントによる補足慣習は廃止）。
- **キー順の推奨**（`scenarios`）: `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`。
- **基本方針は「単数を表すキー＝文字列／複数を表すキー＝配列」**。例外（`queries[].users` は文字列だが `sources` は配列、`brs[].pol` と `transition.to` は単数/複数両方可の oneOf 等）は `dmlctl hint --path=<a.b.c>` が教える。

散文情報（`session` / `narratives[]` / `actions[]` / `questions[]` / `queries[]` / `contexts[].description`）もすべて DML 内のトップレベルフィールドとして保持する（別の `.md` は無い）。全フィールドが optional（空 `{}` も valid・進行中セッション許容）。

---

## 2. シナリオ (Scenario)

### 定義

アクター（人・システム）＋行為の 1 単位。「誰が何をして、どんな事実が起きたか」を EVT 起点で記述する。

### 命名・構文

- schema: `#/$defs/scenario`。必須 `[name, ctx, actor]`。`evt` と `brs` は同時指定禁止、`brMode` 単独指定禁止。
- `name` は日本語（§1）。`cmd` / `evt` / `agg` の値は PascalCase。`pol` は配列のみ。

### 設計判断ルール

- **なぜ EVT 起点か**: 「起きた事実」から始めることで、実装の都合（コマンドの存在・API の形）に引きずられず、ビジネスの本質的な流れを先に把握できる。
- **`actor` 必須**: コマンドを発行するアクターを明記する。典型値は `Organizer`（主催者）、`Member`（参加者）、`System`（システム/ポリシー）。`actor: System` は機械が起点であることを意味し、業務担当者が居ない自動処理を明示する慣習。
- **分岐（`brs`）の使い所**: コマンドの処理結果に応じて発火イベントが変わる場合、`evt` の代わりに `brs` で分岐を書く（同一トランザクション内の **SAME-TX** 分岐）。EVENTUAL-TX は `policies` で表現する（§6）。`brMode` の語彙（`exclusive` 既定 / `concurrent` / `inclusive`）は schema `#/$defs/branchMode` 参照。
- **内部 CMD（時刻駆動・コールバック・副作用）の書き方**: 業務アクターが直接発行しない CMD でも、AGG の状態を変える限り scenario として書くか policy.cmd として実体化する。

  | 類型 | 書き方 | 例 |
  |----|-------|----|
  | 時刻駆動（タイムアウト・失効） | BULK policy（`qry`・`cmd` 必須）＋ 対応する scenario（actor: System） | `DetectArrivalTimeoutWhenItemNotReceived` policy + `システムが未着タイムアウトを検出する` scenario |
  | 外部コールバック（決済結果通知等） | 結果を 2 値以上に分けるなら `brs` で SAME-TX 分岐、別トランザクションなら policy | ExecutePayout の brs に PayoutExecuted / PayoutFailed |
  | 内部副作用（再試行・補償・リカバリ） | 別 scenario（actor: System）。trigger 元は前 scenario の `brs[].next` か policy | `システムが入金をリトライする` |

### 検証観点

- 構造: `flow_chain_resolution`（`next`/`brs[].terminal` の解決）、`dangling_cmd`（`transitions[].via` と突合）。
- 意味: [`checks/scenario-rules-quality.md`](./checks/scenario-rules-quality.md)（rules/errs の業務語彙）、[`checks/causal-chain-completeness.md`](./checks/causal-chain-completeness.md)（因果連鎖）。

---

## 3. 不変条件・エラー (rules / errs)

### 定義

- **不変条件 / Invariant（`rules[].rule`）**: 集約が**常に**守るべき業務ルール。違反したら集約が壊れる（例: 「在庫数は 0 以上」）。CMD 実行の事前条件・状態遷移後の事後条件。
- **業務エラー / ERR（`errs[].err`）**: 不変条件違反や前提条件未充足で起きる業務エラー（例: `OutOfStock`）。

### 命名・構文

- schema: `rule` は `#/$defs/rule`（必須 `[rule]`、任意 `why` / `note`）、`error` は `#/$defs/error`（`cond` / `err` / 任意 `when`）。
- `rules[]` には `why` があるが **`errs[]` には `why` フィールドが無い**（非対称）。`why` を書くと schema が `Additional properties are not allowed ('why' was unexpected)` で弾く。
- `err.err` は PascalCase の業務エラー名（複合語）。

### 設計判断ルール

- **`rules[].why` の書き方（業務・UX 文脈への翻訳）**: `rule` をユーザー影響・業務文脈に翻訳する。`rule` の言い換えは情報が増えないので NG。
  - NG: `why: "name の一意性を保つため"`（rule の言い換え）
  - OK: `why: "URL slug や検索 UX で name→id 逆引きを想定するため"`
- **`errs[]` の業務的理由は `when` に自然文で書く**（`why` が無いため）。
  - OK: `{ cond: applyDeadline >= scheduledAt, err: ApplyDeadlineInvalid, when: 申込締切が開催以降では業務的に成立しない }`
- **業務エラーと実装エラーを区別する**（正典。`checks/scenario-rules-quality.md` はここへ委譲）: `errs[]` には業務的に発生し得る違反のみ書き、以下は書かない。

  | カテゴリ | 例 | 理由 |
  |---|---|---|
  | スケジューラ／cron 誤発火 | `TooEarlyForNoShow` | 業務違反でなく実装／インフラ問題 |
  | null pointer / 型不一致 | `NullParticipationId` | スキーマ／実装で防ぐ |
  | API タイムアウト / ネットワーク | `PaymentGatewayTimeout` | infrastructure 層で再試行・補償 |
  | 並行制御の衝突 | `OptimisticLockFailure` | リトライ / トランザクション境界の話 |

  判別のコツ: (1) 業務関係者（PO / 主催者 / 法務）が想定するエラーか → YES なら書く。(2) 実装エンジニアがコードレビューで指摘するエラーか → YES なら書かない。(3) 同事象でも業務語彙に寄せられるなら寄せる（NG: `err: TooEarlyForNoShow, when: スケジューラ誤発火` → OK: `err: NoShowDetectionTooEarly, when: 早期判定試行（遅刻者の余裕未確保）`）。
- **`rules[]`/`errs[]` は全 scenario 義務ではない**: goal に直結し業務価値を持つ scenario に絞る。単純な CRUD・導線・通知だけの scenario は空でよい。`dmlctl view --view=coverage` の「未記入」は**意図的に許容した箇所**と**未着手**を区別して読む（残欠そのものはバグではない）。迷ったら「この不変条件が破れると業務が困るか？」を基準にする。

### 検証観点

- 構造: `err_name_quality`（数字入りコード風 / 1 語の汎用語を検出）。
- 意味: [`checks/scenario-rules-quality.md`](./checks/scenario-rules-quality.md)（rule=不変条件か・err=業務エラーか・why/when 補強）。

---

## 4. コマンド (Command)

### 定義

「これをやってほしい」というシステムへの依頼。命令形で書く（例: 「注文する」「在庫を引き当てる」）。

### 命名・構文

- 値は PascalCase（§1、schema `#/$defs/pascalCase`）。命令形の業務行為動詞。

### 設計判断ルール

- **CRUD 風接頭辞を避ける**: `Create` / `Add` / `Update` / `Delete` / `Remove` / `Get` / `Set` / `Fetch` / `Edit` / `Modify` / `Insert` などの汎用接頭辞ではなく、業務行為の動詞に言い換える（貧血な命名の回避）。接頭辞リストの実体は `checks.py` の `crud_cmd_naming`。
- 業務アクターが発行しない内部 CMD の書き方は §2「内部 CMD」を参照。

### 検証観点

- 構造: `crud_cmd_naming`（CRUD 接頭辞の検出）、`dangling_cmd`（`scenarios[].cmd`・`policies[].cmd` を declared として `transitions[].via` と突合）。
- 意味: [`checks/bc-vocabulary-consistency.md`](./checks/bc-vocabulary-consistency.md)（接頭辞に現れない CRUD 的発想の評価）。

---

## 5. ドメインイベント (Event)

### 定義

業務的に「あ、これが起きた」と言える過去の出来事。「〜された」「〜完了した」と書く（例: 「注文が確定した」）。

### 命名・構文

- 値は PascalCase。schema: EVT 宣言は `aggregates[].events[]`（`#/$defs/eventMeta`）、分岐 EVT は `#/$defs/branch`。
- 過去形・受動態・中粒度（大きすぎず・細かすぎず＝運用上意味のある粒度）。

### 設計判断ルール

- **`pivotal: true`（節目イベント）の宣言**: Big Picture EventStorming の Pivotal Event（タイムラインを大きく区切る節目）を、発火元 scenario の `pivotal: true` で宣言する。
  - **判定基準**: そのイベントの前後で「業務の関心事・登場人物・言葉」が変わるか（例: 「注文が確定した」を境に販売の言葉から物流の言葉に変わる）。
  - **個数の目安**: 1 モデルに 2〜4 個。多すぎると節目の意味を失う。
  - **効能**: BC 境界候補の最有力な手がかり（§9・フェーズ 4.5 で「節目の前後で言葉が変わるか」を確認）。HTML §3 で ⭐ バッジ＋強調枠で描画。
  - `brs` を持つ scenario に付けると全分岐 EVT が節目扱い。特定分岐だけが節目なら scenario 分割を検討。
- フロー連鎖の起点・連結における EVT の役割は §12 を参照。

### 検証観点

- 構造: `orphan_event`（どこからも参照されない EVT。意図的な終端は `events[].terminal: true` で除外）、`unknown_evt_in_policy`（`policies[].trg` が未宣言 EVT を指す）。
- 意味: [`checks/causal-chain-completeness.md`](./checks/causal-chain-completeness.md)。

---

## 6. ポリシー (Policy / EVENTUAL-TX)

### 定義

「あるイベントが起きたら、次にこのコマンドを発行する」という業務ルール（例: 「注文確定 → 在庫引き当て」）。`policies[]` は **EVENTUAL-TX（非同期・別トランザクション）限定**で使用する。

### 命名・構文

- schema: `#/$defs/policy`。必須 `[name, ctx]`。`trg`（単一）と `trgs`（複数）は同時指定禁止。`bulk: true` のとき `qry` 必須。
- `trgs` は `{ evts: [...], mode }`。`mode` は `#/$defs/triggerMode`（`all`/`any`/`or`）。

### 設計判断ルール

- **SAME-TX と EVENTUAL-TX の判定**:

  | TX | 書き方 | 根拠 |
  |----|-------|------|
  | SAME | SCENARIO の `brs`（§2） | コマンド内の同期処理。Repository のトランザクション境界内で完結 |
  | EVENTUAL | `policies` の要素 | EventBus 経由の非同期処理。別トランザクションで発火 |

- **副作用専用 POLICY の `cmd` 省略基準**: 外部通知 / メール / プッシュ送信など infrastructure 呼び出しで、内部 AGG を一切変更しないものに限り `cmd` を省略できる（対応する SCENARIO も書かない）。AGG を更新する処理が含まれるなら必ず `cmd` と SCENARIO を書く。
- **`policies[].agg`**: POL の `cmd` が AGG を変更するなら `agg` を併記する（scenarios と対称化）。`dangling_cmd` は `policies[].cmd` も declared として扱う。
- **bulk / qry の関係**: `bulk: true` のとき `qry` 必須（送信対象リストを明示）。単一宛先が `trg` ペイロードから決まる場合は省略可。HTML §2 では fanout（× N バッジ）で描画。
- **複数トリガーの join / OR（`trgs`）**:
  - `mode: all`（= concurrent）= **join（AND）** — 全 evts が揃って起動。HTML では BPMN シンクバー（Σ N）。
  - `mode: any`（= or）= **OR** — いずれか 1 つで起動。複数の業務経路が同一 POLICY に合流する構造を 1 つで表す（例: 返品確定・持ち戻り取消・一部返金合意のいずれでも同じ返金台帳へ記帳）。
- **時間・期限・SLA**: ドメインの時間制約は散文に逃がさず専用フィールドで一級表現する。
  - `policies[].within` — EVENTUAL-TX の**遅延許容 SLA**（例「火金の週2回」「出荷から24時間以内」）。バッチ・定期実行であることを明示し、競合の議論の起点になる。
  - `brs[].after` — **タイムアウト分岐**の待機時間（例「入金なく1週間」）。時刻駆動の分岐を cond の散文でなくフィールドで表す。
  - いずれも optional・自然文。値は `flow-causality` view に載り意味チェックが時間観点を評価できる。
- **POLICY のガード条件は呼び出される SCENARIO の `rules[]` に書く**（正典。`checks/saga-completeness.md` はここへ委譲）: policy schema には `rules[]` が無い。「この POLICY を skip すべき業務条件」は policy の `note` に簡潔に書きつつ、**policy が起動する CMD を実行する SCENARIO の `rules[]` / `errs[]` にガードを書く**。これにより scenario 側の構造チェック（dangling_cmd・state_reachability 等）でガード抜けが検出されやすくなる。

  典型的な暴発リスク: `bulk: true` の POLICY が cascade 発火するとき後続 POLICY を意図せず起動する。例: `NotifyParticipantsOnEventCancelled`（bulk Cancel）→ `ParticipationCancelled` 連発 → `PromoteOnCancelled` が繰上を試みるが Event 自体が CANCELLED なので業務矛盾。防ぐには繰上 scenario に：

  ```yaml
  scenarios:
    - name: システムが繰上を実行する
      cmd: PromoteFromWaitlist
      rules:
        - { rule: Skip promotion when Event itself is CANCELLED, why: alt-cancel フロー連鎖中の暴発防止 }
      errs:
        - { cond: 対応する Event が CANCELLED, err: EventAlreadyCancelled, when: alt-cancel 連鎖中の繰上試行 }
  ```

  合わせて `policies[...].note` に「`EventAlreadyCancelled` ガードで連鎖発火を防いでいる」と明記するとレビュー時に relation を辿りやすい。

### 検証観点

- 構造: `unknown_evt_in_policy`（trg/trgs の実在）、`dangling_cmd`（policies[].cmd）。
- 意味: [`checks/saga-completeness.md`](./checks/saga-completeness.md)（Saga 完結性・POLICY オーバーラップ・補償 TX・OR の妥当性）。

---

## 7. リードモデル (Read Model / qry)

### 定義

画面表示や判断材料のために「読むだけ」のデータ（書き換えはしない）。例: ダッシュボード、検索一覧。

### 命名・構文

- schema: トップレベル `queries[]` は `#/$defs/qry`。**`users` は文字列 / `sources` は配列**（非対称・§1）。値識別子は PascalCase。

### 設計判断ルール

- **`qry` は判断材料のみ**: アクター（「このコマンドを発行するか」）またはポリシー（「どのコマンドを発行するか・誰に対して」）が判断するために必要なデータのみ書く。コマンド実装内部で必要なデータ（BULK の実行対象リストなど）は書かない。
- **`queries[]` リードモデル候補の粒度**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む / (b) 複数集約・複数 BC を横断 / (c) BULK クエリ（一覧取得）のいずれかのみ記載する。

### 検証観点

- 構造チェックは無い（参照は任意）。品質は主にレビューで担保。

---

## 8. 集約 (Aggregate)

### 定義

「同時に変わるデータの塊」。トランザクション境界であり、不変条件を守る単一の責任主体（例: 注文 1 件と注文明細は同じ集約）。

### 命名・構文

- schema: トップレベル `aggregates[]` は `#/$defs/aggregate`。`name` は PascalCase、`states` は UPPER_SNAKE。
- `contexts[].aggs` は AGG 名（PascalCase 文字列）の**軽量名簿**。詳細はトップレベル `aggregates[]` に集約する。

### 設計判断ルール

- **なぜトップレベルか**（contexts 内に埋めない理由）: (1) AGG は BC をまたいで参照される（品質チェックのグラフ起点）、(2) `transitions[].via`（CMD 名）と `scenarios[].cmd` を機械的に突合できる、(3) 責務を 1 ブロックで読める。
- **フィールドの役割**（型・必須は schema 参照）:

  | フィールド | 役割 |
  |---|---|
  | `name` / `ctx` | AGG 識別子と所属 BC（所有者は 1 つ） |
  | `purpose` | 「単一の責任主体として何のソース・オブ・トゥルースか」を 1 文で（**30 字以上推奨**。閾値実体は `checks.py` の `agg_purpose_minlength`） |
  | `background` | 「なぜ今この AGG を切り出すか・既存運用の何が痛いか」（1〜3 文・WHY） |
  | `constraints[]` | 業務／法令／プラットフォーム由来の制約（技術スタック制約に偏らせない） |
  | `states` / `transitions[]` | 状態名（UPPER_SNAKE）と遷移。`via` は scenarios[].cmd と突合 |
  | `attrs[]` | ペイロード属性（`name`/`type`/`required`/`note`）。HTML §7 で属性表 |
  | `events[]` | emit する EVT 宣言（`params[]` は `attrs[]` と同構造）。HTML §7 でペイロード表 |

- **`purpose` は業務語彙・単一責任で**（`checks/agg-purpose-quality.md` の根拠）: 実装詳細（「テーブル trade_in を CRUD する」）や短すぎる記述（「下取を扱う」）は NG。OK 例「旧機種の引き受けから売買成立まで状態を所有し、各遷移の根拠を法令準拠で明示する」。
- **AGG は所有 BC が 1 つ**: 複数 BC で参照される AGG でも `ctx` は 1 つに決める。参照側 BC は up/dn の依存関係で表現する（§9）。
- **transitions[] の初期化規約**: **AGG 生成（creation）は `transitions[]` に書かない**（schema の `from` は実在状態名のみ、`(initial)` 等の疑似状態は不可）。

  | 状況 | 書き方 |
  |---|---|
  | 単一の入口状態（Group → ACTIVE） | `states: [ACTIVE]` だけ書き `transitions:` には書かない |
  | 入口で分岐（Rsvp → ACCEPTED / WAITLISTED） | 入口受付ステート `APPLIED` を states[] に加え `{ from: APPLIED, to: [ACCEPTED, WAITLISTED], via: ApplyForMeetup }` |
  | 同一状態内の属性変更（AppointCoOrganizer） | `transitions[]` には書かず `scenarios[].agg` ＋ `lang.cmds` で表現 |
  | 単一状態のみで終わる AGG（CheckIn → CHECKED_IN） | `states: [CHECKED_IN]`、`transitions: []`（空配列）を明示 |

  `state_reachability` は「states[] 先頭を入口とみなし、それ以外はいずれかの `to` で到達可能でなければ違反」と解釈する。入口状態を states[] 先頭に置くこと。

### 検証観点

- 構造: `orphan_agg`（どの scenario からも参照されない）、`dangling_cmd`、`state_reachability`、`agg_purpose_minlength`、`cross_bc_state_name_collision`。
- 意味整合の突合: `scenarios[].agg` ⇔ `aggregates[].name`、`scenarios[].cmd` ⇔ `transitions[].via`、`scenarios[].evt` ⇔ `events[].name`、`contexts[].aggs` ⇔ `aggregates[].ctx`。
- 意味: [`checks/agg-purpose-quality.md`](./checks/agg-purpose-quality.md)（単一責任・業務語彙・WHY）。

---

## 9. 境界づけられたコンテキスト (BC)

### 定義

「同じ言葉が同じ意味で通じる範囲」（例: 営業の「顧客」と請求の「顧客」は別 BC のことが多い）。BC 内で全員（業務・開発・AI）が同じ意味で使う言葉が **Ubiquitous Language**（`contexts[].lang`）。

### 命名・構文

- schema: `contexts[]` は `#/$defs/context`。`name` は `lowercase-with-hyphen`（`#/$defs/contextName`）。関係タイプ `rel` は `#/$defs/relationshipEntry`（Customer-Supplier / Conformist / Shared-Kernel / ACL + CML 語彙）。BC 種別は `#/$defs/bcType`。
- **`up`/`dn` は推奨**（schema 上 optional だが依存方向を明示すると BC マップが立体化）。**依存なしは空リスト `[]`** を書いて「考慮済み」と示す。
- **`contexts[].lang` はカテゴリ別 dict-of-dicts**（`aggs`/`vos`/`actors`/`cmds`/`evts`/`pols`/`qrys`）。本 BC で扱う語彙を種別ごとに英→日ラベル（短い表記）で与える。

  ```yaml
  contexts:
    - name: store-front
      lang:
        aggs:    { Order: "注文", Quote: "概算見積" }
        cmds:    { PlaceOrder: "注文を確定する" }
        evts:    { OrderPlaced: "注文された" }
        pols:    { AuthorizeOnOrderPlaced: "注文確定時に差額与信" }
  ```

- 値は**短い日本語ラベル**（フロー図の付箋ラベルに直接使う）。長い説明文は `purpose` / `background` / `note` 側へ。
- 依存方向: **上流 / Upstream（`up`）** = 自分が参照する側の BC（提供される側でなく借りる側）。**下流 / Downstream（`dn`）** = 自分が提供する側。

### 設計判断ルール

- **`contexts[].lang` / `up` / `dn` は HTML §6 の LANGUAGE / 依存方向、および glossary_index（英→日変換）の唯一の真実源**（別の用語集は持たない）。境界の理由・含むシナリオ・目的・背景・制約の散文は `contexts[].description` に書く。
- **同じ識別子が複数 BC で出る場合は最初の登録を優先**（後勝ちにすると flow 描画ラベルが BC 順序依存になり不安定）。
- **関係タイプ**: Customer-Supplier（下流が上流に API を注文でき優先順位を交渉できる）／ Conformist（下流が上流の形にそのまま従う・交渉力なし）／ ACL（下流に変換レイヤを挟み上流の言葉を隔離）／ Shared-Kernel（両 BC で共有する小さなモデル・変更は両方の合意）。
- **インフラ系ドメインの BC 昇格 vs POLICY 留置**: 業務ドメインと独立した技術基盤（通知・バッチ・外部 API 連携・決済・メール等）は毎回どちらか判定する（正典。session-guide はここへ委譲）。

  | POLICY 留置で十分なサイン | BC に昇格すべきサイン |
  |---|---|
  | 通知/連携が 1 種類のみ | 複数種類を統一管理（APPROVAL / REMINDER / CANCELLATION 等） |
  | 送信結果の監査・再送/失敗管理が不要 | 送信状態（QUEUED / SENT / FAILED / RETRYING）を持つ |
  | 状態を持たない（送ったら完了） | SLA・再送ポリシー・フォールバックが業務要件 |
  | 他 BC から参照されない | 他 BC から「どの通知を送ったか」を参照される |
  | → 既存 BC の `policies` に追加。専用 CONTEXT は作らない | → `contexts` に新規 BC を宣言し `up`/`dn` を明示 |

  迷う場合は `note: "[?] ..."` で保留し後続で再評価。**「データモデル（テーブル）は存在するが BC として宣言していない」宙吊り状態は原則 NG**。

### 検証観点

- 構造: `language_coverage`（AGG/CMD/EVT/POL が lang に未登録）、`dangling_lang_entry`（lang の名前の実体が本体に無い）、`bc_vocabulary_collision`（同 EN 別ラベル / 同ラベル別 EN の完全一致衝突）、`cross_bc_state_name_collision`。
- 意味: [`checks/bc-vocabulary-consistency.md`](./checks/bc-vocabulary-consistency.md)（異名同義・同名異義・Conformist/ACL の判断）。

---

## 10. サブドメイン (Subdomain / コアドメイン蒸留)

### 定義

全部を同じ熱量で作らないために投資配分を仕分ける分類（Distillation）。**CORE**（間違えると事業が成り立たない・差別化そのもの）／ **SUPPORTING**（業務に必要だが差別化でない）／ **GENERIC**（買ってくれば済む・SaaS で十分）。

### 命名・構文

- schema: `domains[]` は `#/$defs/domain`、`subs[].type` は `#/$defs/subdomainType`（`CORE_SUBDOMAIN` / `SUPPORTING_SUBDOMAIN` / `GENERIC_SUBDOMAIN`）。各 `contexts[].sub` に所属サブドメイン名を割り当てる（BC : サブドメイン は N:1 可）。

### 設計判断ルール

- BC 候補が出揃ったら依存方向を決める前に 2 問で分類する: (1)「間違えると事業が成り立たない／差別化そのもの」は？→ CORE、(2)「買ってくれば済む／他社の真似で十分」は？→ GENERIC（どちらでもない＝ SUPPORTING）。
- CORE はモデリング・実装に最も投資、GENERIC は SaaS/ライブラリ購入や省力実装で済ませる。迷う場合は `[?]` で保留し `decisions[]` 昇格候補に。

### 検証観点

- 構造: `subdomain_classification`（未実施・`subs` 未定義・`contexts[].sub` 未設定/参照切れ・CORE 0 件・全件 CORE を検出。フェーズ 7 のゲート）。

---

## 11. 意思決定 (decisions)

### 定義

設計の分岐点で「採用案 / 不採用案 / 各案の理由」を残す記録。未来の自分・実装者・後から参加するメンバーが「なぜそうなっているか」を再現できるようにする。`[?]` の保留メモを「選択肢が揃ったら」昇格させる。

### 命名・構文

- schema: `decisions[]` は `#/$defs/decision`（必須 `[id, topic, chosen, options]`）、`options[]` は `#/$defs/decisionOption`。
- `chosen` は `options[].name` のいずれかと完全一致（未確定なら `chosen: 未確定`）。
- **`options[].adopted: true`** — 採用した option を boolean で明示する。`chosen`（採用案の名前）と `adopted: true`（採用フラグ）は**対で書く**。構造チェック `decision_chosen_adopted` が両者の整合（不在 / 0 件 / 複数 / 不一致）を検証するため、`chosen` だけ書いて `adopted` を落とすと違反になる。
- `options[].name` は追跡用の英語 slug 推奨（例 `10-days`, `hold-difference`）。`options[].label` は HTML 表示用の日本語ラベル（あれば「label (name)」形式で描画）。

### 設計判断ルール

- **各フィールドの書き方**:

  | フィールド | 書き方のコツ |
  |---|---|
  | `topic` | 「何を決めたか」を 1 行で（CMD 名でなく業務概念で） |
  | `options[]` | 検討した全選択肢を書く（1 件しか書かないと「比較していない」シグナル） |
  | `options[].why` / `why_not` | **業務文脈**で書く（採用: 業務が何が楽になるか／不採用: 業務的に何が不利か）。「実装が楽」だけでなく業務的な違いを |
  | `affects[]` | 影響を受ける AGG / Policy / BC 名。AGG 名は必ず含める。Policy 連鎖に影響するなら Policy 名も。Event 単独は粒度が低すぎる |
  | `note` | 「決まったが後で見直す可能性のある条件」「関連する未決問題」等 |

- **業務文脈で書く**（`why`/`why_not`）の目安: 「この理由を後から読んだ人が、自分でコードレビューに反映できるか」。できないなら抽象的すぎる。
  - わかりにくい: `why_not: 責務違反` → わかりやすい: `Participation 集約に capacity を持たせると、申込のたびに他を全部読んで合計しないと残席が出せず、ロック競合が頻発する`。
- **ストローマン論法を避ける**: `why_not` を複数 decision で使い回すと選択肢の固有性を語れていない。各オプションの固有の不利点に書き換える。
- **「決められないとき」**: `chosen: 未確定` で保留し `options[]` の理由だけ埋めておく。`[?]` より一段構造化されており、品質チェックが「未確定 decision の長期残存」を検出する余地もある。

### 検証観点

- 構造: `decision_chosen_adopted`（chosen ⇔ adopted: true の整合）、`decision_affects_presence`（affects の有無）、`question_decision_link`（closed question の decision_id が実在するか）。
- 意味: [`checks/decision-rationale-clarity.md`](./checks/decision-rationale-clarity.md)（why/why_not の非循環性・affects 粒度・ストローマン回避）。

### `[?]`（未確認）の慣習と昇格

確信が低い箇所・設計判断が必要な箇所は該当要素の `note` に `[?]` を付けて理由も書く。選択肢が見えてきた段階で `decisions[]` に昇格させ、HTML §5 で比較カードとしてレビューできる状態にする。

---

## 12. フロー連鎖 (Flow chaining)

### 定義

ハッピーパスと複数の代替シナリオ（キャンセル・繰上待ち・エラー復旧等）が「どの scenarios/policies をどの順で辿るか」を明示的に残す仕組み。明示しないと後で別パスを書き起こすときに情報が落ちる。

### 命名・構文

- フロー定義は 3 フィールドに分散して保持する（トップレベル `flows[]` は存在しない）:
  - **`narratives[]`**（`#/$defs/narrative`）: フロー識別子（`id`）・見出し（`title`）・種別（`kind`）・散文（`prose`）・開始 scenario（`entry`）。
  - **`scenarios[].next`**: 継続先（string = 全フロー共通 / dict = `narratives[].id` ごと）。
  - **`scenarios[].brs[].terminal`**: 「この分岐が発火したら指定フローはここで終わる」宣言。
- **`kind`**（narrative 必須）: `happy` = 主要フロー（**1 セッションで原則 1 本**、400〜600 字）／ `alt` = 代替シナリオ（複数可、100〜200 字）。`kind` は分類ヒントで HTML 表示には影響しない。

### 設計判断ルール（参照規則）

- **`narratives[].entry`** は `scenarios[].name` を指す（typo は `flow_chain_resolution` が検出）。
- **`scenarios[].next`** が dict のとき、キーは `narratives[].id` の集合のサブセット。
- **`scenarios[].brs[].next`** — branch ごとに連鎖を変える時に書く。**`sc.next` より優先**。
- **`scenarios[].brs[].terminal`** 値は `narratives[].id` のいずれか。`brs[].next` と同時指定は禁止（schema の not 制約）。
- 順序は因果連鎖と整合させる（前 scenario の `evt` が後続 scenario の `cmd` まで policy 連鎖で繋がる）。
- 同一 `ctx` の連続 sync ステップはビルダーが 1 レーンに併合。`ctx` 変化・policy ステップ・`trgs` join は非同期矢印・sync-bar として描画。
- **複数 `narratives[].entry` が同一 scenario を指す場合**は当該 scenario の `next` を dict 形式 `{happy: ..., alt-X: ...}` にしてフロー別の継続先を分岐させる。
- policy ステップはビルダーが `scenarios[].evt → policies[].trg` マッチで**自動挿入**する（手書きの記号 DSL は無い）。

### 検証観点

- 構造: `flow_chain_resolution`（entry/next/terminal の解決）、`narrative_entry_consistency`（共有 entry で next が dict 分岐していない）、`narrative_happy_unique`（happy が 2 件以上）。
- 意味: [`checks/causal-chain-completeness.md`](./checks/causal-chain-completeness.md)、[`checks/saga-completeness.md`](./checks/saga-completeness.md)。

---

## 13. 検証の境界（構文 vs 意味）

| レイヤ | 担保するもの | 例 |
|------|------|------|
| **JSON Schema**（機械・決定論的） | 構文 validity。型・必須・enum・命名 pattern・排他制約・未知フィールド禁止（全量は [`dml.schema.yaml`](./dml.schema.yaml)） | `cmd` が PascalCase か、`bulk:true` に `qry` があるか |
| **構造チェック**（Python・LLM 不要） | 参照実在・命名・到達可能性（19 観点は [`quality-check.md`](./quality-check.md)、実体は [`checks.py`](../scripts/dml_filters/checks.py)） | `trg` が実在 EVT を指すか、`scenarios[].cmd` ↔ `transitions[].via` |
| **意味チェック**（観点別 LLM） | 因果整合・モデル品質（6 観点は [`checks/*.md`](./checks/)） | 分岐の MECE 性、業務語彙の適切さ、Saga 完結性 |

**スキーマ通過は必要条件であって十分条件ではない。** ビルダー（`eventstorming_build.py`）は読込時に schema 検証し HTML §9 にバナー（✅ / ⚠ 違反一覧）を描画する。検証は**非ブロッキング**（違反があっても HTML は生成される）。全行コメントのみ（YAML→`None`）や空ファイルは「未記述」として検証対象外（進行中セッション許容）。

書き出し後の標準フロー・Agent 起動テンプレは [`quality-check.md`](./quality-check.md) を参照。
