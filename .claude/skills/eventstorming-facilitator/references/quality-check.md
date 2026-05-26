# EventStorming / DDD 表記品質チェックリスト

MDファイルを書き出した後、サブエージェントがこのチェックリストに従って検査・修正する。

---

## 1. DML記法チェック（セクション8の ```dml ブロック）

| # | ルール | NG例 | OK例 |
|---|-------|------|------|
| D1 | `EVT`/`CMD`/`AGG` 名は英語PascalCaseのみ | `EVT 注文確定` | `EVT OrderConfirmed` |
| D2 | `EVT` 名は過去形 | `EVT PlaceOrder` | `EVT OrderPlaced` |
| D3 | `CMD` 名は命令形 | `CMD OrderPlaced` | `CMD PlaceOrder` |
| D4 | `SCENARIO` 名は日本語でアクター＋行為 | `SCENARIO OrderFlow` | `SCENARIO 顧客が注文を確定する` |
| D5 | 各 `SCENARIO` 内に `ACTOR` 行がある | （ACTOR行なし） | `ACTOR Customer` |
| D6 | `CONTEXT` 名は `lowercase-with-hyphen` | `CONTEXT OrderManagement` | `CONTEXT order-management` |
| D7 | `RULE`/`ERR`/`POLICY` の日本語補足は直上の `#` コメント行に書く | `RULE 在庫数 >= 0` | `# 在庫数は0以上`<br>`RULE StockNonNegative` |
| D8 | `EVT`/`CMD`/`AGG` に `()` `<<>>` を付けない | `EVT (OrderPlaced)` | `EVT OrderPlaced` |
| D9 | `POLICY` ブロックは EVENTUAL-TX 限定。`TX SAME` 記述を検出したら SCENARIO の `WHEN` 分岐に書き換え提案する | `POLICY X`<br>`  TX SAME` | SCENARIO 内 `WHEN condition → EVT ...` |
| D10 | 各 `CONTEXT` 宣言に `UPSTREAM` / `DOWNSTREAM` が記載されている（依存なしは `(none)` 明示） | `CONTEXT foo`<br>`  LANGUAGE Foo = "..."` | `CONTEXT foo`<br>`  LANGUAGE Foo = "..."`<br>`  UPSTREAM (none)`<br>`  DOWNSTREAM bar  # Customer-Supplier` |

---

## 2. event_flow 図チェック（セクション2・3の `` ```event-flow-svg `` ブロック、旧記法 `:::diagram-svg event_flow` も対象）

| # | ルール | NG例 | OK例 |
|---|-------|------|------|
| F1 | `$Policy` の直後に必ず `!Command` がある（`$Policy > [Event]` は禁止） | `$在庫確認ポリシー > [在庫が不足した]` | `$在庫確認ポリシー > !在庫を確認 > [在庫が不足した]` |
| F2 | イベントは `[日本語過去形]` で表記 | `[在庫不足]` | `[在庫が不足した]` |
| F3 | コマンドは `!動詞句（日本語）` で表記 | `[注文確定]` や `OrderConfirm` | `!注文を確定` |
| F4 | BC名は `|lowercase-with-hyphen|` | `|OrderManagement|` | `|order-management|` |
| F5 | アクターは `@役割名（日本語）` で表記 | `@Customer` | `@顧客` |
| F6 | `?ReadModel` は**操作対象集約以外**からのデータ取得にのみ付ける。同一集約の参照には付けない。順序は `@Actor > ?ReadModel > !Command` | 書き込む集約と同じデータを `?ビュー` で表記する | 別集約の残席数を確認する `?残席数 > !参加申込` |

---

## 3. セクション完全性チェック

