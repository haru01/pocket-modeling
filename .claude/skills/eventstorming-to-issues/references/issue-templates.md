# Issue 本文テンプレート

すべての Issue 本文は以下の構造を厳密に守る。`gh issue view --json body` から再パース可能にするため、見出し名は固定。

設計原則: **1 AGG Epic = 1 PR = AI エージェント 1 担当。**CMD / QRY / 受信 POLICY / 発信 EVT の詳細はすべて AGG Epic 本文に inline。Sub-issue は持たない。

## AGG Epic Issue (self-contained)

```markdown
<!-- es-key: bc/<bc-slug>/agg/<AggName> -->

## 実装担当範囲
- **BC (大項目)**: `bc:<bc-slug>`
- **AGG (中項目)**: `agg:<AggName>`
- **スコープ**: この AGG の全 CMD / QRY / 受信 POLICY を 1 PR で実装
- **原則**: 1 AGG = 1 オーナー = 1 PR (AI エージェント 1 担当)
- **本 Epic 外**: AGG 跨ぎ統合 Issue で扱う処理は別 Issue

## Aggregate 概要
<日本語説明>

## ビジネス背景と制約

### 目的
<この AGG が「単一の責任主体」として担う責務を 1 文で（30字以上）。元 MD の §5 `#### 目的`>

### 背景
<なぜ今この AGG を切り出すか・現状運用の何が痛いか（1〜3 文）。元 MD の §5 `#### 背景`>

### 制約
- <業務／法令／プラットフォーム由来の制約> → RULE n / ERR `Name`
- <制約 2>

### BC 共通の方針 (`bc:<bc-slug>`)
- 目的: <BC レベルの戦略的判断（任意）>
- 制約:
  - <BC レベルで横断的な制約>

## スキーマ (Zod)

\`\`\`typescript
<Zod スキーマをそのまま転記>
\`\`\`

## 不変条件 (RULE)
- <invariant 1>
- <invariant 2>

## エラー (ERR)
- `ErrorName`: <説明>

## 状態モデル

状態: `A` | `B` | `C`

## 状態遷移 (State Transitions)

\`\`\`mermaid
stateDiagram-v2
    [*] --> A
    A --> B: TransitionY
    B --> C: TransitionZ
\`\`\`

## 状態遷移を起こす CMD（一覧）

| from | to | CMD | Issue | RULE |
|---|---|---|---|---|
| `A` | `B` | `TransitionY` | (未起票) | <RULE 概要> |

## 状態遷移を起こす CMD（詳細）

### `CmdName` — `FROM` → `TO`
- **由来シナリオ**: <SCENARIO 名>
- **アクター**: `<ActorName>`
- **発火 EVT**: `EvtName`
- **適用 RULE**:
  - <rule text 1>
    - **なぜ必要か**: <DML の RULE 直下に書かれた `WHY "..."`>
- **想定 ERR**:
  - <err text 1>
    - **発生条件**: <DML の ERR 直下に書かれた `WHEN "..."`>
- **連鎖 POLICY**: `PolicyA`, `PolicyB`

## 状態を変えない CMD（属性更新・一覧）

| CMD | 由来シナリオ | Issue |
|---|---|---|
| `UpdateX` | <SCENARIO 名> | (未起票) |

## 状態を変えない CMD（詳細）

### `CmdName`
- **由来シナリオ**: <SCENARIO 名>
- **発火 EVT**: `EvtName`
- **適用 RULE**: ...
- **想定 ERR**: ...

## QRY（読み出し口・詳細）

### `QryName`
- **目的**: <用途>
- **利用者**: <利用 POLICY / UI 等>
- **ソース**: <参照集約>
- **算出**: <ロジック>

## 受信 POLICY (inbound: 他 AGG / BC の EVT に反応してこの AGG の CMD を発火)

### `PolicyName` ⚠ **cross-BC**
- **TRIGGER EVT**: `EventName` ← `agg:SourceAgg` (`bc:source-bc`)
- **QRY** (BULK 対象選択): `QryName`
- **発火 CMD** (この AGG 内): `CmdName`
- **BULK**: true / false
- **発火 EVT**: `EvtName`
- メモ: <冪等性注意点 / Saga 注意点>
- **実装**: cross-BC は adapter/port パターンで分離

## 発信イベント (outbound: この AGG が発火する EVT とその消費先)

### EVT `EventName`
- **発火 CMD** (この AGG 内): `CmdName`
- **消費 POLICY**:
  - `PolicyA` → `agg:TargetAgg.CmdX` (`bc:target-bc`) ⚠ cross-BC
  - `PolicyB` → `agg:OtherAgg.CmdY`

## 副作用専用 POLICY (この AGG の EVT を観測、CMD は発火しない)

### `PolicyName`
- **TRIGGER**: `EvtName` (この AGG 発)
- **QRY**: `QryName`
- **観測 EVT**: `EvtName`
- メモ: <用途>
- 実装: 外部通知サービス等の adapter 経由、AGG 状態は変更しない

## 推奨モジュール構造

\`\`\`
src/<bc>/<aggregate>/
  index.ts       — Aggregate root + 不変条件
  schema.ts      — Zod schemas
  commands/      — 1 CMD = 1 file
  queries/       — 1 QRY = 1 file
  events.ts      — EVT 定義
  errors.ts      — ERR 定義
  policies.ts    — 受信 POLICY ハンドラ
tests/<bc>/<aggregate>/<aggregate>.spec.ts
\`\`\`

## 受け入れ条件
- [ ] Zod スキーマが Epic 記載と一致
- [ ] 状態遷移図の全エッジが実装されテストでカバー
- [ ] 全不変条件 (RULE) が enforce され、違反時に Epic 記載の ERR が発火
- [ ] 全 CMD / QRY が公開 API として動作
- [ ] 受信 POLICY 全件のハンドラが実装され、テストで TRIGGER EVT → CMD 発火が検証されている
- [ ] 発信 EVT 全件が CMD 成功時に確実に publish され、ペイロード schema が一致
- [ ] POLICY の冪等性（重複 EVT 受信時の重複 CMD 防止）がテストでカバー
- [ ] 上流 BC との依存が adapter / port パターンで分離（cross-BC POLICY 含む）
- [ ] AGG 跨ぎ統合 Issue で扱う処理は本 Epic 外（参照 link のみ）

## AGG 跨ぎ統合 Issue への参加
- `integration/<scenario>.md` — <SCENARIO 名>（他参加 AGG: `agg:OtherAgg`）

## Depends on
- 上流 BC: `bc:upstream-bc`
- 受信 POLICY 発生元 AGG: `agg:SourceAgg`
- 統合 Issue: `integration/<scenario>.md`

## Source
- セッション MD: `docs/eventstorming/eventstorming-<sid>.md`
```

