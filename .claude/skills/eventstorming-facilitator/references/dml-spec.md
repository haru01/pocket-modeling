# DML（Domain Modeling Language）記法仕様

DDDモデリングのための情報圧縮言語。**YAML フォーマット**で記述する。
`ctxs`（BC 宣言）・`scs`（EVT を起点にした業務シナリオ）・`pols`（EVENTUAL-TX）の
3 つのトップレベルリストで 1 ドメインを表す。

**記法の原則**
- DML は **MD とは別の兄弟ファイル `docs/eventstorming/<session>.dml.yaml`** に **YAML 直書き**（フェンス不要）で保存する。`.md` の §9 はこの `.dml.yaml` へのリンク参照のみ。ビルダーは `.md` ＋ 兄弟 `.dml.yaml` から HTML を生成する。
  - （本仕様書内の ` ```dml ` フェンスは YAML 例の表示目的。実アーティファクトはフェンスなしの `.dml.yaml` ファイル。）
- トップレベルは `ctxs` / `scs` / `pols` の 3 リスト。**コメントによるセクション区切りは使わない**（リスト構造で自然に分離される）。
- `scs` / `pols` の各要素は `ctx:` フィールドで所属 BC を参照する。
- **識別子（`cmd` / `evt` / `agg` / `trg` / `emits` / `qry` の値）は英語 PascalCase**。`()` や `<<>>` は付けない。
- **`scs[].name` は日本語**で「アクター＋行為」を書く（例：`主催者がコミュニティを作成する`）。
- **`rules[].rule` の不変条件は英語**。日本語の補足は `why` / `when` / `note` の**構造化フィールド**へ書く（`#` 行コメントによる補足慣習は廃止）。
- BC（`ctxs[].name`）は `lowercase-with-hyphen` 形式、略さずに書く。
- キー順の推奨: `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`（YAML では強制ではないがスタイルとして統一する）。

**バージョンと後方互換（DML v2）**
- 本仕様は ContextMapper（CML）を参考にした **v2 拡張**を含む。拡張フィールド（`type` / `vision` / `resp` / `tech` / `sub` / `aggs` / `roles` / `prRoles` / `brMode` / `trgs` / トップレベル `domains`）は**すべて optional**。v1 記法（`ctxs` / `scs` / `pols` の 3 リストと既存フィールド）は **v2 でもそのまま永続的に valid**。
- 文法は **JSON Schema（Draft 2020-12）で機械検証**できる。スキーマ本体は [`./dml.schema.yaml`](./dml.schema.yaml)。検証は構文 validity のみを保証する（意味検証は causal-check / quality-check が担う。§9 参照）。

---

## 1. CONTEXT（BC 宣言）

```dml
ctxs:
  - name: <lowercase-with-hyphen>      # BC 名（略さない）
    lang:
      <EnglishTerm>: "<この文脈での意味（日本語可）>"
    mod: <module-name>
    up:                                # この BC が依存する側（参照するモデルの所有者）
      - ctx: <context-name>
        rel: Customer-Supplier         # Customer-Supplier | Conformist | Shared-Kernel | ACL
        note: "<任意の補足>"
    dn:                                # この BC に依存される側（このモデルを参照する下流）
      - ctx: <context-name>
        rel: Customer-Supplier
```

`lang` でユビキタス言語を定義する。
**同じ言葉が別 CONTEXT で意味が違う場合、それぞれの CONTEXT で別々に定義する**。
この差異が Bounded Context（BC）の境界を示す。

`up` / `dn` は BC 間の依存方向を明示する（必須）。**依存がない場合は空リスト `[]`** を書く。

例：
```dml
ctxs:
  - name: community-events
    lang:
      Event: "コミュニティが主催する集会・勉強会"
    mod: community-events
    up: []
    dn:
      - ctx: participation
        rel: Customer-Supplier
        note: "Event を下流 BC が参照"

  - name: participation
    lang:
      Event: "参加申込の対象となるエントリー"
    mod: participation
    up:
      - ctx: community-events
        rel: Customer-Supplier
    dn:
      - ctx: checkin
        rel: Customer-Supplier

  - name: checkin
    lang:
      CheckIn: "当日の来場確認"
    mod: checkin
    up:
      - ctx: participation
        rel: Customer-Supplier
    dn: []
```

### 1.1 リレーション語彙の拡充（v2・任意）