| # | ルール |
|---|-------|
| S1 | セクション1（ハッピーパスストーリー）が400〜600字で記述されているか |
| S2 | セクション2（代替シナリオ）は**テキストのみ**。`` ```event-flow-svg `` / `:::diagram-svg` ブロックがあれば削除する（図はセクション3に集約） |
| S3 | セクション3（Event Walkthrough）に **ハッピーパス図が最初** に来ているか |
| S4 | セクション3の代替シナリオにも `` ```event-flow-svg `` 図があるか（ハッピーパス図の後。旧記法 `:::diagram-svg event_flow` も可） |
| S5 | セクション5（集約候補）の各 AGG に ` ```ts ` の Zod スキーマブロックが存在するか |
| S6 | セクション4（コンテキスト候補）の各 BC に「依存方向」項目（UPSTREAM / DOWNSTREAM）が存在するか |
| S7 | セクション10（用語集）が存在し、フロー図で使われている `@` / `!` / `[]` / `$` / `?` 付き日本語ラベルがすべて登録されているか |
| **S8** | **セクション5（集約候補）の各 AGG に `#### 目的` サブセクションがあり、本文が 30 字以上書かれているか**。空・未記入・短すぎる項目は **自動修正せず**、ホットスポット候補 `[?-WHY] S8_<AggName>: 目的が未記入または短すぎる` として返す（M 系と同じ運用） |

---

## 3-B. WHY/WHEN 推奨チェック（W1〜W2）

「**形式違反ではない・あるとより良い**」を見るカテゴリ。違反は自動修正せず、ホットスポット候補 `[?-WHY] W_N` として返す。

| # | ルール | 検出ロジック | 違反例 → 推奨 |
|---|-------|------|------|
| W1 | 各 `RULE` 行の直下にインデント +2 で `WHY "..."` が書かれていることを推奨 | DML パースで `RULE  ...` 行の次の行が `    WHY  "..."` でない | `RULE communityName must be unique system-wide` → `WHY "URL slug や検索 UX で name → id 逆引きを想定するため"` を推奨 |
| W2 | 各 `ERR` 行の直下にインデント +2 で `WHEN "..."` が書かれていることを推奨 | 同上、`ERR  ...` 行の次の行が `    WHEN "..."` でない | `ERR duplicateName → DuplicateCommunityNameError` → `WHEN "name が既存と重複"` を推奨 |

**S8 / W1 / W2 の運用方針:** D / F / S1〜S7 のような自動修正は **しない**。意味判断を伴うため、検出後はホットスポット候補 `[?-WHY]` プレフィックスで列挙し、ファシリテーター本体が次ターン以降に **1 件ずつ会話補完**（詳細は `chat-output-format.md` §10A「WHY 補完モード」）。

---

## 4. モデリング意味チェック（M1〜M5）

D・F・S 系が「**表記** の正しさ」を見るのに対し、M 系は「**意味** の正しさ」を見る。CMD / EVT の命名が業務概念と一致しているか、CRUD 的に技術側へ寄っていないかを確認する。

