# DML（Domain Modeling Language）記法仕様 — 設計ガイドライン

DDD モデリングのための情報圧縮言語。**構文 validity（形が正しいか）は [`./dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12）で機械検証**する。本書は schema では表現できない**設計判断・記法哲学・慣習**を扱う。

- スキーマ通過は必要条件であって十分条件ではない。「形が正しい」ことを schema が、「意味が正しい」ことを causal-check / quality-check が担保する（§7）
- 検証: `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py docs/eventstorming/<session>.dml.yaml`
- フル例: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)（コミュニティイベント参加ドメイン・`narratives[]`（entry 付き）/ `decisions[]` を含む v6 参照例）

## v5: 散文系トップレベルフィールド

`.md` 廃止に伴い、旧 `.md` セクションが担っていた散文情報を DML 内部に統合した：

| 旧 .md セクション | v5 で追加された DML フィールド |
|---|---|
| ヘッダー（Session/Domain/Status/Goal） | `session: { id, domain, goal, status, started_at, html_link }` |
| §1 Happy Path Story + §2 代替シナリオ散文＋フロー定義 | `narratives[]`（v8 で統合）: `id` 必須・`kind` 必須 (`happy` \| `alt`) ・`prose` 必須・`title`/`entry` 任意。`kind:happy` が HTML §1 ストーリー先頭に、`kind:alt` が後続に並ぶ。`entry` 指定で §2 フロー図 1 行を駆動 |
| §4 次のアクション | `actions[]: { id, text, owner?, done? }` |
| §5 オープンクエスチョン | `questions[]: { id, topic, why, status: open\|closed, decision_id? }` |
| §7 BC 散文 | `contexts[].description: \|` Markdown 風散文 |
| §9 リードモデル候補 | `queries[]: { name, ctx, purpose, users, sources, formula }` |

> **v8 注記**: 旧トップレベル `story: |` キーは廃止。ハッピーパスは `narratives[]` に `kind: happy` のエントリとして書く。HTML も §1 ハッピーパスストーリー / §2 代替シナリオ の 2 セクションが §1 ストーリー 1 つに統合された。

各フィールドはすべて optional（進行中セッション中は欠落 OK）。AI からの編集は
`scripts/dmlctl.py` の `set/add/remove` を使うと round-trip でコメント・引用形式を維持できる。

---

## 0. 記法の原則

- **YAML 直書き・`.md` と兄弟ファイル**: `docs/eventstorming/<session>.dml.yaml` に純 YAML（フェンス不要）。`.md` の §10 はこの `.dml.yaml` へのリンク参照のみ。ビルダーは `.md` + 兄弟 `.dml.yaml` から HTML を生成する
- **トップレベルは 4 リスト + 任意 3 リスト**: `contexts` / `aggregates` / `scenarios` / `policies` 必須、`domains` / `flows` / `decisions` 任意。コメントによるセクション区切りは使わない（リスト構造で自然に分離される）
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

→ `contexts` に新規 BC を宣言し、`up` / `dn` で他 BC との関係を明示する。**`contexts[].lang` / `up` / `dn` は HTML §6 の LANGUAGE / 依存方向、および glossary_index（語彙の英→日変換）の唯一の真実源**（`.md` §7 や別の用語集セクションには書かない）。`.md` §7 は散文（境界の理由・含むシナリオ・目的・背景・制約）のみを担い、ビルダーが merge して描画する。

**`contexts[].lang` はカテゴリ別 dict-of-dicts**: 本 BC で扱う語彙を種別ごとに分類して英→日ラベル（短い表記）を与える。HTML §6 では制約の下にタイプ別表で描画される。

```yaml
contexts:
  - name: store-front
    lang:
      aggregates:    { Order: "注文", Quote: "概算見積" }
      vos:     { HoldAmount: "与信額" }
      actors:  { Member: "会員", System: "システム" }
      cmds:    { PlaceOrder: "注文を確定する" }
      evts:    { OrderPlaced: "注文された" }
      policies:    { AuthorizeOnOrderPlaced: "注文確定時に差額与信" }
      queries:    { GetEstimateAmount: "概算買取額" }
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

### `qry` は判断材料のみ

アクター（「このコマンドを発行するか」）またはポリシー（「どのコマンドを発行するか・誰に対して」）が**判断するために必要なデータ**のみ書く。コマンド実装内部で必要なデータ（BULK の実行対象リストなど）は `qry` に書かない。

### 分岐（`brs`）の使い所

コマンドの処理結果に応じて発火イベントが変わる場合、`evt` の代わりに `brs` で分岐を書く（同一トランザクション内の SAME-TX 分岐）。EVENTUAL-TX は `policies` で表現する（§3）。

`brMode` の語彙（`exclusive` 既定 / `concurrent` / `inclusive`）と構造は schema 参照。

### 内部 CMD（時刻駆動・コールバック・副作用）の書き方

業務アクター（会員・スタッフ）が直接発行しない CMD でも、AGG の状態を変える限り **scenario として書く** か **policy.cmd として実体化する** 必要がある。`dangling_cmd` チェック（v7）は両方を参照する。

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

### 複数トリガーの join（`trgs`）

複数のイベントが揃って初めて起動する POLICY は、`trg`（単一）の代わりに `trgs`（`evts` 配列 + `mode`）を使う。HTML §2 では **BPMN シンクバー（Σ N）** で描画される。

---

## 4. AGG（v3 トップレベル化）の設計意図

v2 までは `contexts[].aggs[]` 内に集約宣言を持っていたが、**v3 で AGG をトップレベル `aggregates[]` に切り出した**。`contexts[].aggs` は AGG 名（PascalCase 文字列）の**軽量名簿**として残る。

### なぜトップレベル化したか

- AGG は BC をまたいで参照される（quality-check / causal-check のグラフ起点）
- `transitions[].via`（CMD 名）と `scenarios[].cmd` を機械的に突合できる
- AGG の責務（`purpose` / `background` / `constraints` / `states` / `transitions` / `attrs` / `events`）を 1 ブロックで読める

### `aggregates[]` のフィールド構成（v4）

| フィールド | 型 | 役割 |
|---|---|---|
| `name` | PascalCase | AGG 識別子（必須） |
| `ctx` | lowercase-with-hyphen | 所属 BC（必須・所有者は 1 つ） |
| `purpose` | string | 「単一の責任主体として何のソース・オブ・トゥルースか」を 1 文で（必須・30 字以上推奨） |
| `background` | string | 「なぜ今この AGG を切り出すか・既存運用の何が痛いか」（任意・1〜3 文） |
| `constraints[]` | string list | 業務／法令／プラットフォーム由来の制約（任意・複数可） |
| `states` | upper_snake list | 状態名（DRAFT / PUBLISHED 等） |
| `transitions[]` | `{from,to,via,when?}` | 状態遷移。`via` は scenarios[].cmd と突合 |
| `attrs[]` | `{name,type,required?,note?}` | AGG ペイロード属性。HTML §7 で属性表として描画 |
| `events[]` | `{name, params[]?}` | この AGG が emit する EVT 宣言。`params[]` は `attrs[]` と同じ attribute 構造。HTML §7 でイベントペイロード表として描画 |

### 意味整合（quality-check が担保）

| 観点 | 突合 |
|---|---|
| 孤立 AGG / 未定義 AGG 参照 | `scenarios[].agg` ⇔ `aggregates[].name` |
| CMD が AGG 状態遷移に紐付くか | `scenarios[].cmd` ⇔ `aggregates[].transitions[].via` |
| EVT が AGG の宣言済み発火イベントか | `scenarios[].evt` ⇔ `aggregates[].events[].name` |
| BC 所有 AGG の双方向参照 | `contexts[].aggs`（名簿） ⇔ `aggregates[].ctx` |

スキーマは「`aggregates[].name` が PascalCase か」「`states` が UPPER_SNAKE か」までしか保証しない。**意味整合は quality-check / causal-check の責務**。

### AGG は所有 BC が 1 つ

複数 BC で参照される AGG でも `aggregates[].ctx` は 1 つに決める（所有者は 1 つ）。参照側 BC は up/dn の依存関係として表現する。

### transitions[] の初期化規約（v6・明示）

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

## 5. 付箋色との対応（DML 値のロール）

DML（YAML）の値は HTML レンダリング時に**役割ベースの意味色**でハイライトされる（付箋フロー図と同じパレット）。

| フィールド | 意味 | 付箋色 |
|------|------|--------|
| `evt` / `emits` / `brs[].evt` / `aggregates[].events[].name` | ドメインイベント（発生した事実・過去形） | 橙 |
| `trg` / `trgs.evts` | POL が購読するトリガ参照（発生 evt と区別） | Amber |
| `cmd` / `via` | コマンド（操作・意図） | 青 |
| `agg` / `actor` / `aggregates[].name` | 集約 / アクター | 黄 |
| `qry` | Read Model（CMD 発行前に参照するビュー） | 緑 |
| `pol` / POLICY の `name` | ポリシー | 紫 |
| `errs[].err` | エラー型（不変条件違反） | 赤 |
| `states` / `from` / `to` | 状態名（UPPER_SNAKE） | 黄（淡） |
| キー名 | YAML キー | 淡い灰緑 |

> **フロー図は DML から自動生成される**（手書きの記号 DSL は無い）。`narratives[].entry` を起点にビルダーが `scenarios[].next` を辿り、`scenarios[].evt → policies[].trg` のマッチで policy を自動挿入して Big Picture グリッドに描画する。詳細は [`./html-render-spec.md`](./html-render-spec.md) §5 参照。

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
| **JSON Schema**（機械・決定論的） | 構文 validity。トップレベル 4 リスト＋任意 `domains`/`flows`/`decisions`、各要素の必須フィールド、型、enum、識別子の PascalCase・lowercase-with-hyphen・UPPER_SNAKE（状態名）・camelCase（属性名）、`evt`↔`brs` 排他、`trg`↔`trgs` 排他、`bulk:true`→`qry` 必須、未知フィールド禁止 | `cmd` が PascalCase か、`sub.type` が enum 値か、`aggregates[].states` が UPPER_SNAKE か |
| **causal-check / quality-check**（LLM・文脈依存） | 意味 validity。参照の実在・因果整合・モデル品質 | `trg` が実在 EVT を指すか、`pol` が実在 POLICY か、up↔dn の双方向一致、`scenarios[].cmd` ↔ `aggregates[].transitions[].via` 整合、`scenarios[].evt` ↔ `aggregates[].events[].name` 整合、`narratives[].entry` / `scenarios[].next` / `brs[].terminal` の解決（→ `flow_chain_resolution` チェック）、`decisions[].affects[]` が実在要素を指すか、分岐の MECE 性、`evt` の過去形・`cmd` の命令形 |

**スキーマ通過は必要条件であって十分条件ではない。** ビルダー（`eventstorming_build.py`）は `.dml.yaml` 読込時に schema 検証し、HTML §9 にバナー（✅ / ⚠ 違反一覧）を描画する。**検証は非ブロッキング**で、違反があっても HTML は生成される。全行コメントのみ（YAML→`None`）や空ファイルは「未記述」として検証対象外（進行中セッション許容）。

---

## 8. 最小実例

```yaml
contexts:
  - name: community-events
    lang:
      aggregates:
        Event: "イベント"
      actors:
        Organizer: "主催者"
      cmds:
        PublishEvent: "イベントを公開する"
      evts:
        EventPublished: "イベントが公開された"
    mod: community-events
    up: []
    dn: []
    aggregates: [Event]

aggregates:
  - name: Event
    ctx: community-events
    purpose: "イベントのライフサイクルとキャパシティの単一の真実源"
    background: "現状はスプレッドシート手動運用で公開ステータスの曖昧さが申込導線の混乱を生んでいる"
    constraints:
      - "定員は 1 以上必須（個人情報保護法対象外データ）"
    states: [DRAFT, PUBLISHED, CANCELLED]
    transitions:
      - { from: DRAFT,     to: PUBLISHED, via: PublishEvent, when: "必須項目が揃いキャパシティ > 0" }
      - { from: PUBLISHED, to: CANCELLED, via: CancelEvent }
    attrs:
      - { name: eventId,  type: EventId, required: true }
      - { name: title,    type: string,  required: true }
      - { name: capacity, type: int,     required: true, note: "1 以上" }
    events:
      - name: EventPublished
        params:
          - { name: eventId, type: EventId }
          - { name: title,   type: string }
      - name: EventCancelled

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

flows:
  - id: happy
    title: ハッピーパス — イベントを公開する
    kind: happy
    steps:
      - 主催者がイベントを公開する
  - id: alt-cancel
    title: 代替シナリオ — イベントをキャンセルする
    kind: alt
    steps:
      - NotifyEventCancelled

decisions:
  - id: D1
    topic: 定員（capacity）はどの AGG が所有するか
    chosen: Event 集約に持たせる
    options:
      - name: Event 集約に持たせる
        adopted: true
        why: "公開時点で確定する属性で、Participation と独立に変更されるため Event のライフサイクルと同居が自然"
      - name: Participation 集約に持たせる
        why_not: "個別申込ごとに上限を計算し直す必要があり、整合性管理コストが高い"
    affects: [Event]
```

**コミュニティイベント参加ドメイン全体のフル例**: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)。

