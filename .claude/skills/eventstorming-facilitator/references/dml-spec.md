# DML（Domain Modeling Language）記法仕様 — 設計ガイドライン

DDD モデリングのための情報圧縮言語。**構文 validity（形が正しいか）は [`./dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12）で機械検証**する。本書は schema では表現できない**設計判断・記法哲学・慣習**を扱う。

- スキーマ通過は必要条件であって十分条件ではない。「形が正しい」ことを schema が、「意味が正しい」ことを causal-check / quality-check が担保する（§7）
- 検証: `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py docs/eventstorming/<session>.dml.yaml`
- フル例: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)（コミュニティイベント参加ドメイン・v3 文法）

---

## 0. 記法の原則

- **YAML 直書き・MD と兄弟ファイル**: `docs/eventstorming/<session>.dml.yaml` に純 YAML（フェンス不要）。`.md` の §9 はこの `.dml.yaml` へのリンク参照のみ。ビルダーは `.md` + 兄弟 `.dml.yaml` から HTML を生成する
- **トップレベルは 4 リスト**: `ctxs` / `aggs` / `scs` / `pols`（任意で `domains`）。コメントによるセクション区切りは使わない（リスト構造で自然に分離される）
- **識別子は英語 PascalCase**（`cmd` / `evt` / `agg` / `trg` / `qry` の値、`aggs[].name` 等）。`()` や `<<>>` は付けない
- **`scs[].name` のみ日本語**で「アクター＋行為」を書く（例: `主催者がコミュニティを作成する`）
- **`rules[].rule` の不変条件は英語**。日本語の補足は `why` / `when` / `note` の**構造化フィールド**へ書く（`#` 行コメントによる補足慣習は廃止）
- **BC 名は `lowercase-with-hyphen`**、略さずに書く
- **キー順の推奨**（`scs`）: `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`

詳細な型・必須フィールド・enum 値は schema を参照。

---

## 1. インフラ系ドメインの扱い（BC 昇格 vs POLICY 留置）

業務ドメインと独立した技術基盤（通知・バッチ・外部 API 連携・決済・メール等）は、**BC に昇格する**か**既存 BC の POLICY 内に留める**かを毎回判断する。

### POLICY 留置で十分なサイン

- 通知 / 連携が 1 種類のみ（例: 承認通知のみ）
- 送信結果の監査・再送 / 失敗管理が不要
- 状態を持たない（送ったら完了で追跡しない）
- 他 BC から参照されない

→ 既存 BC の `pols` に POLICY を追加する。専用 CONTEXT は作らない。

### BC に昇格すべきサイン

- 複数種類の通知 / 連携を統一的に管理（例: APPROVAL / REMINDER / SURVEY / CANCELLATION など）
- 送信状態（QUEUED / SENT / FAILED / RETRYING）を持つ
- SLA・再送ポリシー・失敗時のフォールバックが業務要件
- 他 BC から「どの通知を送ったか」を参照される（監査ログ兼用など）

→ `ctxs` に新規 BC を宣言し、`up` / `dn` で他 BC との関係を明示する。

迷う場合は `note: "[?] ..."` で保留し、後続フェーズで再評価する。**「データモデル（テーブル）は存在するが BC として宣言していない」状態は原則 NG**。

---

## 2. SCENARIO の哲学

### なぜ EVT 起点で書くか

「起きた事実」から始めることで、実装の都合（コマンドの存在・API の形）に引きずられず、ビジネスの本質的な流れを先に把握できる。

### `scs[].name` は日本語

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

コマンドの処理結果に応じて発火イベントが変わる場合、`evt` の代わりに `brs` で分岐を書く（同一トランザクション内の SAME-TX 分岐）。EVENTUAL-TX は `pols` で表現する（§3）。

`brMode` の語彙（`exclusive` 既定 / `concurrent` / `inclusive`）と構造は schema 参照。

---

## 3. POLICY の運用（EVENTUAL-TX）

`pols` の各要素は **EVENTUAL-TX（非同期・別トランザクション）限定**で使用する。同一トランザクションで処理される分岐（SAME-TX）は、発行元 SCENARIO の `brs` として書く。

### SAME-TX と EVENTUAL-TX の判定

| TX | 書き方 | 根拠 |
|----|-------|------|
| SAME | SCENARIO の `brs` | コマンド内の同期処理。Repository のトランザクション境界内で完結 |
| EVENTUAL | `pols` の要素 | EventBus 経由の非同期処理。別トランザクションで発火 |

### 副作用専用 POLICY の `cmd` 省略基準

**副作用専用 POLICY**（外部通知 / メール / プッシュ送信などの infrastructure 呼び出しで、内部 AGG を一切変更しないもの）に限り `cmd` を省略できる。この場合、対応する SCENARIO も書かない。AGG を更新する処理が含まれるなら必ず `cmd` と SCENARIO を書く。

```yaml
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

### bulk / qry の関係

`bulk: true` のとき `qry` 必須（送信対象リストを明示するため）。schema が機械検証する。単一宛先が `trg` ペイロードから決まる場合は `qry` 省略可。

### 複数トリガーの join（`trgs`）

複数のイベントが揃って初めて起動する POLICY（フロー DSL の `&>>` join に対応）は、`trg`（単一）の代わりに `trgs` を使う。構造と `mode` 語彙は schema 参照。

---

## 4. AGG（v3 トップレベル化）の設計意図

v2 までは `ctxs[].aggs[]` 内に集約宣言を持っていたが、**v3 で AGG をトップレベル `aggs[]` に切り出した**。`ctxs[].aggs` は AGG 名（PascalCase 文字列）の**軽量名簿**として残る。

### なぜトップレベル化したか

- AGG は BC をまたいで参照される（quality-check / causal-check のグラフ起点）
- `transitions[].via`（CMD 名）と `scs[].cmd` を機械的に突合できる
- AGG の責務（`purpose` / `states` / `transitions` / `attrs` / `events`）を 1 ブロックで読める

### 意味整合（quality-check が担保）

| 観点 | 突合 |
|---|---|
| 孤立 AGG / 未定義 AGG 参照 | `scs[].agg` ⇔ `aggs[].name` |
| CMD が AGG 状態遷移に紐付くか | `scs[].cmd` ⇔ `aggs[].transitions[].via` |
| EVT が AGG の宣言済み発火イベントか | `scs[].evt` ⇔ `aggs[].events[].name` |
| BC 所有 AGG の双方向参照 | `ctxs[].aggs`（名簿） ⇔ `aggs[].ctx` |

スキーマは「`aggs[].name` が PascalCase か」「`states` が UPPER_SNAKE か」までしか保証しない。**意味整合は quality-check / causal-check の責務**。

### AGG は所有 BC が 1 つ

複数 BC で参照される AGG でも `aggs[].ctx` は 1 つに決める（所有者は 1 つ）。参照側 BC は up/dn の依存関係として表現する。

---

## 5. 付箋色との対応（DML 値のロール）

DML（YAML）の値は HTML レンダリング時に**役割ベースの意味色**でハイライトされる（付箋フロー図と同じパレット）。

| フィールド | 意味 | 付箋色 |
|------|------|--------|
| `evt` / `trg` / `emits` / `brs[].evt` / `aggs[].events[].name` | ドメインイベント（起きた事実・過去形） | 橙 |
| `cmd` / `via` | コマンド（操作・意図） | 青 |
| `agg` / `actor` / `aggs[].name` | 集約 / アクター | 黄 |
| `qry` | Read Model（CMD 発行前に参照するビュー） | 緑 |
| `pol` / POLICY の `name` | ポリシー | 紫 |
| `errs[].err` | エラー型（不変条件違反） | 赤 |
| `states` / `from` / `to` | 状態名（UPPER_SNAKE） | 黄（淡） |
| キー名 | YAML キー | 淡い灰緑 |

> **フロー図 DSL**（`event-flow-svg` フェンスの `@$![]>>*>&>>`）は DML とは別の DSL。記号一覧と HTML 描画ルールは [`./html-render-spec.md`](./html-render-spec.md) §5-0 参照。

---

## 6. `[?]`（未確認）の慣習

確信が低い箇所や設計判断が必要な箇所には、該当要素の `note` に `[?]` を付けて理由も書く。進行中セッションを残しつつ、後続フェーズや次回セッションで再評価する。

```yaml
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

## 7. 検証の境界（構文 vs 意味）

| レイヤ | 担保するもの | 例 |
|------|------|------|
| **JSON Schema**（機械・決定論的） | 構文 validity。トップレベル 4 リスト＋任意 `domains`、各要素の必須フィールド、型、enum（`rel` / `subdomainType` / `bcType` / `brMode`）、識別子の PascalCase・lowercase-with-hyphen・UPPER_SNAKE（状態名）・camelCase（属性名）、`evt`↔`brs` 排他、`trg`↔`trgs` 排他、`bulk:true`→`qry` 必須、未知フィールド禁止 | `cmd` が PascalCase か、`sub.type` が enum 値か、`aggs[].states` が UPPER_SNAKE か |
| **causal-check / quality-check**（LLM・文脈依存） | 意味 validity。参照の実在・因果整合・モデル品質 | `trg` が実在 EVT を指すか、`pol` が実在 POLICY か、up↔dn の双方向一致、`scs[].cmd` ↔ `aggs[].transitions[].via` 整合、`scs[].evt` ↔ `aggs[].events[].name` 整合、分岐の MECE 性、`evt` の過去形・`cmd` の命令形 |

**スキーマ通過は必要条件であって十分条件ではない。** ビルダー（`eventstorming_build.py`）は `.dml.yaml` 読込時に schema 検証し、HTML §9 にバナー（✅ / ⚠ 違反一覧）を描画する。**検証は非ブロッキング**で、違反があっても HTML は生成される。全行コメントのみ（YAML→`None`）や空ファイルは「未記述」として検証対象外（進行中セッション許容）。

---

## 8. 最小実例

```yaml
ctxs:
  - name: community-events
    lang:
      Event: "コミュニティが主催する集会・勉強会"
    mod: community-events
    up: []
    dn: []
    aggs: [Event]

aggs:
  - name: Event
    ctx: community-events
    purpose: "イベントのライフサイクルとキャパシティの単一の真実源"
    states: [DRAFT, PUBLISHED, CANCELLED]
    transitions:
      - { from: DRAFT,     to: PUBLISHED, via: PublishEvent, when: "必須項目が揃いキャパシティ > 0" }
      - { from: PUBLISHED, to: CANCELLED, via: CancelEvent }
    attrs:
      - { name: eventId,  type: EventId, required: true }
      - { name: title,    type: string,  required: true }
      - { name: capacity, type: int,     required: true }
    events:
      - name: EventPublished
      - name: EventCancelled

scs:
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

pols:
  - name: NotifyEventCancelled
    ctx: community-events
    trg: EventCancelled
    qry: AllApprovedParticipations
    bulk: true
    evt: CancellationNotificationSent
    note: "副作用専用 POLICY（メール送信のみ・cmd 省略）"
```

**コミュニティイベント参加ドメイン全体のフル例**: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)（2 BC・複数 AGG・SCENARIO / POLICY を含む 190 行の参照モデル）。