| # | ルール | 検出ロジック | 違反例 | 推奨 |
|---|-------|-----|------|------|
| M1 | CMD と直後 EVT の **動詞語幹が一致** しており、かつその EVT が **他 BC を経由する Saga の起点** になっている場合、CMD 発行時点は「真の業務完了」ではないため、命名が早すぎる可能性がある | (1) `SCENARIO X` の `CMD V_X` と直後の `EVT X_V_ed` の動詞語幹が一致<br>(2) その EVT を `TRIGGER` とする `POLICY` が存在<br>(3) その POLICY チェーンが別 BC を経由 → 警告 | `CMD PlaceOrder` (注文を**確定**) ↔ `EVT OrderPlaced` (注文が**確定**された) で、後続に在庫予約・決済 Saga が続く | CMD `PlaceOrder` (注文する) / EVT `OrderPlaced` (注文された) に **過渡状態** を表現し、Saga 完了時の別 SCENARIO で `ConfirmOrder` / `OrderConfirmed` を導入 |
| M2 | CMD 名に **技術的・CRUD 的動詞** が含まれる | CMD 名に次の prefix を検出: `Mark`, `Set`, `Update`, `Modify`, `Change`, `Save`, `Persist`, `Flush` | `CMD MarkOrderPaid` `CMD SetUserStatus` `CMD UpdateInventoryCount` | 業務動作を表す動詞へ: `ConfirmOrder` / `ActivateUser` / `RestockInventory` 等 |
| M3 | AGG の **status enum 値** と、その状態へ遷移させる **CMD の動詞語幹** が乖離している | (1) AGG の `status` enum 値リストを抽出<br>(2) 各 status へ遷移させる CMD を SCENARIO から特定<br>(3) status 値の名詞と CMD の動詞語幹が **対応関係にない** ものを検出 | `status: 'paid'` への遷移 CMD が `MarkOrderPaid`（status と動詞が不対応） | status を `'confirmed'` に統合し、CMD を `ConfirmOrder` にすると `confirm/confirmed` で対応 |
| M4 | Saga チェーンの **完了 EVT が業務上の確定を表現できていない** | (1) POLICY チェーン（複数 BC 経由）の起点 EVT と終点 EVT を特定<br>(2) 終点 EVT が業務的に意味のある「完了状態」を表しているか<br>(3) もし起点と終点が同じ業務概念の異なる段階を表せていないなら警告 | 注文 Saga の最終 EVT が `OrderMarkedPaid` で、業務上の「注文確定」を表す明確な完了 EVT が存在しない | Saga 完了として `OrderConfirmed`（注文が確定された）を導入し、起点 `OrderPlaced`（注文された）と段階を区別 |
| M5 | POLICY 名が **業務意義のない一般名** で、TRIGGER → CMD の意味が把握しづらい | POLICY 名が「○○ポリシー」だけで、TRIGGER EVT と発行 CMD の業務的橋渡しを説明していない場合に提案 | `POLICY 引当確定ポリシー` (TRIGGER: PaymentCompleted → CMD: CommitStockReservation + MarkOrderPaid) | 業務的意義を反映した命名へ: `POLICY 注文確定ポリシー` （「決済成功で注文を確定する」業務ルールを表す） |

---

### M 系の修正方針: 「指摘のみ・自動修正しない」

D / F / S 系のような **形式的な違反は自動修正** するが、M 系は **業務概念の判断を伴う** ため、エージェントは自動修正せず以下のように扱う:

- 違反候補を検出したら **ホットスポット候補** として `[?] M_N: <該当箇所>` 形式で結果に列挙
- 修正案（推奨 CMD/EVT 名、推奨 SCENARIO 分割）を提示
- **人間が次ターンで判断・採用するための材料を提供** する

これにより、技術的正しさ（D/F/S）と業務的正しさ（M）の **2 段階レビュー** が成立する。

---

## 検査・修正手順

1. MDファイルを `Read` で読み込む
2. **D・F・S1〜S7 系**を全項目検査 → 違反は `Edit` tool で自動修正
3. **S8 / W1 / W2 / M 系**を全項目検査 → 違反候補は自動修正せず、レポートに `[?-WHY] S8/W_N` または `[?] M_N` として列挙
4. 結果を返す：
   - 違反なし → `「品質チェック完了：問題なし」`
   - D/F/S1〜S7 違反あり → 修正した項目リスト（`F1: $Policy後の!Command追加 ×3箇所` など）
   - S8 違反あり → ホットスポット候補リスト（`[?-WHY] S8_Payment: AGG Payment の #### 目的 が未記入` など）
   - W1/W2 違反あり → ホットスポット候補リスト（`[?-WHY] W1: SCENARIO 主催者がコミュニティを作成する の RULE 1 に WHY 未記入` など）
   - M 違反候補あり → ホットスポット候補リスト（`[?] M1: SCENARIO 顧客が注文を確定する — CMD/EVT で「確定」が重複、Saga 起動のため早すぎる命名の可能性` など）