---

## 9. フロー連鎖（v6）と `decisions[]` の哲学

### なぜフロー連鎖が必要か

ドメインモデルには **ハッピーパス** に加えて **複数の代替シナリオ**（キャンセル・繰上待ち・エラー復旧 等）が存在する。それぞれが「どの scenarios/policies をどの順で辿るか」を明示的に残さないと、後で別パスを思い出して書き起こすときに必ず情報が落ちる。

v6 ではフロー定義を **3 つのフィールドに分散** して保持する：
- **`narratives[]`**: フロー識別子（`id`）・見出し（`title`）・種別（`kind`）・散文（`prose`）・開始 scenario（`entry`）
- **`scenarios[].next`**: フロー連鎖の継続先（string = 全フロー共通 / dict = フロー別）
- **`scenarios[].brs[].terminal`**: 「この brs 分岐が発火したら指定フローはここで終わる」宣言

policy ステップはビルダーが **`scenarios[].evt → policies[].trg` マッチで自動挿入**するため、各 scenario の業務記述に集中できる。

```yaml
narratives:
  - id: happy
    title: ハッピーパス — 申込から決済確定まで
    kind: happy
    entry: 主催者がイベントを作成する        # フロー開始 scenarios[].name
    prose: |
      <ハッピーパス散文>
  - id: alt-waitlist
    title: 代替シナリオ — 残席ゼロで繰上待ち
    kind: alt
    entry: 参加者がイベントに参加申込する    # 任意。指定なし → §2 描画は省略
    prose: |
      <代替シナリオ散文>

scenarios:
  - name: 主催者がイベントを作成する
    cmd: CreateEvent
    evt: EventCreated
    next: 参加者がイベントに参加申込する     # 全フロー共通

  - name: 参加者がイベントに参加申込する
    cmd: ApplyForEvent
    next: システムが申込を確定し監査記録する  # happy 系の継続先
    brs:
      - { cond: "...", evt: ParticipationApplied }
      - { cond: "...", evt: ParticipationWaitlisted, terminal: alt-waitlist }  # alt-waitlist 終端

  - name: 注文確定（分岐点の例）
    cmd: PlaceOrder
    evt: OrderPlaced
    next:                                    # フロー別に異なる時は dict
      happy: 旧機種発送
      alt-timeout: タイムアウト検知
```

