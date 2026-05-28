# EventStorming 風味のドメインモデリング - ミートアップ・プラットフォーム

- Session: eventstorming-20260515-1901
- Domain: meetup-platform
- Status: **フェーズ6 完了 / 整合性チェック反映済み（Q9-Q11 クローズ）**
- Goal: 主催者と参加者の両面プラットフォームとして、コミュニティ単位でミートアップを企画・運営し、有料／無料イベントの申込・決済・キャンセル待ち繰り上げ・返金までを一貫してモデリングする
- HTML ビュー: [../../dist/eventstorming/eventstorming-20260515-1901.html](../../dist/eventstorming/eventstorming-20260515-1901.html) （Python ビルダーが自動生成する派生ファイル）

### スコープ確定事項

- **両面プラットフォーム**: 主催者（コミュニティ運営）／参加者（メンバー）両方の体験を扱う
- **コミュニティ単位中心** (connpass / Doorkeeper 型): Community が第一級概念、Event はその下にぶら下がる
- **有料イベント含む**: 決済・チケット発行・返金あり
- **ハイブリッド対応**: オフライン会場が主、オンライン参加（配信URL）も併存（`participationType: VENUE | ONLINE`）
- **キャンセル待ち**: 繰り上げを含む（キャンセル発生・決済期限切れ・定員増枠の3経路）

### 設計上の主要判断（フェーズ3〜6 で確定）

- **申込状態の二段表現**: `Application` は申込受付 (`APPLIED`) → 決済完了で `CONFIRMED`。`ApplicationSubmitted` は暫定 EVT、`ApplicationConfirmed` を業務確定 EVT として明示
- **キャンセルの Saga 二段化**: `ApplicationCancellationRequested` → 返金完了後 `ApplicationCancellationCompleted`
- **イベント中止の Saga 二段化**: `EventCancellationRequested` → 全返金完了後 `EventCancellationCompleted`
- **イベント変更の属性別 CMD**: `RescheduleEvent`／`RelocateEvent`／`RepriceEvent` に分解
- **メンバー料金スナップショット**: `Ticket` に `memberAtPurchase: boolean` と `priceSnapshot` を保持。コミュニティ退会後も価格不変
- **再同意モデル**: 日時変更・料金変更は再同意必須、会場変更は通知のみ
- **繰り上げ決済期限**: 24 時間、上限回数なし
- **オンライン枠／会場枠**: 同一 Event AGG 内に `venueCapacity` ／ `onlineCapacity` を独立管理
- **開催完了**: 主催者の明示確定（`CompleteEvent` CMD）
- **コミュニティ退会と既存チケット**: 独立した状態（Ticket が `memberAtPurchase` を凍結保持）。専用 POLICY 不要

---

## 1) Happy Path Story

あるエンジニアが、勉強会を継続開催したいと考え、プラットフォーム上に **コミュニティ「大阪 DDD 勉強会」** を作成する。参加希望者は自由にコミュニティへ参加し、メンバーとなる。

主催者は次回イベントを企画する。タイトル・開催日時・**会場（定員 50 名）**・**オンライン配信枠（定員 200 名）**・参加費（一般 3,000 円／メンバー無料）を設定し、コミュニティメンバーに告知する形で公開する。

メンバー A はイベント詳細を見て、会場参加で申込み、クレジットカードで決済する。決済が完了するとチケットが発行され、A は正式な参加者となる。会場枠は早々に埋まり、メンバー B は会場枠に申込んだもののキャンセル待ちとなる。

開催 3 日前、別のメンバー C が体調不良で参加をキャンセルし、ポリシーに従い返金される。空いた 1 枠に対し、キャンセル待ち先頭の B が繰り上がり、決済期限付きで支払いを促される。B は期限内に支払い、参加が確定する。

開催当日、A は会場で受付チェックインし、オンライン枠の参加者は配信 URL から参加する。終了後、主催者はイベントを「開催済」とし、参加者には次回案内が届く。

---

## 2) 代替シナリオ

### 主催者によるイベント中止

