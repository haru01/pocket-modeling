# EventStorming 風味のドメインモデリング - ミップカメラ 下取り可能オンラインストア

- Session: eventstorming-20260525-1331
- Domain: ミップカメラ オンラインストア（下取り交換 + ポイント優遇）
- Status: **フェーズ4 完了（DML 生成済み）/ フェーズ5-6（属性・不変条件/エラー詳細化）未了**
- Goal: 購入フローの中で下取り交換を選べ、下取り承認時に残金決済とポイント優遇付与が走るドメインモデルを構築する
- HTML ビュー: [../../dist/eventstorming/eventstorming-20260525-1331.html](../../dist/eventstorming/eventstorming-20260525-1331.html) （Python ビルダーが自動生成する派生ファイル）

---

## 1) Happy Path Story

佐藤さんは、新しいフルサイズ一眼カメラ（200,000 円）の購入を検討している。ミップカメラのオンラインストアで目当ての機種をカートに入れ、決済画面で「下取り交換を利用する」を選んだ。手持ちの旧カメラの型番・付属品・外観コンディションを申告すると、システムから概算下取り見積もり 95,000 円が即時提示された。佐藤さんは過去の購入で貯めたポイント残高から 10,000 ポイント（= 10,000 円相当）の使用も指定し、注文を受け付けてもらった。このとき購入カメラはまだ発送されない。

翌日、ミップカメラから集荷キット（らくらくキット）の段ボールが届いた。佐藤さんは旧カメラを梱包して発送した。

ミップカメラの査定担当が品物を受領し、実機査定を行った結果、申告通りの状態だったため本査定額は概算と同じ 95,000 円で確定。佐藤さんに承認依頼が通知された。佐藤さんが承認すると、購入が確定し、指定した 10,000 ポイントが消費され、残金 95,000 円（= 200,000 − 95,000 − 10,000）は登録済みクレジットカードで決済された。購入カメラが発送される。

同時にポイント計算ロジックが走った。下取り交換利用の優遇 +10%、開催中の「春の買い替えキャンペーン」適用 +5% が積算され、購入金額 200,000 円に対して合計 15% = 30,000 ポイントが付与された。佐藤さんのポイント残高は、消費分を差し引き付与分が加算されて更新された。

---

## 2) 代替シナリオ

### Alt-1: 査定が見積もりより下がった（不一致）→ 客が再判断

佐藤さんは概算見積もり 95,000 円で注文確定したが、本査定の結果、実機にスレ・薄キズが見つかり本査定額は 82,000 円に減額された。ミップカメラから「査定額が変動しました」と通知が届く。佐藤さんは (a) 減額された額で承認する／(b) 下取りをキャンセルして品物を返送してもらう／(c) 下取りなしで購入だけ進める（残金 = 購入額全額をクレカ決済）から選ぶ。佐藤さんは (a) を選び、82,000 円を充当して購入完了。ポイントは購入金額ベースで計算され付与される。

### Alt-2: 客が査定を拒否（キャンセル）→ 全体取消

佐藤さんは Alt-1 と同じ状況で、減額に納得できず (b) キャンセル を選択。下取り品は佐藤さんへ返送される（送料は客負担）。購入注文も自動的にキャンセルされ、課金は発生しない。ポイントも付与されない。

### Alt-3: 査定差異あり → 下取りだけキャンセルして購入は続行

佐藤さんは減額された 82,000 円も受け入れられないが、購入は予定通り進めたい。(c) 下取りキャンセルして購入だけ進める を選択。下取り品は客負担で返送、購入カメラの残金は購入額全額をクレカ決済して発送される。下取り優遇 +10% は適用されず、キャンペーン分 +5% のみのポイント付与となる。

### Alt-4: キャンペーン期間外の通常購入

ハッピーパスとほぼ同じ流れだが、注文時点でキャンペーンが開催されていない。下取り優遇 +10% のみ適用され、合計 10% のポイント付与で完了。

---

## 3) Event Walkthrough

イベントフローは DML（`<session>.dml.yaml` の `flows[]`）から自動生成される。
HTML ビュー（`dist/eventstorming/<session>.html` §3）を参照のこと。

---

## 4) コンテキスト候補

> **命名規約**: `### english-slug（日本語名）` 形式。HTML レンダー時にこの全体が `<h3>` に表示される。