### 参照規則

- **`narratives[].entry`** は `scenarios[].name` を指す（typo は `flow_chain_resolution` チェックで検出）
- **`scenarios[].next`** 値が dict のとき、キーは `narratives[].id` の集合のサブセットでなければならない
- **`scenarios[].brs[].next`** — branch ごとに連鎖を変える時はここに書く。**`sc.next` より優先される**（v7：両方のスクリプトが branch.next を最初に確認する）
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

```yaml
decisions:
  - id: D2
    topic: WAITLIST（繰上待ち）の管理単位
    chosen: Participation 集約の状態として持つ
    options:
      - name: Participation 集約の状態として持つ
        adopted: true
        why: "Event 集約に WAITLIST を持たせると申込キャンセルのたびに Event を更新する必要があり、Event の責務（ライフサイクル管理）から外れる"
      - name: 独立した Waitlist 集約を切り出す
        why_not: "繰上ロジックが Participation の状態遷移と密結合で、別 AGG にすると整合性管理のコストが高い"
      - name: 別 BC（waitlisting）に切り出す
        why_not: "通知 / 繰上 / キャンセル等の参加ライフサイクル管理は participation BC の責務内で十分。複雑性に見合う独立性が無い"
    affects: [Participation]
    note: "繰上の通知タイミング（CancellationDetected 直後 / 翌日バッチ）は別途要検討（H7 にて）"
```

