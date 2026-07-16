# DML（Domain Modeling Language）記法仕様 — 設計ガイドライン

DDD モデリングのための情報圧縮言語。**構文 validity（形が正しいか）は [`./dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12）で機械検証**する。本書は schema では表現できない**設計判断・記法哲学・慣習**を扱う。

- スキーマ通過は必要条件であって十分条件ではない。「形が正しい」ことを schema が、「意味が正しい」ことを品質チェック（構造＋意味、`references/quality-check.md`）が担保する（§7）
- 検証: `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py docs/eventstorming/<session>.dml.yaml`
- フル例: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)（コミュニティイベント参加ドメイン・`narratives[]`（entry 付き）/ `decisions[]` を含む参照例）

散文情報（`session` / `narratives[]` / `actions[]` / `questions[]` / `queries[]` /
`contexts[].description`）もすべて DML 内のトップレベルフィールドとして保持する（別の `.md` は無い）。
各フィールドはすべて optional（進行中セッション中は欠落 OK）。AI からの編集は
`scripts/dmlctl.py` の `set/add/remove` を使うと round-trip でコメント・引用形式を維持できる。

---

## 0. 記法の原則

- **YAML 直書き**: `docs/eventstorming/<session>.dml.yaml` に純 YAML（フェンス不要）で書く。ビルダーはこの 1 ファイルだけから HTML を生成する
- **トップレベルは 4 モデル本体 + 任意散文系**: モデル本体 `contexts` / `aggregates` / `scenarios` / `policies` ＋意思決定ログ `decisions`、加えて散文系 `session` / `narratives` / `actions` / `questions` / `queries` / `domains`。全フィールドが optional（空 `{}` も valid）。トップレベル `flows[]` は存在しない（連鎖は `narratives[].entry` ＋ `scenarios[].next` / `brs[].terminal` で表現）。コメントによるセクション区切りは使わない（リスト構造で自然に分離される）
- **識別子は英語 PascalCase**（`cmd` / `evt` / `agg` / `trg` / `qry` の値、`aggregates[].name` 等）。`()` や `<<>>` は付けない
- **`scenarios[].name` のみ日本語**で「アクター＋行為」を書く（例: `主催者がコミュニティを作成する`）
- **`rules[].rule` の不変条件は英語**。日本語の補足は `why` / `when` / `note` の**構造化フィールド**へ書く（`#` 行コメントによる補足慣習は廃止）
- **BC 名は `lowercase-with-hyphen`**、略さずに書く
- **キー順の推奨**（`scenarios`）: `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`

詳細な型・必須フィールド・enum 値は schema を参照。

---

## 1. インフラ系ドメインの扱い（BC 昇格 vs POLICY 留置）

業務ドメインと独立した技術基盤（通知・バッチ・外部 API 連携・決済・メール等）は、**BC に昇格する**か**既存 BC の POLICY 内に留める**かを毎回判断する。

### POLICY 留置で十分なサイン

- 通知 / 連携が 1 種類のみ（例: 承認通知のみ）
- 送信結果の監査・再送 / 失敗管理が不要
- 状態を持たない（送ったら完了で追跡しない）
- 他 BC から参照されない

→ 既存 BC の `policies` に POLICY を追加する。専用 CONTEXT は作らない。

### BC に昇格すべきサイン

- 複数種類の通知 / 連携を統一的に管理（例: APPROVAL / REMINDER / SURVEY / CANCELLATION など）
- 送信状態（QUEUED / SENT / FAILED / RETRYING）を持つ
- SLA・再送ポリシー・失敗時のフォールバックが業務要件
- 他 BC から「どの通知を送ったか」を参照される（監査ログ兼用など）

→ `contexts` に新規 BC を宣言し、`up` / `dn` で他 BC との関係を明示する。**`contexts[].lang` / `up` / `dn` は HTML §6 の LANGUAGE / 依存方向、および glossary_index（語彙の英→日変換）の唯一の真実源**（別の用語集は持たない）。境界の理由・含むシナリオ・目的・背景・制約の散文は `contexts[].description` に書き、ビルダーが merge して描画する。

**`contexts[].lang` はカテゴリ別 dict-of-dicts**: 本 BC で扱う語彙を種別ごとに分類して英→日ラベル（短い表記）を与える。HTML §6 では制約の下にタイプ別表で描画される。

```yaml
contexts:
  - name: store-front
    lang:
      aggs:    { Order: "注文", Quote: "概算見積" }
      vos:     { HoldAmount: "与信額" }
      actors:  { Member: "会員", System: "システム" }
      cmds:    { PlaceOrder: "注文を確定する" }
      evts:    { OrderPlaced: "注文された" }
      pols:    { AuthorizeOnOrderPlaced: "注文確定時に差額与信" }
      qrys:    { GetEstimateAmount: "概算買取額" }
```

同じ識別子が複数 BC で出る場合は **最初の登録を優先**（後勝ちにすると flow 描画ラベルが BC 順序依存になり不安定）。値は **短い日本語ラベル**（フロー図の付箋ラベルに直接使う）。長い説明文は `purpose` / `background` / `note` 側に書く。

迷う場合は `note: "[?] ..."` で保留し、後続フェーズで再評価する。**「データモデル（テーブル）は存在するが BC として宣言していない」状態は原則 NG**。

---

## 2. SCENARIO の哲学

### なぜ EVT 起点で書くか

「起きた事実」から始めることで、実装の都合（コマンドの存在・API の形）に引きずられず、ビジネスの本質的な流れを先に把握できる。

### `scenarios[].name` は日本語

アクター（主催者/参加者/システム）＋行為を日本語で書く。「誰が何をするシナリオか」が一目でわかり、BC の責務やユーザーロールとの対応も明確になる（英語識別子だけだと「OrderConfirmFlow」のような形式名に逃げやすい）。

### `actor` 必須

コマンドを発行するアクターを明記する。典型値は `Organizer`（主催者）、`Member`（参加者）、`System`（システム/ポリシー）。

### `rules[].why` の書き方（業務・UX 文脈への翻訳）

`rule` を**ユーザー影響・業務文脈**に翻訳する。`rule` の言い換えは情報が増えていないので NG。

- NG: `why: "name の一意性を保つため"`（rule の言い換え）
- OK: `why: "URL slug や検索 UX で name→id 逆引きを想定するため"`（業務・UX 文脈で説明）

AI 実装エージェントが Issue から実装するときに意図を読み解きやすくするため、`rules[].why` / `errs[].when` は強く推奨（schema 上は optional）。

### `errs[]` には `why` フィールドが無い

`rules[]` には `why` があるが `errs[]` には無く、フィールド名が非対称。`errs[]` の業務的理由（なぜそのエラーが起こり得るか／なぜ業務的に問題か）は **`when` フィールドに自然文で書く**。

- OK: `{ cond: applyDeadline >= scheduledAt, err: ApplyDeadlineInvalid, when: 申込締切が開催以降では業務的に成立しない }`
- NG: `{ cond: ..., err: ..., why: ... }`（schema が `why` を未知フィールドとして弾く）

加えて **業務エラーと実装エラーを区別する**。`errs[]` には業務的に発生し得る違反のみ書き、スケジューラ誤発火・null pointer・タイムアウト等のインフラ／実装エラーは含めない。判別基準は `references/checks/scenario-rules-quality.md` も参照。

### `rules[]`/`errs[]` は全 scenario 義務ではない

不変条件・業務エラーは、**goal に直結し業務価値を持つ scenario に絞って**書く。単純な CRUD・導線・通知だけの scenario は `rules`/`errs` が空でよい（無理に埋めると業務価値の薄いルールでノイズが増える）。`dmlctl view --view=coverage` に出る「未記入」は、**意図的に許容した箇所**と**未着手**を区別して読む — 残欠そのものはバグではない。どこに書くべきか迷ったら「この不変条件が破れると業務が困るか？」を基準にする。

### `pivotal: true`（節目イベント）の宣言

Big Picture EventStorming の **Pivotal Event**（タイムラインを大きく区切る節目イベント）を、
発火元 scenario の `pivotal: true` で宣言する。

- **判定基準**: そのイベントの前後で「業務の関心事・登場人物・言葉」が変わるか（例: 「注文が確定した」を境に販売の言葉から物流の言葉に変わる）
- **個数の目安**: 1 モデルに 2〜4 個。多すぎると節目の意味を失う
- **効能**: BC 境界候補の最有力な手がかり（フェーズ 4.5 で「節目の前後で言葉が変わるか」を確認する）。HTML §3 フロー図では ⭐ バッジ＋強調枠で描画され、後から見る人がフローの構造を掴みやすくなる
- `brs` を持つ scenario に付けた場合は全分岐 EVT が節目扱いになる。特定の分岐だけが節目のときは scenario の分割を検討する

### `qry` は判断材料のみ

アクター（「このコマンドを発行するか」）またはポリシー（「どのコマンドを発行するか・誰に対して」）が**判断するために必要なデータ**のみ書く。コマンド実装内部で必要なデータ（BULK の実行対象リストなど）は `qry` に書かない。

### 分岐（`brs`）の使い所

コマンドの処理結果に応じて発火イベントが変わる場合、`evt` の代わりに `brs` で分岐を書く（同一トランザクション内の SAME-TX 分岐）。EVENTUAL-TX は `policies` で表現する（§3）。

`brMode` の語彙（`exclusive` 既定 / `concurrent` / `inclusive`）と構造は schema 参照。

### 内部 CMD（時刻駆動・コールバック・副作用）の書き方

業務アクター（会員・スタッフ）が直接発行しない CMD でも、AGG の状態を変える限り **scenario として書く** か **policy.cmd として実体化する** 必要がある。`dangling_cmd` チェックは両方を参照する。

| 類型 | 書き方 | 例 |
|----|-------|----|
| 時刻駆動（タイムアウト・失効） | BULK policy（`qry`・`cmd` 必須）＋ 対応する scenario（actor: System） | `DetectArrivalTimeoutWhenItemNotReceived` policy + `システムが未着タイムアウトを検出する` scenario |
| 外部コールバック（決済結果通知等） | 結果を 2 値以上に分けるなら `brs` で SAME-TX 分岐、別トランザクションなら policy | ExecutePayout の brs に PayoutExecuted / PayoutFailed |
| 内部副作用（再試行・補償・リカバリ） | 別 scenario（actor: System）として書く。trigger 元は前 scenario の `brs[].next` か policy | `システムが入金をリトライする` |

`actor: System` は機械が起点であることを意味し、業務担当者が居ない自動処理を明示する慣習。

---

## 3. POLICY の運用（EVENTUAL-TX）

`policies` の各要素は **EVENTUAL-TX（非同期・別トランザクション）限定**で使用する。同一トランザクションで処理される分岐（SAME-TX）は、発行元 SCENARIO の `brs` として書く。

### SAME-TX と EVENTUAL-TX の判定

| TX | 書き方 | 根拠 |
|----|-------|------|
| SAME | SCENARIO の `brs` | コマンド内の同期処理。Repository のトランザクション境界内で完結 |
| EVENTUAL | `policies` の要素 | EventBus 経由の非同期処理。別トランザクションで発火 |

### 副作用専用 POLICY の `cmd` 省略基準

**副作用専用 POLICY**（外部通知 / メール / プッシュ送信などの infrastructure 呼び出しで、内部 AGG を一切変更しないもの）に限り `cmd` を省略できる。この場合、対応する SCENARIO も書かない。AGG を更新する処理が含まれるなら必ず `cmd` と SCENARIO を書く。

```yaml
policies:
  - name: NotifyOnEventRelocation
    ctx: event-planning
    trg: EventRelocated
    qry: GetConfirmedApplications
    bulk: true
    evt: ChangeNotified
    note: "会場変更時に既存参加者へ通知（メール送信のみ、状態遷移なし）"
```

### bulk / qry の関係

`bulk: true` のとき `qry` 必須（送信対象リストを明示するため）。schema が機械検証する。単一宛先が `trg` ペイロードから決まる場合は `qry` 省略可。

HTML §2 のフロー図では、`bulk: true` の POLICY は **fanout（× N バッジ + 3 枚スタック）** で描画される。

### 複数トリガーの join / OR（`trgs`）

複数のイベントに反応する POLICY は、`trg`（単一）の代わりに `trgs`（`evts` 配列 + `mode`）を使う。`mode` で結合方法を区別する：

- **`mode: all`（または `concurrent`）= join（AND）** — 全 evts が揃って初めて起動。HTML §2 では **BPMN シンクバー（Σ N）** で描画される。
- **`mode: any`（または `or`）= OR** — いずれか 1 つの evt で起動。「複数の業務経路が同一 POLICY に合流する」構造（例: 返品確定・持ち戻り取消・一部返金合意のいずれでも同じ返金台帳へ記帳）を 1 つの POLICY で表す。経路別に POLICY を複製する必要がなくなる。

```yaml
policies:
  - name: RegisterRefund
    ctx: accounting
    trgs:
      evts: [ReturnConfirmed, RedeliveryCancelled, PartialRefundAgreed]
      mode: or            # いずれかの経路で返金台帳に記帳される
    cmd: ExecuteRefund
    within: 火金の週2回     # 遅延許容 SLA（下記）
```

OR の意味論（1 つ揃えば発火してよいか、経路ごとに重複記帳しないか等）の妥当性は、構造チェックではなく `references/checks/saga-completeness.md` の LLM 観点で評価する。

### 時間・期限・SLA（`policies[].within` / `brs[].after`）

ドメインの時間制約は散文（note / cond）に逃がさず、専用フィールドで一級表現する：

- **`policies[].within`** — EVENTUAL-TX の**遅延許容 SLA**。「いつまでに反応が完了すべきか / 実際どの頻度で回るか」を自然文で書く（例「火金の週2回」「出荷から24時間以内」）。POLICY が即時でなくバッチ・定期実行であることを明示し、競合（バッチ遅延窓でのキャンセル競合など）の議論の起点になる。
- **`brs[].after`** — **タイムアウト分岐**の待機時間を自然文で書く（例「入金なく1週間」「本人確認3日不通」）。時刻駆動の分岐（期限切れ→自動取消など）を cond の散文ではなくフィールドで表す。

いずれも optional・自然文。値は `flow-causality` view にも載り（`policy.within` / `branch.after`）、意味チェックが時間観点を評価できる。HTML の ⏱ バッジ描画は将来対応（未描画でも壊れない）。上表「時刻駆動（タイムアウト・失効）」の BULK policy + System scenario 方式と併用する（`within`/`after` は宣言、実処理は scenario/policy が担う）。

### POLICY のガード条件は呼び出される SCENARIO の `rules[]` に書く

policy schema には `rules[]` が無い。「この POLICY を skip するべき業務条件」は、policy の `note` に簡潔に書きつつ、**policy が起動する CMD を実行する SCENARIO の `rules[]` / `errs[]` にガードを書く**。これにより scenario 側の構造化チェック（dangling_cmd・state_reachability 等）でガード抜けが検出されやすくなる。

例: `NotifyParticipantsOnEventCancelled` が `bulk: CancelParticipation` を発行すると `ParticipationCancelled` evt が連鎖し、`PromoteOnCancelled` policy が暴発するリスクがある。これを防ぐには `システムが繰上を実行する` scenario の `rules[]` に次を入れる：

```yaml
- { rule: Skip promotion when Event itself is CANCELLED, why: alt-cancel フローで bulk Cancel 後の暴発防止 (PromoteOnCancelled ガード) }
- { cond: 対応する Event が CANCELLED, err: EventAlreadyCancelled, when: alt-cancel 連鎖中の繰上試行 }
```

合わせて `policies[NotifyParticipantsOnEventCancelled].note` に「PromoteOnCancelled の連鎖発火を `EventAlreadyCancelled` ガードで防いでいる」と明記すると、後でレビューする人が relation を辿りやすい。

### `policies[].agg`

POL の `cmd` が AGG を変更するなら `agg` を併記する（scenarios と対称化）。`dangling_cmd` 構造チェックは `scenarios[].cmd` と `policies[].cmd` の両方を declared として扱う。

---

## 4. AGG（トップレベル）の設計意図

AGG 詳細はトップレベル `aggregates[]` に置き、`contexts[].aggs` は AGG 名（PascalCase 文字列）の**軽量名簿**とする。

### なぜトップレベルか（contexts 内に埋めない理由）

- AGG は BC をまたいで参照される（品質チェックのグラフ起点）
- `transitions[].via`（CMD 名）と `scenarios[].cmd` を機械的に突合できる
- AGG の責務（`purpose` / `background` / `constraints` / `states` / `transitions` / `attrs` / `events`）を 1 ブロックで読める

### `aggregates[]` のフィールドの役割（型・必須は schema 参照）

| フィールド | 役割 |
|---|---|
| `name` / `ctx` | AGG 識別子と所属 BC（所有者は 1 つ） |
| `purpose` | 「単一の責任主体として何のソース・オブ・トゥルースか」を 1 文で（30 字以上推奨） |
| `background` | 「なぜ今この AGG を切り出すか・既存運用の何が痛いか」（1〜3 文） |
| `constraints[]` | 業務／法令／プラットフォーム由来の制約（複数可） |
| `states` / `transitions[]` | 状態名（UPPER_SNAKE）と遷移。`via` は scenarios[].cmd と突合 |
| `attrs[]` | AGG ペイロード属性。HTML §7 で属性表として描画 |
| `events[]` | この AGG が emit する EVT 宣言。`params[]` は `attrs[]` と同じ構造。HTML §7 でペイロード表として描画 |

### 意味整合（品質チェックが担保）

| 観点 | 突合 |
|---|---|
| 孤立 AGG / 未定義 AGG 参照 | `scenarios[].agg` ⇔ `aggregates[].name` |
| CMD が AGG 状態遷移に紐付くか | `scenarios[].cmd` ⇔ `aggregates[].transitions[].via` |
| EVT が AGG の宣言済み発火イベントか | `scenarios[].evt` ⇔ `aggregates[].events[].name` |
| BC 所有 AGG の双方向参照 | `contexts[].aggs`（名簿） ⇔ `aggregates[].ctx` |

スキーマは「`aggregates[].name` が PascalCase か」「`states` が UPPER_SNAKE か」までしか保証しない。**意味整合は品質チェックの責務**（`references/quality-check.md`）。

### AGG は所有 BC が 1 つ

複数 BC で参照される AGG でも `aggregates[].ctx` は 1 つに決める（所有者は 1 つ）。参照側 BC は up/dn の依存関係として表現する。

### transitions[] の初期化規約

**AGG 生成（creation）は `transitions[]` に書かない**。schema の `from` は `^[A-Z][A-Z0-9_]*$`（実在の状態名のみ）に制約されているため、`(initial)` や `_INITIAL_` のような疑似状態は使えない。

書き方の規約：

| 状況 | 書き方 |
|---|---|
| 単一の入口状態（例: Group → ACTIVE） | `states: [ACTIVE]` だけ書き `transitions:` には書かない |
| 入口で分岐がある（例: Rsvp → ACCEPTED または WAITLISTED） | サンプル DML のように "APPLIED" のような **入口受付ステート** を states[] に加え、`{ from: APPLIED, to: [ACCEPTED, WAITLISTED], via: ApplyForMeetup }` を書く |
| 同一状態内の属性変更（例: AppointCoOrganizer） | `transitions[]` には書かず、`scenarios[].agg` ＋ `lang.cmds` で表現する |
| 単一状態のみで終わる AGG（例: CheckIn → CHECKED_IN） | `states: [CHECKED_IN]`、`transitions: []`（空配列）を明示 |

`state_reachability` 構造チェックは「states[] のうち入口状態（最初に列挙したもの）を入口とみなし、それ以外はいずれかの `to` で到達可能でなければ違反」と解釈する。入口状態を意識して states[] 先頭に置くこと。

---

## 5. HTML 描画との関係

DML の値は HTML レンダリング時に付箋フロー図と同じ**役割ベースの意味色**でハイライトされる
（フィールド→色の対応はレンダリング仕様を参照。AI が色を意識して DML を書く必要はない）。

> **フロー図は DML から自動生成される**（手書きの記号 DSL は無い）。`narratives[].entry` を起点にビルダーが `scenarios[].next` を辿り、`scenarios[].evt → policies[].trg` のマッチで policy を自動挿入して Big Picture グリッドに描画する。

---

## 6. `[?]`（未確認）の慣習と `decisions[]` への昇格

確信が低い箇所や設計判断が必要な箇所には、該当要素の `note` に `[?]` を付けて理由も書く。進行中セッションを残しつつ、後続フェーズや次回セッションで再評価する。

```yaml
scenarios:
  - name: 参加者がイベントに参加申込する
    ctx: participation
    actor: Member
    cmd: ApplyForEvent
    agg: Participation
    rules:
      - rule: capacity check
        note: "[?] Event 集約と Participation 集約どちらが定員を持つ？"
```

**`[?]` で残した未確定判断は、選択肢が見えてきた段階で `decisions[]` に昇格させる**。`decisions[]` に書くことで「採用したもの / 不採用にしたもの / それぞれの理由」が構造化され、HTML §5 で比較カードとしてレビューできる（§9 参照）。

---

## 7. 検証の境界（構文 vs 意味）

| レイヤ | 担保するもの | 例 |
|------|------|------|
| **JSON Schema**（機械・決定論的） | 構文 validity。型・必須フィールド・enum・命名 pattern・排他制約・未知フィールド禁止は schema が機械検証する（制約の全量は [`./dml.schema.yaml`](./dml.schema.yaml)） | `cmd` が PascalCase か、`bulk:true` に `qry` があるか |
| **品質チェック**（構造チェック＋LLM 意味チェック） | 意味 validity。参照の実在・因果整合・モデル品質（観点一覧は `references/quality-check.md`） | `trg` が実在 EVT を指すか、`scenarios[].cmd` ↔ `transitions[].via` 整合、分岐の MECE 性、`evt` の過去形・`cmd` の命令形 |

**スキーマ通過は必要条件であって十分条件ではない。** ビルダー（`eventstorming_build.py`）は `.dml.yaml` 読込時に schema 検証し、HTML §9 にバナー（✅ / ⚠ 違反一覧）を描画する。**検証は非ブロッキング**で、違反があっても HTML は生成される。全行コメントのみ（YAML→`None`）や空ファイルは「未記述」として検証対象外（進行中セッション許容）。

---

## 8. 最小実例

scenario 1 件 + policy 1 件の最小形。**ドメイン全体のフル例**（contexts / aggregates / narratives /
decisions / queries を含む）は [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml) が正典。

```yaml
scenarios:
  - name: 主催者がイベントを公開する
    ctx: community-events
    actor: Organizer
    cmd: PublishEvent
    evt: EventPublished
    agg: Event
    rules:
      - rule: event must be in DRAFT status
        why: "公開済み・キャンセル済みからの再公開は別フロー"
    errs:
      - cond: alreadyPublished
        err: EventAlreadyPublishedError
        when: "既に PUBLISHED 状態の Event に PublishEvent が来た"

policies:
  - name: NotifyEventCancelled
    ctx: community-events
    trg: EventCancelled
    qry: AllApprovedParticipations
    bulk: true
    evt: CancellationNotificationSent
    note: "副作用専用 POLICY（メール送信のみ・cmd 省略）"
```

---

## 9. フロー連鎖と `decisions[]` の哲学

### なぜフロー連鎖が必要か

ドメインモデルには **ハッピーパス** に加えて **複数の代替シナリオ**（キャンセル・繰上待ち・エラー復旧 等）が存在する。それぞれが「どの scenarios/policies をどの順で辿るか」を明示的に残さないと、後で別パスを思い出して書き起こすときに必ず情報が落ちる。

フロー定義は **3 つのフィールドに分散** して保持する：
- **`narratives[]`**: フロー識別子（`id`）・見出し（`title`）・種別（`kind`）・散文（`prose`）・開始 scenario（`entry`）
- **`scenarios[].next`**: フロー連鎖の継続先（string = 全フロー共通 / dict = フロー別）
- **`scenarios[].brs[].terminal`**: 「この brs 分岐が発火したら指定フローはここで終わる」宣言

policy ステップはビルダーが **`scenarios[].evt → policies[].trg` マッチで自動挿入**するため、各 scenario の業務記述に集中できる。
記法例は SKILL.md「Event Flow」節と [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml) を参照。

### 参照規則

- **`narratives[].entry`** は `scenarios[].name` を指す（typo は `flow_chain_resolution` チェックで検出）
- **`scenarios[].next`** 値が dict のとき、キーは `narratives[].id` の集合のサブセットでなければならない
- **`scenarios[].brs[].next`** — branch ごとに連鎖を変える時はここに書く。**`sc.next` より優先される**
- **`scenarios[].brs[].terminal`** 値は `narratives[].id` のいずれか。`brs[].next` と同時指定は禁止（schema で not 制約）
- 順序は因果連鎖と整合させる（前 scenario の `evt` が後続 scenario の `cmd` まで policy 連鎖で繋がる）
- 同一 `ctx` の連続 sync ステップはビルダー側で 1 レーンに併合される。`ctx` 変化・policy ステップ・`trgs` join はそれぞれ HTML §2 の非同期矢印・sync-bar として描画される
- `next` 省略・`brs[].terminal` 一致いずれでフローを終端させてよい
- **複数 `narratives[].entry` が同一 scenario を指す場合**（happy と alt-X が同じ start scenario を共有）は、当該 scenario の `next` を **dict 形式** `{happy: ..., alt-X: ...}` にしてフロー別の継続先を分岐させる

### `kind` の使い分け（narratives[].kind）

| 値 | 用途 |
|---|---|
| `happy` | 主要フロー。1 セッションで原則 1 本 |
| `alt` | 代替シナリオ（例外パス・回避パス・補助フロー）。複数可 |

`kind` は分類ヒントで HTML 表示には影響しない。

### `decisions[]` の書き方

`decisions[]` は **「採用したもの + なぜ採用したか + 不採用にしたもの + なぜ採用しなかったか」を構造化して残す**。設計判断の歴史を引き継ぐためのログで、`[?]` の保留メモを「選択肢が揃ったら」昇格させる。
実例は [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml) の `decisions:` を参照。

### 各フィールドの書き方のコツ（必須/型は schema 参照）

| フィールド | 書き方のコツ |
|---|---|
| `topic` | 「何を決めたか」を 1 行で（CMD 名ではなく業務概念で） |
| `chosen` | `options[].name` のいずれかと完全一致（未確定なら `chosen: 未確定`） |
| `options[]` | 検討した全選択肢を書く。1 件しか書かないと「比較していない」シグナル |
| `options[].name` | 追跡用の識別子。`chosen` との突合や履歴参照のため **英語 slug（例: `10-days`, `hold-difference`）** を推奨 |
| `options[].label` | HTML 表示用の日本語ラベル（例: `10 日`）。あれば「label (name)」形式で並び読み下しやすい |
| `options[].why` / `why_not` | `rules[].why` と同様に **業務文脈** で書く。「実装が楽」だけでなく「業務的に何が違うか」を |
| `affects[]` | 影響を受ける AGG / BC / 要素名。実在突合は意味チェック（decision-rationale-clarity）が担う |
| `note` | 「決まったが後で見直す可能性のある条件」「関連する未決問題」等 |

### 「決められないとき」の扱い

意思決定が早すぎて確証が無い場合は **`chosen: 未確定`** で保留する。`options[]` だけ書いて理由を埋めておけば、後続セッションで再評価できる。これは `[?]` よりも一段構造化されており、品質チェックが「未確定 decision が長期残存」を検出する余地もある。