## AGG 跨ぎ統合 SCENARIO Issue

```markdown
<!-- es-key: bc/<bc1>+<bc2>/scenario/<name-slug> -->

## 関係する BC
- `bc:bc1`
- `bc:bc2`

## 関係する集約
- `agg:Agg1` (Epic: #N)
- `agg:Agg2` (Epic: #N)

## 概要
<SCENARIO 本文。複数 AGG を跨ぐフローを記述>

## 構成要素
- CMD: `<CmdName>` (`agg:Agg1`)
- 連携: `agg:Agg1` → EVT → POLICY → CMD → `agg:Agg2`

## 受け入れ条件
- [ ] 全 CMD が成功時に正しい順序で発火される
- [ ] 部分失敗時の整合性が保たれる（補償トランザクション or eventual consistency）
- [ ] 参加 AGG Epic 完了後の E2E テストでフロー検証

## 前提
- 関係する AGG Epic がすべて完了済み

## Depends on
- 参加 AGG Epic 全件
```

## Cross-BC Saga Issue (将来拡張)

```markdown
<!-- es-key: bc/<bc1>->/<bc2>/saga/<name-slug> -->

## Triggers
- TRIGGER EVT: `EventName` (発生元 `agg:Agg1`)

## 関係する BC
- 上流: `bc:bc1`
- 下流: `bc:bc2`

## Saga ステップ
1. `agg:Agg1` → CMD `Cmd1` → EVT `Evt1`
2. POLICY `PolicyName` 受信 → `agg:Agg2` → CMD `Cmd2`
3. ...

## 補償トランザクション
- 失敗時: `agg:Agg2` → CMD `CompensateCmd` で `agg:Agg1` を逆遷移

## 受け入れ条件
- [ ] 正常系の全ステップが順序通り完了
- [ ] 各段階の失敗で補償が走り、整合性が保たれる
- [ ] Saga インスタンス管理（DB / Temporal / etc）の選択を明記
```