`rel`（粗い分類・人間向け）は従来どおり使える。より厳密に表現したいときは、CML 互換の
`roles`（自 BC 側の役割パターン）/ `prRoles`（相手 BC 側の役割パターン）を **任意で**併記する。
`up` / `dn` が既に方向（U/D）を示すので、`roles` から `U`/`D` は省略してよい。

| ショートコード | 意味 | | ショートコード | 意味 |
|------|------|---|------|------|
| `U` | Upstream | | `ACL` | Anti-Corruption Layer |
| `D` | Downstream | | `CF` | Conformist |
| `S` | Supplier | | `SK` | Shared Kernel |
| `C` | Customer | | `P` | Partnership |
| `OHS` | Open Host Service | | `PL` | Published Language |

```dml
up:
  - ctx: printing                # CML の [D,ACL]<-[U,OHS,PL] を表す
    roles: [ACL]                 # 自分（下流）側
    prRoles: [OHS, PL]           # 相手（上流）側
```

`rel` の enum は v1 の `Customer-Supplier` / `Conformist` / `Shared-Kernel` / `ACL` に加え、
`Partnership` / `Upstream-Downstream` / `Open-Host-Service` / `Published-Language` を追加。
**`rel` と `roles` はどちらか一方で十分**（両者の意味整合は quality-check が確認する）。

### 1.2 BC / 集約メタデータ（v2・任意）

`.md` 側（§4 の目的/背景、§5 の集約）にあった情報を DML に構造化できる。すべて optional。

```dml
ctxs:
  - name: event-planning
    type: FEATURE                 # FEATURE | APPLICATION | SYSTEM | MICROSERVICE
    vision: "イベントのライフサイクルとキャパシティを所有する"   # domainVisionStatement
    resp: [Event, Capacity, Schedule]                        # 文字列 or 文字列配列
    tech: "TypeScript, NestJS"                               # 任意
    sub: event-core               # §1.5 参照
    lang:
      Event: "単発の開催単位"
    mod: event-planning
    up: []
    dn: []
    aggs:                         # 任意。scs の agg を集約宣言で補足
      - name: Event
        purpose: "イベントのライフサイクルとキャパシティの単一の真実源"
        states: [DRAFT, PUBLISHED, CANCELLED, COMPLETED]     # 状態名は UPPER_SNAKE
```

`aggs[].states` を宣言すると、scs の rules / brs が参照する状態名との整合を
quality-check が検証できる。

---

## 1.5 Domain / Subdomain 分類（v2・任意）

戦略的設計の意図（コア／補完／汎用）を残したいとき、トップレベルに `domains` を **任意で**置く。
`domains` を書かなくても `ctxs[].sub` は単なるタグとして使える（漸進的にビジョンと
`type` を後から `domains` に集約できる）。

```dml
domains:
  - name: community-event-domain
    vision: "企画から当日参加までを一気通貫で支える"
    subs:
      - name: event-core
        type: CORE_DOMAIN          # CORE_DOMAIN | SUPPORTING_DOMAIN | GENERIC_SUBDOMAIN
        vision: "イベントの企画・公開・変更というコア価値"
      - name: payment
        type: GENERIC_SUBDOMAIN
        vision: "決済・返金。外部 PSP に委譲する汎用領域"
```

`subs[].name` と `ctxs[].sub` は同じ `lowercase-with-hyphen` 名前空間。
両者の突合（参照の実在）は quality-check が確認する。

---

## 2. インフラ系ドメインの扱い（通知・スケジューラ・決済・メール等）

業務ドメインと独立した技術基盤（通知・バッチ・外部 API 連携）は、**BC に昇格する**か**POLICY 内に留める**かを毎回判断する。デフォルト判断基準：

### POLICY 留置で十分なサイン
- 通知 / 連携が 1 種類のみ（例：承認通知のみ）
- 送信結果の監査・再送 / 失敗管理が不要
- 状態を持たない（送ったら完了で追跡しない）
- 他 BC から参照されない

→ 既存 BC の `pols` に POLICY を追加する。専用 CONTEXT は作らない。

### BC に昇格すべきサイン
- 複数種類の通知 / 連携を統一的に管理（例：APPROVAL / REMINDER / SURVEY / CANCELLATION など）
- 送信状態（QUEUED / SENT / FAILED / RETRYING）を持つ
- SLA・再送ポリシー・失敗時のフォールバックが業務要件
- 他 BC から「どの通知を送ったか」を参照される（監査ログ兼用など）

