# EventStorming / DDD 表記品質チェックリスト

`.md` と兄弟 `.dml.yaml` を書き出した後、サブエージェントがこのチェックリストに従って検査・修正する。

---

## 1. DML記法チェック（兄弟 `.dml.yaml` ファイル・YAML 直書き）

DML は兄弟 `<session>.dml.yaml` ファイル（純 YAML・フェンスなし）。`ctxs` / `aggs` / `scs` / `pols` の 4 トップレベルリスト（任意で `domains` / `flows` / `decisions`）で構成される。AGG 詳細はトップレベル `aggs[]` に集約し、`ctxs[].aggs` は AGG 名（PascalCase 文字列）の軽量名簿として保持する。

> **JSON Schema との分担**: 形式（正規表現で判定できるもの）= **D1 / D6 / D8** と、`evt`↔`brs` 排他・`trg`↔`trgs` 排他・`bulk:true`→`qry` 必須・未知フィールド禁止・enum 違反は `references/dml.schema.yaml` が機械検証する（`scripts/validate_dml.py`）。サブエージェントはまず兄弟 `.dml.yaml` を Read し、Schema 違反（あれば build バナー / validate_dml の出力）を判断材料にする。**時制・命令形・言語・意図の判断（D2 / D3 / D4 / D7）は Schema では不可能**なので、引き続きこのチェックリストで確認・修正する。

| # | ルール | NG例 | OK例 |
|---|-------|------|------|
| D1 | `evt`/`cmd`/`agg` の値は英語PascalCaseのみ | `evt: 注文確定` | `evt: OrderConfirmed` |
| D2 | `evt`（および `trg`/`emits`/`brs[].evt`）の値は過去形 | `evt: PlaceOrder` | `evt: OrderPlaced` |
| D3 | `cmd` の値は命令形 | `cmd: OrderPlaced` | `cmd: PlaceOrder` |
| D4 | `scs[].name` は日本語でアクター＋行為 | `name: OrderFlow` | `name: 顧客が注文を確定する` |
| D5 | 各 `scs[]` に `actor` がある | （actor なし） | `actor: Customer` |
| D6 | `ctxs[].name` は `lowercase-with-hyphen` | `name: OrderManagement` | `name: order-management` |
| D7 | 日本語補足は `rules[].why` / `errs[].when` / `note` フィールドへ。`#` 行コメントは使わない | `# 在庫数は0以上`<br>`- rule: StockNonNegative` | `- rule: stock must be non-negative`<br>`  why: "在庫数は0以上"` |
| D8 | `cmd`/`evt`/`agg` 等の値に `()` `<<>>` を付けない | `evt: (OrderPlaced)` | `evt: OrderPlaced` |
| D9 | `pols` は EVENTUAL-TX 限定。同期分岐（SAME-TX）は `pols` に置かず、発行元 `scs[].brs` に書く | 同期分岐用の `pols` 要素 | scenario 内 `brs:`<br>`  - cond: ...`<br>`    evt: ...` |
| D10 | 各 `ctxs[]` に `up` / `dn` がある（依存なしは空リスト `[]`、`rel` 併記） | `- name: foo`<br>`  lang: {...}` | `- name: foo`<br>`  up: []`<br>`  dn:`<br>`    - ctx: bar`<br>`      rel: Customer-Supplier` |

---

## 2. フロー記述チェック（DML `flows[]`）

§3 のフロー図は手書きの DSL ではなく **DML `flows[]` から自動生成** される。記述ミスは以下で検出する。

| # | ルール | NG例 | OK例 |
|---|-------|------|------|
| F-flows | `flows[].steps[]` の各 step 名が **scs[].name（日本語）または pols[].name（PascalCase）** のいずれかと完全一致する。typo・未定義参照は **自動修正せず**、ホットスポット候補として返す | `steps: [- 顧客が注文確定する]`（scs[].name 未定義） | `steps: [- 顧客が注文を確定する]`（scs[].name と一致） |
| F-decisions | 各 `decisions[]` エントリで `chosen` が `options[].name` のいずれかと一致し、各 option に `why` または `why_not` が記述されているか | `chosen: A 案` / `options[].name: [A, B]`（不一致） | `chosen: A`／`options[].name: [A, B]` 各々に `why`/`why_not` あり |

`F-flows` の検出ロジック:
```
flows[].steps[] の各 step について：
  → scs[].name にあるか？  pols[].name にあるか？
  → どちらにも無ければ:
     [?] F-flows_<flowId>_<step>: step "<step>" は scs/pols に未定義
```

`F-decisions` の検出ロジック:
```
decisions[] の各エントリ d について：
  → d.chosen が d.options[].name のいずれかと一致するか？
  → 各 option に why または why_not が記述されているか？
  → 不一致／未記述があれば:
     [?] F-decisions_<id>: <内容>
```

---

## 3. セクション完全性チェック

