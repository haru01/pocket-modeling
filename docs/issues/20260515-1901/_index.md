# Issue Index — Session 20260515-1901

Source: `docs/eventstorming/eventstorming-20260515-1901.md`

> **設計**: 大項目 = BC、中項目 = AGG。1 AGG Epic = 1 PR = AI エージェント 1 担当。
> CMD/QRY/受信 POLICY の詳細は各 Epic に inline。AGG 跨ぎは integration Issue で別建て。

## BC（大項目）× AGG（中項目）

### `bc:community`

UP: なし / DOWN: `bc:community`, `bc:ticketing`

- **`agg:Community`** → [Epic](epics/community__Community.md)  — 状態遷移 CMD 2 / 属性 CMD 2 / QRY 0

### `bc:event-planning`

UP: `bc:community` / DOWN: `bc:registration`, `bc:ticketing`, `bc:attendance`

- **`agg:Event`** → [Epic](epics/event-planning__Event.md)  — 状態遷移 CMD 4 / 属性 CMD 4 / QRY 4

### `bc:registration`

UP: `bc:event-planning` / DOWN: `bc:ticketing`

- **`agg:Application`** → [Epic](epics/registration__Application.md)  — 状態遷移 CMD 9 / 属性 CMD 2 / QRY 3

### `bc:ticketing`

UP: `bc:event-planning`, `bc:registration` / DOWN: `bc:registration`, `bc:attendance`

- **`agg:Ticket`** → [Epic](epics/ticketing__Ticket.md)  — 状態遷移 CMD 2 / 属性 CMD 1 / QRY 0
- **`agg:Payment`** → [Epic](epics/ticketing__Payment.md)  — 状態遷移 CMD 1 / 属性 CMD 0 / QRY 0
- **`agg:Refund`** → [Epic](epics/ticketing__Refund.md)  — 状態遷移 CMD 1 / 属性 CMD 0 / QRY 0

### `bc:attendance`

UP: `bc:ticketing`, `bc:event-planning` / DOWN: なし

- **`agg:Attendance`** → [Epic](epics/attendance__Attendance.md)  — 状態遷移 CMD 0 / 属性 CMD 0 / QRY 0

## AGG 跨ぎ統合 Issue（複数 AGG を跨ぐシナリオ）

- `integration/システムが返金を実行する.md` — [bc:ticketing][agg:Ticket+Refund] システムが返金を実行する
- `integration/参加者が会場で受付する.md` — [bc:attendance+ticketing][agg:Ticket+Attendance] 参加者が会場で受付する
- `integration/参加者がオンラインで参加する.md` — [bc:attendance+ticketing][agg:Ticket+Attendance] 参加者がオンラインで参加する

## BC 依存関係（再掲）

詳細は [dependency-graph.md](dependency-graph.md) を参照。