→ `ctxs` に新規 BC を宣言し、`up` / `dn` で他 BC との関係を明示する。

迷う場合は `note: "[?] ..."` で保留し、後続フェーズで再評価する。
**「データモデル（テーブル）は存在するが BC として宣言していない」状態は原則 NG**。

---

## 3. SCENARIO（EVT 起点で書く）

```dml
scs:
  - name: <アクター>が<何をする>      # 日本語。アクター＋行為
    ctx: <context-name>              # 所属 BC
    actor: <ActorName>               # 必須。Organizer / Member / System など
    qry:                             # 省略可。CMD 発行判断に必要な Read Model のみ
      - <QueryName>
    cmd: <CommandName>
    evt: <EventName>                 # 単一イベント。分岐する場合は brs を使う
    agg: <AggregateName>
    rules:
      - rule: <invariant in English>
        why: "<この不変条件が必要な業務・UX 上の理由（日本語可・推奨）>"
    errs:
      - cond: <condition>
        err: <ErrorType>
        when: "<このエラーが発生する状況の日本語説明（推奨）>"
    pol:                             # 後続 POLICY 参照（EVENTUAL-TX への接続）
      - <PolicyName>
```

**`why` / `when`（推奨）：** `rules[].why` でその不変条件が「なぜ必要か」を、`errs[].when` でエラー発生条件を機械可読に紐付ける。AI 実装エージェントが Issue から実装するときに意図を読み解きやすくなる。両方とも省略可（後方互換）だが強く推奨。

**`why` の書き方：** `rule` を**ユーザー影響・業務文脈**に翻訳する。
- NG: `why: "name の一意性を保つため"`（rule の言い換えで情報が増えていない）
- OK: `why: "URL slug や検索 UX で name→id 逆引きを想定するため"`（業務・UX 文脈で説明）

**集約が複数イベントを発火しうる場合（brs）：**
コマンドの処理結果に応じて発火イベントが変わる場合、`evt` の代わりに `brs` で分岐を書く。
分岐ごとに後続ポリシーが異なる場合は各 branch に `pol` を付ける（同一トランザクション内の SAME-TX 分岐）。

```dml
scs:
  - name: システムが在庫を確保する
    ctx: inventory
    actor: System
    cmd: ReserveInventory
    agg: Inventory
    rules:
      - rule: reserved quantity must not exceed available stock
        why: "在庫を超える引当を防ぐため"
    brs:
      - cond: "stock >= requested"
        evt: InventoryReserved
        pol: ConfirmOrder
      - cond: "stock < requested"
        evt: InventoryInsufficient
        pol: CancelOnOutOfStock
```

`brs` を使う場合、トップレベルの `evt` は省略する。`cond` に `>` `<` `=` を含む場合はクォートで囲む（YAML パースエラー回避）。

**分岐セマンティクス（`brMode`・v2・任意）：** `brs` は省略時 `exclusive`（排他・1 つだけ発火）。
CML の分岐演算子に対応した `brMode` を任意で明示できる。

| `brMode` | CML | 意味 | `cond` |
|------|-----|------|------|
| `exclusive`（既定） | `X` | 条件に応じて 1 つだけ発火 | 各分岐に必須（網羅・排他は quality-check が確認） |
| `concurrent` | `+` | すべて同時発火 | 省略可 |
| `inclusive` | `O` | 1 つ以上が発火 | 任意 |

```dml
  - name: システムが申込を確定し記録する
    ctx: ticketing
    actor: System
    cmd: ConfirmApplication
    agg: Application
    brMode: concurrent           # 両方必ず発火（cond 省略可）
    brs:
      - evt: ApplicationConfirmed
        pol: NotifyConfirmation
      - evt: AuditLogRecorded
```
`brMode` は `brs` がある時のみ意味を持つ（単独指定は不可）。

**name は日本語：** アクター（主催者/参加者/システム）＋行為を日本語で書く。「誰が何をするシナリオか」が一目でわかり、BC の責務やユーザーロールとの対応も明確になる。

**actor は必須：** コマンドを発行するアクターを明記する。典型値は `Organizer`（主催者）、`Member`（参加者）、`System`（システム/ポリシー）。