### `decisions[]` の必須/推奨フィールド

| フィールド | 必須/推奨 | 書き方のコツ |
|---|---|---|
| `id` | 必須 | `D1` / `D2` のような連番、または `capacity-owner` のような slug |
| `topic` | 必須 | 「何を決めたか」を 1 行で（CMD 名ではなく業務概念で） |
| `chosen` | 必須 | `options[].name` のいずれかと完全一致（未確定なら `chosen: 未確定`） |
| `options[]` | 必須・1 件以上 | 検討した全選択肢。1 件しか書かないと「比較していない」シグナル |
| `options[].name` | 必須 | 追跡用の識別子。`chosen` との突合や履歴参照のため **英語 slug（例: `10-days`, `hold-difference`）** を推奨 |
| `options[].label` | 推奨 | HTML 表示用の日本語ラベル（例: `10 日`, `差額のみ仮押え`）。あれば「label (name)」形式で並び、識別子だけだと意味が取りにくい選択肢でも読み下せる |
| `options[].why` / `why_not` | 推奨 | `rules[].why` と同様に **業務文脈** で書く。「実装が楽」だけでなく「業務的に何が違うか」を |
| `options[].adopted` | 任意 | `chosen` との照合で自動判定されるが、明示すると意図がはっきりする |
| `affects[]` | 推奨 | 影響を受ける AGG / BC / 要素名（PascalCase or lowercase-with-hyphen）。causal-check C13 で実在突合 |
| `note` | 任意 | 「決まったが後で見直す可能性のある条件」「関連する未決問題」等 |

### 「決められないとき」の扱い

意思決定が早すぎて確証が無い場合は **`chosen: 未確定`** で保留する。`options[]` だけ書いて理由を埋めておけば、後続セッションで再評価できる。これは `[?]` よりも一段構造化されており、quality-check が「未確定 decision が長期残存」を検出する余地もある。
