# [bc:attendance][agg:Attendance] Attendance 集約（受付・参加）

<!-- es-key: bc/attendance/agg/Attendance -->

## 実装担当範囲
- **BC (大項目)**: `bc:attendance`
- **AGG (中項目)**: `agg:Attendance`
- **スコープ**: この AGG の全 CMD / QRY / 受信 POLICY を 1 PR で実装
- **原則**: 1 AGG = 1 オーナー = 1 PR (AI エージェント 1 担当)
- **本 Epic 外**: AGG 跨ぎ統合 Issue で扱う処理は別 Issue（下記「AGG 跨ぎ統合 Issue への参加」参照）

## Aggregate 概要
受付・参加 集約。

## スキーマ (Zod)

```typescript
export const AttendanceIdSchema = z.string().uuid().brand<'AttendanceId'>();

export const AttendanceSchema = z.object({
  id: AttendanceIdSchema,
  ticketId: TicketIdSchema,
  eventId: EventIdSchema,
  memberId: MemberIdSchema,
  participationType: ParticipationTypeSchema,
  status: z.enum(['CHECKED_IN', 'JOINED_ONLINE']),
  recordedAt: z.date(),
});
export type Attendance = z.infer<typeof AttendanceSchema>;
```

## 不変条件 (RULE)
- 対応する Ticket は ISSUED 状態
- 受付時刻 (recordedAt) は Event の開催時間帯内
- 1 つの Ticket に対する Attendance は 1 つまで
- participationType は Ticket の participationType と一致する
- status は participationType に一致する（VENUE → CHECKED_IN、ONLINE → JOINED_ONLINE）

## エラー (ERR)
- `InvalidTicketError`: Ticket が ISSUED 状態でない
- `ParticipationTypeMismatchError`: Ticket の participationType と受付方法が不一致
- `NotTodayError`: 受付時刻が Event の開催時間帯外
- `AlreadyCheckedInError`: 既に受付済みの Ticket での二重受付

## 状態モデル

状態: （なし）

## 状態遷移 (State Transitions)



## 状態遷移を起こす CMD（一覧）

（なし）

## 状態遷移を起こす CMD（詳細）

（なし）

## 状態を変えない CMD（属性更新・一覧）

（なし）

## 状態を変えない CMD（詳細）

（なし）

## QRY（読み出し口・詳細）

（なし）

## 受信 POLICY (inbound: 他 AGG / BC の EVT に反応してこの AGG の CMD を発火)

（なし — この AGG は他 AGG/BC からの EVT 駆動を持たない）

## 発信イベント (outbound: この AGG が発火する EVT とその消費先)

### EVT `CheckedIn`
- **発火 CMD** (この AGG 内): `CheckInAtVenue`
- 消費 POLICY: （現状なし — 観測用 EVT、または下流未モデル）

### EVT `JoinedOnline`
- **発火 CMD** (この AGG 内): `JoinOnline`
- 消費 POLICY: （現状なし — 観測用 EVT、または下流未モデル）

## 推奨モジュール構造

```
src/<bc>/<aggregate>/
  index.ts       — Aggregate root + 不変条件
  schema.ts      — Zod schemas
  commands/      — 1 CMD = 1 file
  queries/       — 1 QRY = 1 file
  events.ts      — EVT 定義
  errors.ts      — ERR 定義
  policies.ts    — 受信 POLICY ハンドラ
tests/<bc>/<aggregate>/<aggregate>.spec.ts
```

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
- `integration/参加者が会場で受付する.md` — 参加者が会場で受付する（他参加 AGG: `agg:Ticket`）
- `integration/参加者がオンラインで参加する.md` — 参加者がオンラインで参加する（他参加 AGG: `agg:Ticket`）

## Depends on
- 上流 BC: `bc:ticketing`, `bc:event-planning`
- 統合 Issue: `integration/参加者が会場で受付する.md`, `integration/参加者がオンラインで参加する.md`

## Source
- セッション MD: `docs/eventstorming/eventstorming-20260515-1901.md`