主催者が開催日前にイベントを中止する判断をした。プラットフォームは全参加者の決済を一括返金し、参加者・キャンセル待ち全員に中止通知を送る。全返金完了をうけてイベントは正式に中止確定となり、コミュニティページにも中止履歴が残る。

### 決済期限切れによる自動キャンセル

参加者が申込後、決済期限（例：24時間）内に支払いをしなかった。プラットフォームは申込を自動取消し、キャンセル待ち先頭のメンバーを繰り上げ、決済依頼を送る。

### 定員増枠による繰り上げ

主催者が開催前に会場変更（より広い会場の確保）により定員を増やした。空いた枠の数だけキャンセル待ちが一括で繰り上げ対象となり、対象者に決済依頼が送られる。

### 主催者によるイベント情報の変更（日時・場所）

開催 5 日前、主催者が会場の手配ミスに気づき、開催日を 1 週間延期した（`RescheduleEvent`）。プラットフォームは申込済み参加者全員に変更通知を送り、参加者は「継続参加」または「キャンセル（全額返金）」を選択できる。会場変更だけ（`RelocateEvent`）の場合は通知のみで再同意不要。料金変更（`RepriceEvent`）の場合は再同意必須で、既存申込の価格は `Ticket` のスナップショットで保持される。変更日時で参加できない参加者がキャンセルすると、空いた枠に対しキャンセル待ちが繰り上がる。

### コミュニティ退会後の申込状態

メンバー A が「メンバー無料」枠でイベントに申込済みの状態で、コミュニティを退会した。プラットフォームのポリシーで、申込時点の参加権はそのまま有効（`Ticket` AGG の `memberAtPurchase` と `priceSnapshot` で過去のメンバー状態を凍結保持）として扱う。`Community` と `Ticket` は独立した状態を持つため、退会イベントから Ticket への伝播は不要。

---

## 3) Event Walkthrough

イベントフローは DML（`eventstorming-20260515-1901.dml.yaml` の `flows[]`）から自動生成される。
HTML ビュー（`dist/eventstorming/eventstorming-20260515-1901.html` §3）を参照のこと。

---

## 4) コンテキスト候補

### community（コミュニティ）

- 境界の理由: コミュニティの存続・メンバーシップ管理は、イベント単位の活動とライフサイクルが異なる（コミュニティは長期、イベントは単発）
- 含むシナリオ: `主催者がコミュニティを作成する`, `参加者がコミュニティに参加する`, `メンバーがコミュニティを退会する`
- **依存方向**:
  - UPSTREAM: (none)
  - DOWNSTREAM: (none) — Ticket がメンバー状態を **スナップショット** で凍結保持するため、退会後の伝播は不要。これにより community と ticketing は時間軸で疎結合
- LANGUAGE: `Community` — コミュニティの永続的なグループ（メンバー・主催者・公開設定を保有） / `Membership` — メンバーがコミュニティに属している状態

### event-planning（イベント企画）

- 境界の理由: 主催者がイベント本体（日時・会場・定員・料金）を企画・変更・中止する責務。参加者の申込状態とは独立してイベントのライフサイクルを管理
- 含むシナリオ: `主催者がイベントを作成する`, `主催者がイベントを公開する`, `主催者が日時を変更する`, `主催者が会場を変更する`, `主催者が料金を変更する`, `主催者が定員を増やす`, `主催者がイベント中止を要求する`, `システムが全返金完了でイベント中止を確定する`, `主催者がイベントを開催完了にする`
- **依存方向**:
  - UPSTREAM: community (Customer-Supplier — Event は Community に紐づく)
  - DOWNSTREAM: registration (Customer-Supplier), ticketing (Customer-Supplier — RefundAllOnEventCancellation 経由), attendance (Customer-Supplier)
- LANGUAGE: `Event` — 単発の開催単位（タイトル・日時・会場・定員・料金を保有） / `Capacity` — 会場枠 (`venueCapacity`) とオンライン枠 (`onlineCapacity`) の独立管理単位

### registration（申込）