| # | ルール |
|---|-------|
| S1 | セクション1（ハッピーパスストーリー）が400〜600字で記述されているか |
| S2 | セクション2（代替シナリオ）は**テキストのみ**。フロー図相当のコードブロックがあれば削除する（図は §3 が DML から自動生成） |
| S3 | `.dml.yaml` の `flows[]` に **`kind: happy`** のエントリが少なくとも 1 件あるか |
| S4 | `.dml.yaml` の `flows[]` に代替シナリオ（`kind: alt`）が 1 件以上あるか（推奨） |
| **S5-attr** | **`.dml.yaml` の `aggs[]` 各エントリに `attrs[]` が 1 件以上記述されているか**。未記述はホットスポット候補として返す: `[?] S5-attr_<AggName>: aggs[].attrs[] が未記述` |
| **S5-evt** | **`.dml.yaml` の `aggs[]` 各エントリに `events[]` が 1 件以上、各 event に `params[]` が記述されているか**。未記述はホットスポット候補として返す: `[?] S5-evt_<AggName>: aggs[].events[] が未記述`、または `[?] S5-evt_<AggName>.<EventName>: params[] が未記述` |
| S6 | セクション8（コンテキスト候補）の各 BC に「依存方向」項目（UPSTREAM / DOWNSTREAM）が存在するか。**§8 は AI/人間が `.md` 本文を書くセクション**であり、`.dml.yaml` 自動生成マーカーへの上書きは禁止 |
| S7 | セクション4（用語集）が存在し、`scs[]`/`pols[]`/`aggs[]` で使われている英語識別子（actor / cmd / evt / agg / pol / qry）がすべて登録されているか。用語集は §8〜§10 を読む前の前置き表として §4 に置く |
| **S8** | **`.dml.yaml` の `aggs[]` 各エントリに `purpose` があり、本文が 30 字以上書かれているか**。空・未記入・短すぎる項目は **自動修正せず**、ホットスポット候補 `[?-WHY] S8_<AggName>: 目的が未記入または短すぎる` として返す |
| **S9** | **`aggs[].name` で宣言された AGG が `scs[].agg` でも参照されているか（孤立 AGG の検出）／逆に `scs[].agg` が `aggs[].name` に存在するか（未定義 AGG 参照の検出）**。違反は **自動修正せず**、ホットスポット候補として返す: `[?] S9_<AggName>: aggs[] に宣言されているが scs[].agg で未参照（孤立 AGG）` または `[?] S9_<AggName>: scs[].agg で参照されているが aggs[] に未宣言` |

---

## 3-B. WHY/WHEN 推奨チェック（W1〜W3）

「**形式違反ではない・あるとより良い**」を見るカテゴリ。違反は自動修正せず、ホットスポット候補 `[?-WHY] W_N` として返す。

| # | ルール | 検出ロジック | 違反例 → 推奨 |
|---|-------|------|------|
| W1 | 各 `rules[]` に `why` キーが書かれていることを推奨 | YAML パースで `rules[]` 要素に `why` が無い | `- rule: communityName must be unique system-wide` → `why: "URL slug や検索 UX で name → id 逆引きを想定するため"` を推奨 |
| W2 | 各 `errs[]` に `when` キーが書かれていることを推奨 | 同上、`errs[]` 要素に `when` が無い | `- cond: duplicateName`<br>`  err: DuplicateCommunityNameError` → `when: "name が既存と重複"` を推奨 |
| W3 | 各 `decisions[]` の各 `options[]` に `why`（採用）または `why_not`（不採用）が書かれていることを推奨 | YAML パースで `options[]` 要素に `why`/`why_not` が無い | `- name: A 案`（理由なし） → `why: "..."` または `why_not: "..."` を推奨 |

**S8 / W1〜W3 の運用方針:** D / F / S1〜S7 のような自動修正は **しない**。意味判断を伴うため、検出後はホットスポット候補 `[?-WHY]` プレフィックスで列挙し、ファシリテーター本体が次ターン以降に **1 件ずつ会話補完**（詳細は `chat-output-format.md` §10A「WHY 補完モード」）。

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

1. `.md` ファイルと兄弟 `.dml.yaml` を `Read` で読み込む
2. **D・F・S1〜S7 系**を全項目検査 → 違反は `Edit` tool で自動修正
3. **S5-attr / S5-evt / S8 / S9 / W1〜W3 / F-flows / F-decisions / M 系**を全項目検査 → 違反候補は自動修正せず、レポートに `[?-WHY] S/W_N` または `[?] S/M/F_N` として列挙
4. 結果を返す：
   - 違反なし → `「品質チェック完了：問題なし」`
   - D/F/S1〜S7 違反あり → 修正した項目リスト（`F1: $Policy後の!Command追加 ×3箇所` など）
   - S5-attr / S5-evt 違反あり → ホットスポット候補リスト（`[?] S5-attr_Event: aggs[].attrs[] が未記述` など）
   - S8 違反あり → ホットスポット候補リスト（`[?-WHY] S8_Payment: AGG Payment の purpose が未記入` など）
   - S9 違反あり → ホットスポット候補リスト（`[?] S9_Notification: aggs[] に宣言されているが scs[].agg で未参照（孤立 AGG）` など）
   - F-flows / F-decisions 違反あり → ホットスポット候補リスト（`[?] F-flows_happy_顧客が注文する: step "顧客が注文する" は scs/pols に未定義` など）
   - W1/W2/W3 違反あり → ホットスポット候補リスト（`[?-WHY] W1: SCENARIO 主催者がコミュニティを作成する の RULE 1 に WHY 未記入` など）
   - M 違反候補あり → ホットスポット候補リスト（`[?] M1: SCENARIO 顧客が注文を確定する — CMD/EVT で「確定」が重複、Saga 起動のため早すぎる命名の可能性` など）