**なぜ EVT 起点か？** 「起きた事実」から始めることで、実装の都合（コマンドの存在・API の形）に引きずられず、ビジネスの本質的な流れを先に把握できる。

---

## 4. POLICY（EVENTUAL-TX 専用）

`pols` の各要素は **EVENTUAL-TX（非同期・別トランザクション）限定**で使用する。
同一トランザクションで処理される分岐（SAME-TX）は、発行元 SCENARIO の `brs` として書く（§3）。

```dml
pols:
  - name: <Name>
    ctx: <context-name>
    trg: <EventName>
    qry: <QueryName>          # BULK の場合は必須。単一宛先なら省略可
    cmd: <CommandName>        # 原則必須。副作用専用 POLICY は省略可
    bulk: true                # × n の場合（省略時は false）
    evt: <EventName>          # 省略可。このポリシーが生成するイベント
    note: "<任意の補足>"
```

- トランザクション種別フィールドは書かない（EVENTUAL 固定）。
- `qry` 必須基準: `bulk: true` のときは必須（送信対象リストを明示するため）。単一宛先が `trg` ペイロードから決まる場合は省略可。
- `cmd` 省略基準: **副作用専用 POLICY**（外部通知 / メール / プッシュ送信などの infrastructure 呼び出しで、内部 AGG を一切変更しないもの）に限り `cmd` を省略できる。この場合、対応する SCENARIO も書かない。AGG を更新する処理が含まれるなら必ず `cmd` と SCENARIO を書く。

**複数トリガーの join（`trgs`・v2・任意）：** 複数のイベントが揃って初めて起動する POLICY
（フロー DSL の `&>>` join に対応）は、`trg`（単一）の代わりに `trgs` を使う。
`trg` と `trgs` は排他（どちらか一方）。

```dml
pols:
  - name: FinalizeOnBothApprovals
    ctx: approval
    trgs:
      evts: [ManagerApproved, FinanceApproved]
      mode: concurrent          # exclusive | concurrent | inclusive（§3 と同じ語彙）
    cmd: Finalize
```

### 副作用専用 POLICY の例

```dml
pols:
  - name: NotifyOnEventRelocation
    ctx: event-planning
    trg: EventRelocated
    qry: GetConfirmedApplications
    bulk: true
    evt: ChangeNotified
    note: "会場変更時に既存参加者へ通知（メール送信のみ、状態遷移なし）"
```

対応フロー DSL は `$ポリシー *> [event]`（CMD なし）と書く。AGG への BULK CMD（`*> !cmd > [event]`）と視覚的に区別され、AGG の責務肥大化を防げる。

### SAME-TX と EVENTUAL-TX の判定

| TX | 書き方 | 根拠 |
|----|-------|------|
| SAME | SCENARIO の `brs` | コマンド内の同期処理。Repository のトランザクション境界内で完結 |
| EVENTUAL | `pols` の要素 | EventBus 経由の非同期処理。別トランザクションで発火 |

---

## 5. 記号の意味（付箋色との対応）

DML（YAML）の値は HTML レンダリング時に**役割ベースの意味色**でハイライトされる（付箋フロー図と同じパレット）。

| フィールド | 意味 | 付箋色 / 値の色 |
|------|------|--------|
| `evt` / `trg` / `emits` | ドメインイベント（起きた事実・過去形） | 橙 |
| `cmd` | コマンド（操作・意図） | 青 |
| `agg` / `actor` | 集約 / アクター | 黄 |
| `qry` | Read Model（CMD 発行前に参照するビュー） | 緑 |
| `pol` / POLICY の `name` | ポリシー | 紫 |
| `errs[].err` | エラー型（不変条件違反） | 赤 |
| キー名 | YAML キー | 淡い灰緑 |
| `note: "[?] ..."` | 未確認・迷い・設計判断が必要な箇所 | — |

### ` ```event-flow-svg ` フロー図記法

（フロー図 DSL は DML とは別のフェンス。YAML 化の対象外で従来どおり。）