- 境界の理由: 申込・キャンセル待ち・繰り上げの状態機械を集約。Event の定員（上流）と Ticket の決済結果（下流）の双方を参照しつつ、申込ステートマシンの一貫性を保つ
- 含むシナリオ: `参加者がイベント詳細を確認して参加を申し込む`, `参加者がキャンセルを要求する`, `参加者がキャンセル待ちを取下げる`, `システムが返金完了をうけてキャンセルを確定する`, `参加者が変更通知を受けて継続参加を選択する`, `システムがキャンセル待ちを繰り上げる`
- **依存方向**:
  - UPSTREAM: event-planning (Customer-Supplier)
  - DOWNSTREAM: ticketing (Customer-Supplier — 決済 Saga のトリガー)
- LANGUAGE: `Application` — 参加申込の状態を保持するエンティティ（`APPLIED` `CONFIRMED` `WAITLISTED` `PROMOTED` `PENDING_RECONFIRMATION` `CANCELLED` `EXPIRED`） / `Waitlist` — キャンセル待ち順序付きキュー（`participationType` 単位）

### ticketing（決済・チケット）

- 境界の理由: 外部決済と内部チケット発行・返金を集約。Application の状態遷移とは独立した決済状態機械（PAID / FAILED / REFUNDED）を管理。返金完了で Application の確定に戻すループあり
- 含むシナリオ: `システムが決済を実行する`, `システムがチケットを発行する`, `システムが申込を確定する`, `システムが返金を実行する`, `システムが期限切れの申込を取消す`
- **依存方向**:
  - UPSTREAM: event-planning (Customer-Supplier — 料金参照), registration (Customer-Supplier — ApplicationSubmitted 受信)
  - DOWNSTREAM: registration (Customer-Supplier — ApplicationConfirmed/Cancelled で逆方向通知), attendance (Customer-Supplier — Ticket 参照)
- LANGUAGE: `Ticket` — 確定参加権の証憑（`priceSnapshot` `memberAtPurchase` を凍結保持） / `Payment` — 外部決済の試行記録 / `Refund` — 返金の試行記録

### attendance（受付・参加）

- 境界の理由: 開催当日の参加確認のみ。Ticket の有効性検証と、`participationType` ごとの受付方法（会場チェックイン or オンライン参加）を扱う
- 含むシナリオ: `参加者が会場で受付する`, `参加者がオンラインで参加する`
- **依存方向**:
  - UPSTREAM: ticketing (Customer-Supplier — Ticket 検証), event-planning (Customer-Supplier — Event 日時・会場参照)
  - DOWNSTREAM: (none)
- LANGUAGE: `Attendance` — 当日の参加確認記録 / `CheckIn` — 会場チェックイン（VENUE 専用） / `OnlineJoin` — オンライン参加記録（ONLINE 専用）

---

## 5) 集約候補

### Community（コミュニティ）

- コンテキスト: `community`
- 関連シナリオ: `主催者がコミュニティを作成する`, `参加者がコミュニティに参加する`, `メンバーがコミュニティを退会する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Event（イベント）

- コンテキスト: `event-planning`
- 関連シナリオ: `主催者がイベントを作成する`, `主催者がイベントを公開する`, `主催者が定員を増やす`, `主催者が日時を変更する`, `主催者が会場を変更する`, `主催者が料金を変更する`, `主催者がイベント中止を要求する`, `システムが全返金完了でイベント中止を確定する`, `主催者がイベントを開催完了にする`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Application（申込）

- コンテキスト: `registration`
- 関連シナリオ: `参加者がイベント詳細を確認して参加を申し込む`, `参加者がキャンセルを要求する`, `参加者がキャンセル待ちを取下げる`, `システムが返金完了をうけてキャンセルを確定する`, `システムがキャンセル待ちを繰り上げる`, `参加者が変更通知を受けて継続参加を選択する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Ticket（チケット）

- コンテキスト: `ticketing`
- 関連シナリオ: `システムがチケットを発行する`, `システムが返金を実行する`, `参加者が会場で受付する`, `参加者がオンラインで参加する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Payment（決済）

- コンテキスト: `ticketing`
- 関連シナリオ: `システムが決済を実行する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Refund（返金）