サブドメイン分類（DML `domains`）: `trade-in-core`（CORE）/ `loyalty-program`（CORE）/ `purchasing`（SUPPORTING）。

### store-front（店舗フロント）

商品閲覧・カート・注文・購入確定・在庫引当・残金決済・発送を所有。サブドメイン `purchasing`。

- **UPSTREAM**: `trade-in`（Partnership）, `loyalty`（Customer-Supplier）
- **DOWNSTREAM**: なし
- 集約: `Cart` / `Order` / `Inventory` / `Payment`

### trade-in（下取り交換）

申告・概算見積もり・集荷・受領・本査定・承認/キャンセルを所有。サブドメイン `trade-in-core`（差別化の中核）。

- **UPSTREAM**: なし
- **DOWNSTREAM**: `store-front`（Partnership）
- 集約: `TradeIn` / `Appraisal`

### loyalty（ポイント優遇）

ポイント消費・付与・返戻とキャンペーン管理を所有。サブドメイン `loyalty-program`。

- **UPSTREAM**: なし
- **DOWNSTREAM**: `store-front`（Customer-Supplier）
- 集約: `PointAccount` / `Campaign`

---

## 5) 集約候補

> 目的・状態は DML `aggs[]` と対応。属性（`aggs[].attrs[]`）・不変条件（`scs[].rules[]`）の詳細化はフェーズ5-6（未了）。

### Cart（カート） — store-front
- **目的**: 購入前の商品選択を保持する。状態: `ACTIVE → CHECKED_OUT`

### Order（注文） — store-front
- **目的**: 下取り・ポイントを含む購入注文のライフサイクルの単一の真実源。状態: `PLACED → PURCHASE_CONFIRMED → COMPLETED` / `CANCELLED`

### Inventory（在庫） — store-front
- **目的**: 購入確定時の在庫引当・解放を管理。状態: `AVAILABLE → ALLOCATED → RELEASED`

### Payment（決済） — store-front
- **目的**: 残金決済の状態を管理。状態: `PENDING → SETTLED` / `FAILED`

### TradeIn（下取り） — trade-in
- **目的**: 下取り交換プロセス（概算→発送→受領→承認/取消）の単一の真実源。状態: `ESTIMATED → KIT_SHIPPED → ITEM_SHIPPED → RECEIVED → APPROVED` / `CANCELLED` / `EXPIRED` / `TIMED_OUT` / `RETURNED`

### Appraisal（査定） — trade-in
- **目的**: 受領後の本査定の状態の単一の真実源。状態: `PENDING → COMPLETED`（/ `DISCREPANCY → REVISED`）→ `APPROVED`

### PointAccount（ポイント口座） — loyalty
- **目的**: 顧客のポイント残高と消費・付与・返戻の単一の真実源（残高ベース）

### Campaign（キャンペーン） — loyalty
- **目的**: ポイント優遇キャンペーンの期間とライフサイクル。状態: `SCHEDULED → ACTIVE → ENDED`

---

## 6) リードモデル候補

> 単一集約への単純ルックアップは省略。判断材料となる Read Model のみ記載。

### GetTradeInEstimate（下取り概算の参照） — trade-in
- 利用者: 客（注文時）／ 目的: 注文確定時に概算下取り額と有効期限を確認 ／ ソース: TradeIn ／ 算出: 申告内容に基づく概算額・期限

### GetPointBalance（ポイント残高の参照） — loyalty
- 利用者: 客（注文時）／ 目的: 使用指定ポイントが残高内か判断 ／ ソース: PointAccount ／ 算出: 現在残高

### GetOutstandingBalance（残金の参照） — store-front
- 利用者: System（残金決済時）／ 目的: 決済すべき残金を算出 ／ ソース: Order + TradeIn + PointAccount ／ 算出: 購入額 − 下取り額 − 使用ポイント

### GetApplicableBonusRate（付与率の参照） — loyalty
- 利用者: System（ポイント付与時）／ 目的: 付与率を決定 ／ ソース: Order（下取り有無）+ Campaign（期間内か）／ 算出: 下取り +10% ＋ キャンペーン +5%

---

## 7) オープンクエスチョン