| 記号 | 意味 | 付箋色 |
|------|------|--------|
| `\|BC名\|:` | Bounded Context レーン（ヘッダー行。説明を続けて書く） | — |
| `@アクター名` | アクター付箋 | 黄 |
| `?クエリ名` | Read Model 付箋 | 緑 |
| `[イベント名]` | イベント付箋 | 橙 |
| `$ポリシー名` | ポリシー付箋 | 紫 |
| `!コマンド名` | コマンド付箋（`!` 省略可） | 青 |
| `>` | 同期フロー（直接連鎖） | — |
| `>>` | 非同期遷移（レーン切り替え）。前レーン最後のフロー行の末尾に付ける | — |
| `*>` | BULK Fork 矢印。直後の CMD/EVT が N 個の並列インスタンスのうちの 1 つを代表 | — |
| `&>>` | Join + 非同期遷移。直前の N 個の EVT が 1 つの後続トリガーへ合流 | — |

`*>` / `&>>` は **BULK POLICY**（`bulk: true` を持つ POLICY）から発火する fanout / join を表現する場合にのみ使う。

---

## 6. `[?]`（未確認）の使い方

確信が低い箇所や設計判断が必要な箇所には、該当要素の `note` に `[?]` を付けて理由も書く。

```dml
scs:
  - name: 参加者がイベントに参加申込する
    ctx: participation
    actor: Member
    cmd: ApplyForEvent
    agg: Participation
    rules:
      - rule: capacity check
        note: "[?] Event 集約と Participation 集約どちらが定員を持つ？"
```

---

## 7. 記述ルール

1. **トップレベルは `ctxs` / `scs` / `pols` の 3 リスト**。セクション区切りコメントは使わない。
2. **キー順を推奨順で統一**: `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`。
3. **省略可能フィールド**: `qry` / `brs` / `bulk` / `pol` は必要なときだけ書く。
4. **qry は「判断に必要なデータ」にのみ書く**: アクター（「このコマンドを発行するか」）またはポリシー（「どのコマンドを発行するか・誰に対して」）が判断するために必要なデータのみ。コマンド実装内部で必要なデータ（BULK の実行対象リストなど）は `qry` に書かない。
5. **errs は積極的に書く**: 「起きない条件」を毎回確認して `errs` に記録する — エラーが AGG の不変条件を明らかにする。
6. **日本語補足は構造化フィールドへ**: `rules[].why` / `errs[].when` / `pols[].note` / 各要素の `note` に書く。`#` 行コメントによる補足は使わない。
7. **`why` は業務・UX 文脈に翻訳**: rule の言い換えではなく「なぜ必要か」を書く。
8. **完成時の発火/起動の明示**: 完成した SCENARIO は `evt` か `brs` の**いずれか一方**を、完成した POLICY は `trg` か `trgs` の**いずれか一方**を持つ（副作用専用 POLICY の cmd 省略は §4 のとおり別途許容）。スキーマは進行中セッションを許容するため両方欠如でも valid だが、完成版では必ず明示する。

---

## 8. フル例（コミュニティイベント参加ドメイン）

