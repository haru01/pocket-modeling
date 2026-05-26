# 依存グラフ — Session 20260515-1901

> 自動生成。`build_dependency_graph.py` が再生成します。

## BC 依存関係

```mermaid
graph LR
    community["community"]
    event_planning["event-planning"]
    registration["registration"]
    ticketing["ticketing"]
    attendance["attendance"]
    community --> event_planning
    event_planning --> registration
    event_planning --> ticketing
    registration --> ticketing
    ticketing --> attendance
    event_planning --> attendance
```

## 集約別 状態遷移

### agg:Community （bc:community）

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PUBLISHED: 公開操作
    PUBLISHED --> ARCHIVED: CreateCommunity
```

### agg:Event （bc:event-planning）

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PUBLISHED: PublishEvent
    PUBLISHED --> CANCELLATION_REQUESTED: RequestEventCancellation
    CANCELLATION_REQUESTED --> CANCELLED: CompleteEventCancellation
    PUBLISHED --> COMPLETED: RescheduleEvent
```

### agg:Application （bc:registration）

```mermaid
stateDiagram-v2
    [*] --> APPLIED
    [*] --> WAITLISTED
    APPLIED --> CONFIRMED: 決済成功 チケット発行
    APPLIED --> EXPIRED: 決済失敗 or 決済期限切れ
    WAITLISTED --> PROMOTED: ConfirmContinuation
    PROMOTED --> CONFIRMED: 期限内決済成功
    PROMOTED --> EXPIRED: 決済期限切れ
    CONFIRMED --> CANCELLATION_REQUESTED: RequestApplicationCancellation
    CANCELLATION_REQUESTED --> CANCELLED: CompleteApplicationCancellation
    WAITLISTED --> CANCELLED: WithdrawFromWaitlist
    CONFIRMED --> PENDING_RECONFIRMATION: RequestApplicationCancellation
    PENDING_RECONFIRMATION --> CONFIRMED: ConfirmContinuation
    PENDING_RECONFIRMATION --> CANCELLATION_REQUESTED: 再同意せずキャンセル
```

### agg:Ticket （bc:ticketing）

```mermaid
stateDiagram-v2
    [*] --> ISSUED
    ISSUED --> USED: CheckInAtVenue
    ISSUED --> REFUNDED: ExecuteRefund
```

### agg:Payment （bc:ticketing）

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> COMPLETED: ExecutePayment
    PENDING --> FAILED: ExecutePayment
```

### agg:Refund （bc:ticketing）

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> COMPLETED: ExecuteRefund
    PENDING --> FAILED: ExecuteRefund
```

## AGG 跨ぎシナリオ

- **システムが返金を実行する**: `agg:Ticket`, `agg:Refund` → CMD `ExecuteRefund`
- **参加者が会場で受付する**: `agg:Ticket`, `agg:Attendance` → CMD `CheckInAtVenue`
- **参加者がオンラインで参加する**: `agg:Ticket`, `agg:Attendance` → CMD `JoinOnline`