- Q1. 概算見積もりロジックは「申告内容に対する辞書ルックアップ」か「機械学習モデル」か？ — 決まると: trade-in BC 内の見積もり責務の重さが変わる
- Q2. 残金決済が失敗した場合の補償フローは？（査定承認済みだが課金失敗） — 決まると: store-front の購入確定 POLICY にエラーパスが追加
- Q3. キャンペーンは「期間 × 機種」か「期間のみ」か？ — 決まると: Campaign AGG の属性数が変わる
- Q4. 下取り品の所有権がミップカメラに移るのはどのイベント時点？（受領時 / 承認時） — 決まると: 法的観点で TradeIn の状態遷移が変わる

---

## 8) 次のアクション

- フェーズ3: 上記フロー DSL から拾った EVT 一覧をユーザーと確認、抜け漏れを補完
- フェーズ4: CMD-EVT-POLICY チェーンの細部詰め（BC 越境ポリシーの同期/非同期判定）

---

## 9) DML

DML 全文は別ファイル [`eventstorming-20260525-1331.dml.yaml`](./eventstorming-20260525-1331.dml.yaml)（YAML 直書き）に保持する。§3 フロー DSL から生成済み（3 BC・27 SCENARIO・19 POLICY、v2 文法: domains/subdomain/BCメタ/aggregates/branchMode を使用）。HTML §9 にその内容が描画される。完全仕様: `.claude/skills/eventstorming-facilitator/references/dml-spec.md`。

---

## 10) 用語集

### アクター
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 客 | Customer | 購入者・下取り依頼者 |
| 査定担当 | Appraiser | 下取り品の受領・実機査定を担当 |
| 発送スタッフ | ShippingStaff | 集荷キット・購入品・返送品の物流を担当 |
| マーケティング担当 | MarketingStaff | キャンペーンの開始・終了を運営 |

### コマンド
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 商品をカートに入れる | AddItemToCart | |
| 下取り品を申告する | DeclareTradeInItem | 機種・付属品・状態を申告 |
| 下取り付きで注文する | PlaceOrderWithTradeIn | 概算下取り額充当の前提で注文を受け付ける |
| 集荷キットを発送する | ShipPickupKit | らくらくキット |
| 下取り品を発送する | ShipTradeInItem | 客が梱包して発送 |
| 下取り品を受領する | ReceiveTradeInItem | |
| 本査定を実施する | PerformAppraisal | |
| 査定承認を依頼する | RequestAppraisalApproval | |
| 査定を承認する | ApproveAppraisal | |
| 減額を承認する | ApproveReducedAppraisal | Alt-1 |
| 再見積もりを提示する | PresentRevisedQuote | Alt-1〜3 共通 |
| 下取りをキャンセルする | CancelTradeIn | Alt-2 |
| 下取りのみキャンセルする | CancelTradeInOnly | Alt-3（注文は継続） |
| 下取り品を返送する | ReturnTradeInItem | 送料客負担 |
| 注文をキャンセルする | CancelOrder | Alt-2/7/8 |
| 購入を確定する | ConfirmPurchase | |
| 在庫を引き当てる | AllocateInventory | 購入確定直後 |
| 在庫を解放する | ReleaseInventory | Alt-8 補償 |
| ポイントを消費する | ConsumePoints | 客が注文時に指定した使用ポイント分を引き落とす |
| ポイントを返戻する | RefundPoints | Alt-8 補償 |
| 残金を決済する | SettleBalance | 下取り充当・ポイント消費後の残金、または全額 |
| 商品を発送する | ShipPurchasedItem | |
| ポイントを付与する | GrantPoints | |
| 見積もりを失効させる | ExpireQuote | Alt-5（タイマー） |
| 下取りを打ち切る | TerminateTradeIn | Alt-6（タイマー） |
| キャンペーンを開始する | StartCampaign | マーケティング担当 |
| キャンペーンを終了する | EndCampaign | 期間終了 |