```dml
ctxs:
  - name: community-events
    lang:
      Event: "コミュニティが主催する集会・勉強会"
      Capacity: "イベントの定員（最大参加者数）"
    mod: community-events
    up: []
    dn:
      - ctx: participation
        rel: Customer-Supplier

  - name: participation
    lang:
      Event: "参加申込の対象となるエントリー"
      Capacity: "参加ステータスの枠（pending 含む）"
    mod: participation
    up:
      - ctx: community-events
        rel: Customer-Supplier
    dn: []

scs:
  - name: 主催者がコミュニティを作成する
    ctx: community-events
    actor: Organizer
    cmd: CreateCommunity
    evt: CommunityCreated
    agg: Community
    rules:
      - rule: communityName must be unique system-wide
        why: "URL slug や検索 UX で name→id 逆引きを想定するため"
      - rule: name and description must not be empty
      - rule: owner must always exist
    errs:
      - cond: duplicateName
        err: DuplicateCommunityNameError
      - cond: emptyName
        err: InvalidCommunityDataError
      - cond: emptyDescription
        err: InvalidCommunityDataError

  - name: 主催者がイベントを作成する
    ctx: community-events
    actor: Organizer
    cmd: CreateEvent
    evt: EventCreated
    agg: Event
    rules:
      - rule: event must belong to an existing community
      - rule: capacity must be positive integer
    errs:
      - cond: communityNotFound
        err: CommunityNotFoundError
      - cond: invalidCapacity
        err: InvalidCapacityError

  - name: 主催者がイベントを公開する
    ctx: community-events
    actor: Organizer
    cmd: PublishEvent
    evt: EventPublished
    agg: Event
    rules:
      - rule: event must be in DRAFT status
    errs:
      - cond: alreadyPublished
        err: EventAlreadyPublishedError

  - name: 主催者がイベントをキャンセルする
    ctx: community-events
    actor: Organizer
    cmd: CancelEvent
    evt: EventCancelled
    agg: Event
    rules:
      - rule: event must not have already occurred
        why: "開催済みイベントはキャンセル不可"
    errs:
      - cond: eventAlreadyOccurred
        err: EventAlreadyOccurredError
    pol:
      - NotifyEventCancelled

  - name: 参加者がイベントに参加申込する
    ctx: participation
    actor: Member
    qry:
      - GetRemainingCapacity
    cmd: ApplyForEvent
    agg: Participation
    rules:
      - rule: event must be published
      - rule: user must not have existing participation for same event
        why: "同一イベントへの二重申込を防ぐため"
    errs:
      - cond: eventNotPublished
        err: EventNotAvailableError
      - cond: duplicateParticipation
        err: AlreadyAppliedError
    brs:
      - cond: "capacity > 0"
        evt: ParticipationApplied
      - cond: "capacity = 0"
        evt: ParticipationWaitlisted

  - name: 主催者が参加申込を承認する
    ctx: participation
    actor: Organizer
    cmd: ApproveParticipation
    evt: ParticipationApproved
    agg: Participation
    rules:
      - rule: participation must be in APPLIED status
    errs:
      - cond: invalidStatus
        err: InvalidStatusTransitionError

  - name: 参加者が参加をキャンセルする
    ctx: participation
    actor: Member
    cmd: CancelParticipation
    evt: ParticipationCancelled
    agg: Participation
    rules:
      - rule: participation must be in APPLIED or APPROVED status
    errs:
      - cond: invalidStatus
        err: InvalidStatusTransitionError
    pol:
      - WaitlistPromotion

pols:
  - name: NotifyEventCancelled
    ctx: community-events
    trg: EventCancelled
    qry: AllApprovedParticipations
    cmd: SendCancellationNotification
    bulk: true
    evt: CancellationNotificationSent
    note: "イベントキャンセル時に参加者へ通知"

  - name: WaitlistPromotion
    ctx: participation
    trg: ParticipationCancelled
    qry: NextWaitlistedParticipation
    cmd: PromoteWaitlistEntry
    evt: WaitlistPromoted
    note: "キャンセル時にキャンセル待ちを繰り上げ（非同期・別トランザクション）"
```

---

## 9. JSON Schema による検証

DML は [`./dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12・YAML 記述）で
**構文 validity** を機械検証できる。検証ツールは `scripts/validate_dml.py`。

```bash
python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py docs/eventstorming/<session>.dml.yaml
```

- ビルダー（`eventstorming_build.py`）は `.dml.yaml` 読込時に検証し、HTML §9 にバナー
  （✅ / ⚠ 違反一覧）を描画する。**検証は非ブロッキング**で、違反があっても HTML は生成される。
- 全行コメントのみ（YAML→`None`）や空ファイルは「未記述」として検証対象外（進行中セッション許容）。

### 構文 validity と意味 validity の境界

| レイヤ | 担保するもの | 例 |
|------|------|------|
| **JSON Schema**（機械・決定論的） | 構文 validity。トップレベル 3 リスト＋任意 `domains`、各要素の必須フィールド、型、enum（rel / subdomainType / bcType / brMode）、識別子の PascalCase・lowercase-with-hyphen、`evt`↔`brs` 排他、`trg`↔`trgs` 排他、`bulk:true`→`qry` 必須、未知フィールド禁止 | `cmd` が PascalCase か、`sub.type` が enum 値か |
| **causal-check / quality-check**（LLM・文脈依存） | 意味 validity。参照の実在・因果整合・モデル品質 | `trg` が実在 EVT を指すか、`pol` が実在 POLICY か、up↔dn の双方向一致、`sub` 参照の突合、`aggs[].states` と分岐の整合、`rel` と `roles` の意味矛盾、分岐の MECE 性、`evt` の過去形・`cmd` の命令形 |

**スキーマ通過は必要条件であって十分条件ではない。** 「形が正しい」ことを Schema が、
「意味が正しい」ことを causal-check / quality-check が担保する。