- コンテキスト: `ticketing`
- 関連シナリオ: `システムが返金を実行する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

### Attendance（受付・参加）

- コンテキスト: `attendance`
- 関連シナリオ: `参加者が会場で受付する`, `参加者がオンラインで参加する`

属性・状態遷移・不変条件・エラーケースは DML（`aggs[].attrs[]`, `aggs[].states`, 各 `scs[].rules`/`errs`）が真実源。

---

## 6) リードモデル候補

### GetEventDetails（イベント詳細）
- **利用者**: 参加者（`参加を申し込む` の判断材料）
- **目的**: タイトル・日時・会場・残席・料金を一覧表示し、申込判断を可能にする
- **ソース**: `event-planning.Event` + `registration.Application` 集約（残席計算）
- **算出**: `venueRemaining = Event.venueCapacity − count(Application.status ∈ {APPLIED, CONFIRMED, PROMOTED} AND participationType = VENUE)`、ONLINE 枠も同様

### GetRemainingCapacity（残席数）
- **利用者**: 参加者（`参加を申し込む` の WHEN 分岐判断）と Application AGG 自身（不変条件チェック）
- **目的**: APPLIED/WAITLISTED の振り分けを決定する
- **ソース**: `Event` + `Application`
- **算出**: GetEventDetails と同じ計算式を `participationType` 別に算出

### GetWaitlistedApplications（キャンセル待ち一覧 BULK）
- **利用者**: POLICY `PromoteWaitlistOnCapacityIncrease`（増枠数分の繰り上げ対象を取得）
- **目的**: 定員増枠時に BULK 繰り上げする対象 Application のリストを取得
- **ソース**: `registration.Application`
- **算出**: `status = WAITLISTED AND eventId = ?` を `participationType` 別に `waitlistPosition ASC` でソートし、増枠数 N 件取得

### GetNextWaitlistedApplication（キャンセル待ち先頭）
- **利用者**: POLICY `PromoteWaitlistOnAvailability`（1 名繰り上げ）
- **目的**: 空席発生時に繰り上げる先頭 1 件を取得
- **ソース**: `registration.Application`
- **算出**: `status = WAITLISTED AND eventId = ? AND participationType = ?` を `waitlistPosition ASC` で 1 件取得

### GetConfirmedApplications（確定済み申込一覧 BULK）
- **利用者**: POLICY `RefundAllOnEventCancellation`, `ReconfirmOnEventReschedule`, `NotifyOnEventRelocation`, `ReconfirmOnEventReprice`
- **目的**: イベントの主要属性変更・中止時に通知 or 返金する対象を取得
- **ソース**: `registration.Application`
- **算出**: `status = CONFIRMED AND eventId = ?`

### GetPendingRefundsForEvent（イベント中止 Saga の残返金件数）
- **利用者**: POLICY `CompleteEventCancellationOnAllRefunded`（中止確定の判定）
- **目的**: 全 confirmed 申込のうち、まだ EventRefundCompleted が届いていない件数を取得（ゼロ件なら中止確定可）
- **ソース**: `event-planning.Event` + `ticketing.Refund`（reason = EVENT_CANCEL の COMPLETED 件数）
- **算出**: `count(Application[eventId=?, status=CONFIRMED at time of cancellation]) − count(Refund[eventId=?, reason=EVENT_CANCEL, status=COMPLETED])`

### GetStreamUrl（配信 URL）
- **利用者**: 参加者（`オンライン参加` の判断 — URL がないと参加できない）
- **目的**: オンライン参加者に配信 URL を提供
- **ソース**: `event-planning.Event.streamUrl` + 当該 Ticket の有効性
- **算出**: 単一ルックアップ + Ticket 検証

---

## 7) オープンクエスチョン

クローズ済み:
- [CLOSED] Q1. メンバー料金スナップショット → `Ticket` に `memberAtPurchase` と `priceSnapshot` を保持。退会後も価格不変
- [CLOSED] Q2. イベント変更時の再同意モデル → 日時 (`Reschedule`) と料金 (`Reprice`) は再同意必須、会場 (`Relocate`) は通知のみ
- [CLOSED] Q3. キャンセル待ち繰り上げの決済期限 → 24 時間、上限回数なし
- [CLOSED] Q4. オンライン枠／オフライン枠の集約境界 → 同一 Event AGG 内で `venueCapacity` / `onlineCapacity` を独立管理
- [CLOSED] Q5. 開催完了の自動／手動 → 主催者の明示確定（`CompleteEvent`）

残課題:
- Q6. 主催者譲渡・コミュニティ閉鎖時の既存イベントの扱い — 別セッションで扱う（今回スコープ外）
- Q7. 招待制・限定公開イベント — 別セッション
- Q8. 外部決済プロバイダの抽象化 — 実装フェーズで決定（Stripe / 他）

### 因果チェーン（自動検出）— 全件クローズ
- [CLOSED] Q9. 再同意依頼と変更通知の業務手順 → 再同意（日時/料金変更）は `registration` BC に `システムが再同意を要求する` SCENARIO を追加（CONFIRMED → PENDING_RECONFIRMATION の状態遷移を持つ）。一方、会場変更の通知（再同意不要）は AGG 更新を伴わないため、**副作用専用 POLICY** として `NotifyOnEventRelocation` を CMD/SCENARIO なし（TRIGGER + QRY + BULK + EVT のみ）で表現し、Application AGG を肥大化させない設計に整理
- [CLOSED] Q10. イベント中止の最終確定 → POLICY `CompleteEventCancellationOnAllRefunded` を追加。`EventRefundCompleted` をトリガーに残返金件数を QRY `GetPendingRefundsForEvent` で確認し、ゼロ件で `CompleteEventCancellation` を発行（実装は Saga インスタンス管理が必要）
- [CLOSED] Q11. 個別キャンセルとイベント中止の流れ分岐 → Refund SCENARIO に WHEN を追加し `reason` 別に `MemberRefundCompleted` / `EventRefundCompleted` を発行。`CompleteCancellationOnMemberRefund` POLICY は個別経由のみ受信し、`PromoteWaitlistOnCancellation` で繰り上げを起動。イベント中止経由は繰り上げを発火しない

---

## 8) 次のアクション

- 実装フェーズ移行: 集約ごとに DML `aggs[].attrs[]` を起点に型実装（TypeScript など）→ Repository → Application Service の順
- Saga の実装方針確定: EventBus + メッセージング基盤の選定（PostgreSQL Outbox / Redis Streams 等）
- POLICY の冪等性: `RefundOnApplicationCancellation` 等の二重起動防止策（イベント ID による重複排除）
- リードモデルの materialized view 戦略: Projection を別データストアにするか同 DB で view にするか
- 当日運用フロー: スマホ受付 UI / オンライン視聴ページの設計
- 未確定の Q6・Q7・Q8 を別セッションでモデリング

---

## 9) DML

DML 全文は別ファイル [`eventstorming-20260515-1901.dml.yaml`](./eventstorming-20260515-1901.dml.yaml)（YAML 直書き）に切り出した。HTML §9 にはこのファイルの内容が描画される。完全仕様: `.claude/skills/eventstorming-facilitator/references/dml-spec.md`。

---

## 10) 用語集

### アクター
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 主催者 | Organizer | コミュニティ作成・イベント企画・運営の主体 |
| 参加者 | Member | コミュニティに参加するエンドユーザー。受付前は「申込者」、受付後は「来場者」を意味する |
| システム | System | POLICY を実行する内部アクター（決済・通知・繰り上げ等） |

### コマンド
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| コミュニティを作成 | CreateCommunity | |
| コミュニティに参加 | JoinCommunity | |
| コミュニティを退会 | LeaveCommunity | |
| イベントを作成 | CreateEvent | |
| イベントを公開 | PublishEvent | |
| 定員を増やす | IncreaseCapacity | |
| 日時を変更 | RescheduleEvent | M2 対応で `UpdateEventInfo` から分解 |
| 会場を変更 | RelocateEvent | 同上 |
| 料金を変更 | RepriceEvent | 同上 |
| イベント中止を要求 | RequestEventCancellation | M1 対応で二段化（要求→完了） |
| イベント中止を確定 | CompleteEventCancellation | 全返金完了後にシステムが発行 |
| イベントを開催済にする | CompleteEvent | 主催者の明示確定 |
| 参加を申し込む | ApplyForEvent | |
| キャンセルを要求 | RequestApplicationCancellation | M1 対応で二段化 |
| キャンセル待ちを取下げ | WithdrawFromWaitlist | WAITLISTED 専用（返金不要） |
| キャンセルを確定 | CompleteApplicationCancellation | 返金完了後にシステムが発行 |
| キャンセル待ちを繰り上げ | PromoteWaitlistEntry | |
| 継続参加を選択 | ConfirmContinuation | |
| 決済を実行 | ExecutePayment | |
| チケットを発行 | IssueTicket | |
| 申込を確定 | ConfirmApplication | M4 対応で新設（業務確定 CMD） |
| 返金を実行 | ExecuteRefund | |
| 申込を期限切れにする | ExpireApplication | |
| 再同意を要求 | RequestReconfirmation | |
| イベント中止に伴い申込をキャンセル | CancelApplicationDueToEventCancel | BULK 実行・繰り上げ抑止 |
| 会場で受付 | CheckInAtVenue | |
| オンラインで参加 | JoinOnline | |

### イベント
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| コミュニティが作成された | CommunityCreated | |
| メンバーが参加した | MemberJoined | |
| コミュニティから退会した | MemberLeft | |
| イベントが作成された | EventCreated | |
| イベントが公開された | EventPublished | |
| 定員が増枠された | CapacityIncreased | |
| 日時が変更された | EventRescheduled | |
| 会場が変更された | EventRelocated | |
| 料金が変更された | EventRepriced | |
| イベント中止が要求された | EventCancellationRequested | Saga 起点 |
| イベント中止が確定した | EventCancellationCompleted | Saga 終点（全返金完了後） |
| イベントが開催済になった | EventCompleted | |
| 参加が申し込まれた | ApplicationSubmitted | 暫定（APPLIED 状態） |
| 参加がキャンセル待ちになった | ApplicationWaitlisted | |
| キャンセルが要求された | ApplicationCancellationRequested | Saga 起点 |
| キャンセル待ちが取下げられた | WaitlistEntryRemoved | |
| キャンセルが確定した | ApplicationCancellationCompleted | Saga 終点（返金完了後） |
| 繰り上げが行われた | WaitlistPromoted | |
| 継続参加が選択された | ContinuationConfirmed | |
| 決済が完了した | PaymentCompleted | |
| 決済が失敗した | PaymentFailed | |
| チケットが発行された | TicketIssued | |
| 申込が確定した | ApplicationConfirmed | 業務確定 EVT |
| 個別キャンセルの返金が完了した | MemberRefundCompleted | reason 別の Refund 完了 EVT。繰り上げ Saga を起動 |
| イベント中止経由の返金が完了した | EventRefundCompleted | reason 別の Refund 完了 EVT。中止確定 Saga を起動 |
| 申込が期限切れで取消された | ApplicationExpired | |
| 決済期限が経過した | PaymentDeadlinePassed | スケジューラが発行する時間 TRIGGER |
| 再同意が要求された | ReconfirmationRequested | |
| 変更が通知された | ChangeNotified | 副作用 POLICY の観測用 EVT（対応 CMD/AGG なし） |
| 申込がイベント中止により取消された | ApplicationCancelledDueToEventCancel | 繰り上げを発火しない別 EVT |
| 受付が完了した | CheckedIn | |
| オンライン参加が記録された | JoinedOnline | |

### ポリシー
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 申込決済処理 | ProcessPaymentForApplication | ApplicationSubmitted → ExecutePayment |
| 繰り上げ後の決済処理 | ProcessPaymentForPromotion | WaitlistPromoted → ExecutePayment（24h 期限） |
| 決済成功時のチケット発行 | IssueTicketOnPaymentSuccess | PaymentCompleted → IssueTicket |
| 決済失敗時の申込失効 | ExpireApplicationOnPaymentFailure | PaymentFailed → ExpireApplication |
| チケット発行時の申込確定 | ConfirmApplicationOnTicketIssued | TicketIssued → ConfirmApplication |
| キャンセル時の返金 | RefundOnApplicationCancellation | ApplicationCancellationRequested → ExecuteRefund (reason=MEMBER_CANCEL) |
| 個別返金完了時のキャンセル確定 | CompleteCancellationOnMemberRefund | MemberRefundCompleted → CompleteApplicationCancellation |
| キャンセル確定時の繰り上げ | PromoteWaitlistOnCancellation | ApplicationCancellationCompleted → PromoteWaitlistEntry |
| 期限切れ時の繰り上げ | PromoteWaitlistOnExpiration | ApplicationExpired → PromoteWaitlistEntry |
| 増枠時の BULK 繰り上げ | PromoteWaitlistOnCapacityIncrease | CapacityIncreased → PromoteWaitlistEntry (BULK) |
| 日時変更時の再同意要求 | ReconfirmOnEventReschedule | EventRescheduled → RequestReconfirmation (BULK) |
| 料金変更時の再同意要求 | ReconfirmOnEventReprice | EventRepriced → RequestReconfirmation (BULK) |
| 会場変更時の通知 | NotifyOnEventRelocation | EventRelocated → 副作用で各 confirmed Application へ通知（BULK・CMD/AGG なし）→ ChangeNotified |
| 中止時の一括返金 | RefundAllOnEventCancellation | EventCancellationRequested → ExecuteRefund (BULK, reason=EVENT_CANCEL) |
| 全返金完了時の中止確定 | CompleteEventCancellationOnAllRefunded | EventRefundCompleted（全件完了）→ CompleteEventCancellation |
| 中止確定時の申込一括キャンセル | CancelApplicationsOnEventCancellation | EventCancellationCompleted → CancelApplicationDueToEventCancel (BULK) |
| 決済期限切れ検出 | ExpireApplicationOnPaymentDeadline | スケジューラ TRIGGER (PaymentDeadlinePassed) → ExpireApplication |

### リードモデル
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| イベント詳細 | GetEventDetails | 申込判断（タイトル・日時・会場・料金・残席） |
| 残席数 | GetRemainingCapacity | 申込時の APPLIED/WAITLISTED 振り分け判断 |
| キャンセル待ち一覧 | GetWaitlistedApplications | BULK 繰り上げ対象（増枠時） |
| キャンセル待ち先頭 | GetNextWaitlistedApplication | 1 名繰り上げ対象（空席発生時） |
| 確定済み申込一覧 | GetConfirmedApplications | BULK 通知/返金対象 |
| 配信URL | GetStreamUrl | オンライン参加判断 |
| 残返金件数 | GetPendingRefundsForEvent | イベント中止 Saga 完了判定 |

---

## 再開ポイント

- セッション完了: フェーズ6（最終出力 + 整合性チェック + Q9-Q11 修正）まで完了
- スコープ完結: 5 BC × 35 SCENARIO × 16 POLICY × 7 AGG（Community / Event / Application / Ticket / Payment / Refund / Attendance）× 7 リードモデル
- Saga 一覧（全 5 系統）:
  1. **申込 Saga**: ApplicationSubmitted → Payment → Ticket → ApplicationConfirmed
  2. **キャンセル Saga**: ApplicationCancellationRequested → MemberRefund → CompleteCancellation → PromoteWaitlist
  3. **イベント中止 Saga**: EventCancellationRequested → BULK EventRefund → CompleteEventCancellation → BULK CancelApplications
  4. **繰り上げ Saga**: WaitlistPromoted → Payment（24h 期限）→ Confirmed or Expired
  5. **失効 Saga**: PaymentDeadlinePassed → ExpireApplication → PromoteWaitlist
- 残課題（別セッション推奨）: Q6（主催者譲渡・コミュニティ閉鎖）/ Q7（招待制イベント）/ Q8（外部決済プロバイダ抽象化）
- 残ホットスポット（M3）: `Application.PENDING_RECONFIRMATION` の名称 / `Ticket.USED` の遷移 CMD — 実装フェーズで命名再考の余地あり