### イベント
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| カートに追加された | ItemAddedToCart | |
| 下取り概算が提示された | TradeInEstimateProvided | |
| 注文が受け付けられた | OrderPlaced | 下取り保留状態（過渡） |
| 集荷キットが発送された | PickupKitShipped | |
| 下取り品が発送された | TradeInItemShipped | |
| 下取り品が受領された | TradeInItemReceived | |
| 本査定が完了した | AppraisalCompleted | 見積もり=査定の場合 |
| 査定差異が検知された | AppraisalDiscrepancyDetected | Alt-1〜3 共通 |
| 再見積もりが提示された | RevisedQuotePresented | |
| 承認が依頼された | ApprovalRequested | |
| 査定が承認された | AppraisalApproved | |
| 下取りがキャンセルされた | TradeInCancelled | Alt-2/3 |
| 下取り品が返送された | TradeInItemReturned | |
| 注文がキャンセルされた | OrderCancelled | Alt-2 |
| 購入が確定された | PurchaseConfirmed | |
| 残金が決済された | BalanceSettled | |
| 残金決済が失敗した | BalanceSettlementFailed | Alt-8 |
| 在庫が引き当てられた | InventoryAllocated | |
| 在庫引当に失敗した | InventoryAllocationFailed | Alt-7 |
| 在庫が解放された | InventoryReleased | Alt-8 補償 |
| ポイントが消費された | PointsConsumed | 客指定の使用ポイント分 |
| ポイントが返戻された | PointsRefunded | Alt-8 補償 |
| 商品が発送された | PurchasedItemShipped | |
| ポイントが付与された | PointsGranted | |
| 下取り見積もりの有効期限が切れた | TradeInQuoteExpired | Alt-5 |
| 下取り品が長期間届かない | TradeInShipmentTimedOut | Alt-6 |
| キャンペーンが開始された | CampaignStarted | |
| キャンペーンが終了した | CampaignEnded | |

### ポリシー
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 下取り集荷手配 | TradeInPickupArrangement | OrderPlaced を契機 |
| 査定結果通知 | AppraisalResultNotification | AppraisalCompleted を契機 |
| 差異検知通知 | DiscrepancyNotification | AppraisalDiscrepancyDetected を契機 |
| 下取り承認時購入確定 | PurchaseConfirmationOnApproval | AppraisalApproved を契機 |
| 下取りキャンセル時注文取消 | OrderCancellationOnTradeInCancel | Alt-2 |
| 下取り無しで購入続行 | PurchaseWithoutTradeIn | Alt-3 |
| 下取り利用優遇付与 | TradeInBonusPointGrant | PurchasedItemShipped を契機・キャンペーン期間内なら +5% も加算 |
| キャンペーン優遇付与 | CampaignBonusPointGrant | Alt-3（下取り無し版） |
| ポイント消費トリガー | PointConsumptionTrigger | InventoryAllocated を契機・使用ポイント分を消費 |
| 残金決済トリガー | BalanceSettlementTrigger | PointsConsumed を契機・残金を決済 |
| 残金決済失敗時補償 | CompensationOnBalanceFailure | Alt-8・消費ポイントを返戻 |
| 在庫解放トリガー | InventoryReleaseTrigger | Alt-8・在庫を解放し注文を取消 |
| 在庫不足時注文取消 | OrderCancellationOnInventoryShortage | Alt-7 |
| 見積もり期限監視 | QuoteExpiryWatchdog | Alt-5・タイマー |
| 下取り品発送猶予監視 | TradeInShipmentWatchdog | Alt-6・タイマー |
| 下取りタイムアウト時注文取消 | OrderCancellationOnTradeInTimeout | Alt-6 |
| キャンペーン終了監視 | CampaignEndWatchdog | Alt-9・期間終了でキャンペーンを終了 |
| 購入確定時在庫引当 | InventoryAllocationOnPurchaseConfirmed | [?] DSL 同期継続の接続（PurchaseConfirmed→AllocateInventory）。SAME/別 TX 要確認 |
| 在庫解放時注文取消 | OrderCancellationOnInventoryRelease | [?] Alt-8 補償の接続（InventoryReleased→CancelOrder） |

### リードモデル
| 日本語（フロー図） | 英語（DML） | 備考 |
|------|------|------|
| 下取り概算の参照 | GetTradeInEstimate | 注文時に概算額・有効期限を確認 |
| ポイント残高の参照 | GetPointBalance | 注文時に使用ポイントが残高内か判断 |
| 残金の参照 | GetOutstandingBalance | 残金 = 購入額 − 下取り額 − 使用ポイント |
| 付与率の参照 | GetApplicableBonusRate | 下取り +10% ＋ キャンペーン +5% |
