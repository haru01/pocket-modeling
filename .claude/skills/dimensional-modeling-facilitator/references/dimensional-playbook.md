# ディメンショナル・モデリング プレイブック（Kimball 正典）

## 0. このプレイブックの役割と読み方

DimML でモデルを書く／育てるときの **設計判断・命名・検証の正典**。Kimball 流の
ディメンショナル・モデリング（データウェアハウス／BI 設計）を概念軸で横断集約する。

- 構文の真実源は `dimml.schema.yaml`（JSON Schema）。**スキーマ通過は必要条件であって十分条件ではない**。
- 各概念は「定義／命名・構文／設計判断ルール／検証観点」の 4 節で書く（EventStorming プレイブックと同形式）。
- 迷ったらまずここ。要約と食い違ったら本プレイブックが優先。

Kimball の設計は **4 ステップ**で進む。SKILL.md のフェーズはこれに沿う:

1. **業務プロセスを選ぶ**（§2）— 何を測定するか。バスマトリクスの行になる。
2. **グレインを宣言する**（§3）— ファクト 1 行が表す実体。**最重要**。
3. **ディメンションを同定する**（§4）— グレインの文脈（誰が・何を・いつ・どこで）。
4. **ファクト（測定値）を同定する**（§6）— グレインに一致する数値。

---

## 1. 記法の原則（横断ルール）

- **識別子は英語**。fact / dimension = PascalCase 単数（`Sales` `Product`）、process = lowercase-with-hyphen（`retail-sales`）、物理列（attribute / measure / degenerate）= camelCase か snake_case（`salesAmount` / `product_key`）。日本語は `label` / `note` に置く。
- **grill 規律（検証状態）**: 全モデル要素（process / fact / dimension / narrative）は `status: verified | unverified` を持つ。**省略時は unverified 扱い**。根拠（業務の裏取り・実データ・有識者確認）が言語化された要素だけ `verified` へ昇格する。推測を「検証済の事実」として通さないための機械可読フラグ。
- **未確認は `questions[]` に open で残す**。推測で埋めない。選択肢が見えたら `decisions[]` に昇格。
- **HTML は派生物**。DimML を直し、`dimml_build.py` で再生成する。手で HTML を編集しない。

### 検証観点
- `status` が全要素 verified の完成主張なのに `questions[]` に open が残る → 矛盾（grill 未了）。
- 識別子が命名パターン外 → `validate_dimml.py` が構文違反として検出。

---

## 2. 業務プロセス (Process)

### 定義
測定可能な業務イベント／活動の単位（受注・出荷・在庫スナップショット等）。エンタープライズ・バスマトリクスの **行**。組織図や部門ではなく「何が起きて何が測れるか」で選ぶ。

### 命名・構文
- `processes[]` の要素。`name`（slug・必須）／`label`（日本語表示）／`description`／`status`。
- 1 プロセスは通常 1 つ以上のファクトを生む（`facts[].process` で参照）。

### 設計判断ルール
- **原子的な業務プロセスを選ぶ**（「販売」「在庫」「出荷」）。「月次売上レポート」のような **成果物**ではなく、それを生む**業務行為**を選ぶ。
- **部門をまたぐ視点で選ぶ**。同じディメンション（顧客・商品・日付）を複数プロセスが共有できるよう、企業横断で行を並べる（＝conformed dimension の土台）。
- 優先順位は「価値が高く実現が容易」なプロセスから（Kimball のバスマトリクス優先度付け）。

### 検証観点
- `facts[].process` が実在の process を指すか（`validate_dimml.py` の参照チェック）。
- プロセスが成果物・レポート・部門名になっていないか（意味レビュー）。

---

## 3. グレイン (Grain) ★最重要

### 定義
**ファクト表の 1 行が表す実体**を宣言したもの。ディメンショナル設計の全判断はグレインに従属する。グレインが曖昧なモデルは必ず破綻する。

### 命名・構文
- `facts[].grain`（自然文 1 行・必須級）。例:「1 行 = POS レシート 1 明細（1 レシート × 1 SKU）」。
- `facts[].grainType`（enum）でファクト種別を宣言（§5）。

### 設計判断ルール
- **グレインは業務語で 1 行で言い切る**。「〜ごとに 1 行」の形。DDD 用語や実装語（テーブル・カラム）で言わない。
- **原子グレイン（最も細かい実用単位）を第一候補にする**。集計は後から常に可能だが、集計済みグレインから明細に降りることはできない。
- **グレイン宣言 → ディメンション → 測定値の順を厳守**。先に列を並べない。すべての dimension と measure は「そのグレインに一致するか？」で採否を決める。
- **グレインの混在禁止**。1 ファクトに異なる粒度の行（明細行と合計行）を混ぜない。

### 検証観点
- `grain` が空／曖昧（「販売データ」等）→ 意味違反。
- ある measure がグレインと一致しない（例: 明細グレインに「注文合計金額」を持つ→重複計上）→ 意味違反。
- `grainType` 未宣言 → §5 の判断が未了。

---

## 4. ディメンション (Dimension)

### 定義
ファクトを **スライス／ドリルする文脈**（誰が・何を・いつ・どこで・どのように）。テキスト属性の集合を持ち、レポートの行見出し・フィルタになる。conformed（複数プロセスで共有）が理想。

### 命名・構文
- `dimensions[]` の要素。`name`（PascalCase 単数）／`grain`（「1 行 = 何か」）／`scd`（none/TYPE_1/TYPE_2）／`conformed`（bool）／`attrs[]`（`name`/`type`/`key`(surrogate|natural)/`note`）／`hierarchies[]`（`name`/`levels[]`）／`status`。
- ファクトからの参照は `facts[].dims[]`（`dimension` 参照＋任意 `role`）。

### 設計判断ルール
- **サロゲートキーを持つ**（`key: surrogate`）。業務キー（自然キー `key: natural`）に依存せず、SCD やキー再利用に耐える。
- **属性は非正規化して豊かに**。ディメンションはスノーフレーク（正規化）せず、フラットに多列で持つのが原則（クエリの単純化・階層のドリルダウン）。
- **SCD（Slowly Changing Dimension）で変化の扱いを決める**（v1 の 3 型）:
  - `none`: 変化しない（日付など）。
  - `TYPE_1`: 上書き（履歴不要。最新のみ）。
  - `TYPE_2`: 履歴行を追加（`effectiveDate`/`expiryDate`/`isCurrent`）。過去のファクトを「当時の属性」に正しく帰属できる。**遡及分析が要るなら TYPE_2**。
- **conformed dimension**: 同一ディメンションを複数プロセス／ファクトで**同じ意味・同じキー・同じ属性**で共有する。これが横断分析（drill-across）を可能にする。バスマトリクスの列（§7）。
- **role-playing dimension**: 1 つの物理ディメンションを複数の役割で参照（`Date` を `OrderDate`/`ShipDate`/`DeliveryDate` として）。`facts[].dims[].role` で表す。
- **degenerate dimension**: 伝票番号（レシート番号・注文番号）のように**ディメンション表を持たずファクトに直接置く**次元。`facts[].degen[]`。
- **既定行（unknown member）を持つ**: 外部キーが NULL にならないよう「不明」「販促なし」を表す行を 1 件用意する（プレイブックの慣習・`note` に明記）。

### 検証観点
- `facts[].dims[].dimension` が実在の dimension を指すか（参照チェック）。
- サロゲートキー不在 / スノーフレーク化 / 属性が貧弱（コードだけで説明列が無い）→ 意味レビュー。
- 同名 conformed のはずのディメンションが `grain`／属性で食い違う → conformance 違反（§7）。

---

## 5. ファクト (Fact) と 3 つの種別

### 定義
測定値（数値）を保持し、複数の外部キーでディメンションに結ばれる表。スタースキーマの中心。

### 命名・構文
- `facts[]` の要素。`name`（PascalCase）／`process`／`grain`／`grainType`／`dims[]`／`msrs[]`／`degen[]`／`status`。
- `grainType` enum:

| grainType | 定義 | 例 | 加法性の傾向 |
|---|---|---|---|
| `transaction` | 業務トランザクション 1 件 1 行 | 販売明細 | 測定値は加法的が基本 |
| `periodic-snapshot` | 一定周期に状態を撮った 1 行 | 日次在庫残高 | **時間軸で semi-additive**（残高） |
| `accumulating-snapshot` | パイプライン 1 インスタンス 1 行を複数マイルストーンで更新 | 注文履行（受注→出荷→配達） | 複数の日付（role-playing）とラグ測定値 |

### 設計判断ルール
- **1 スター = 1 ファクト = 1 グレイン**。まず transaction を疑う（最も汎用）。残高・在庫は periodic-snapshot。工程リードタイムは accumulating-snapshot。
- **ファクトは「痩せて長い」**。数値測定値と外部キーだけ。テキストはディメンションへ。
- **accumulating-snapshot は複数の日付ディメンションを role-playing で持つ**。行は工程進行に応じて UPDATE される（他 2 種は INSERT のみ）。

### 検証観点
- `grainType` と測定値の加法性が整合するか（periodic-snapshot に純加法的な残高 → semi-additive 宣言漏れ）。
- ファクトにテキスト属性が紛れていないか（ディメンション化すべき）。

---

## 6. 測定値 (Measure) と加法性

### 定義
ファクトが持つ数値。分析の「合計・平均」の対象。加法性（どのディメンションで足せるか）が扱いを決める。

### 命名・構文
- `facts[].msrs[]`。`name`（列名）／`label`／`additivity`（additive/semi-additive/non-additive）／`semiAdditiveAcross`（semi のとき足せない軸）／`unit`／`formula`（派生）／`note`。

### 設計判断ルール
- **additive**: すべてのディメンションで合算可（売上金額・数量）。最も扱いやすく望ましい。
- **semi-additive**: 一部の軸（通常は**時間**）で合算不可（在庫残高・口座残高）。`semiAdditiveAcross: Date` を宣言。時間では合計でなく期末値・平均を使う。
- **non-additive**: 比率・単価・率（合算不可）。**分子・分母を加法的な measure として持ち**、比率は集計後に算出する（`unitPrice` は保存せず `salesAmount/salesQuantity`）。
- **派生測定値は `formula` に式を書く**（`grossProfit = salesAmount - costAmount`）。

### 検証観点
- non-additive 測定値をそのまま保存し合計している → 誤集計リスク（意味レビュー）。
- semi-additive に `semiAdditiveAcross` 未宣言 → 時間合計の誤りを招く。

---

## 7. エンタープライズ・バスマトリクス (Bus Matrix)

### 定義
**業務プロセス（行）× conformed ディメンション（列）**の表。企業のデータウェアハウス全体像・実装ロードマップ・conformance の設計図。DimML では `processes`/`facts` × `dimensions` の使用関係から build が派生生成する。

### 命名・構文
- 明示的なトップレベルは持たない（派生）。列の conformed 判定は「2 つ以上のファクトで使用」または `dimensions[].conformed: true`。

### 設計判断ルール
- **conformed dimension を最大化する**。同じ Date/Product/Customer を全プロセスで共有すれば、プロセスをまたいだ drill-across（例: 販売と在庫を同じ商品軸で比較）ができる。
- **列の意味を 1 つに固定する**。同名ディメンションがプロセスごとに違う grain／属性なら conformed ではない（偽の共有）。

### 検証観点
- 複数ファクトが参照する同名ディメンションの `grain`・キー・主要属性が一致するか。
- conformed になり得るのに別々に定義された重複ディメンションが無いか。

---

## 8. 意思決定 (decisions) と 未検証の慣習

### 定義
グレイン粒度・SCD 型選択・ファクト種別など、後から効く設計判断の「採用/不採用理由ログ」。

### 命名・構文
- `decisions[]`：`id`／`topic`／`chosen`／`options[]`（`name`/`label`/`adopted`/`why`/`why_not`）／`affects[]`（fact/dimension 名）。
- `chosen` は `options[].name` のいずれかと一致し、その option に `adopted: true` を付ける。

### 設計判断ルール
- グレインと SCD は**必ず** decisions に残す（最も破壊的な後戻りを生む 2 大論点）。
- `why`/`why_not` は**業務文脈の言葉**で（「遡及集計が壊れる」等）。抽象論（「正しい」）で終わらせない。

### 検証観点
- `chosen` が options に無い／`adopted` 不整合 → `validate_dimml.py` が検出。
- open な `questions[]` が対応する decision で closed 化されているか。

---

## 9. 検証の境界（構文 vs 意味）

- **構文 validity**（`validate_dimml.py` + schema）: 型・enum・命名・参照実在（dims→dimensions、facts→processes、chosen→options）。
- **意味 validity**（本プレイブックの各検証観点＋ LLM レビュー）: グレインの明確さ・グレインと測定値の整合・加法性の妥当性・conformed dimension の一致・SCD 選択の妥当性。
- スキーマ通過は出発点。意味観点はセッション中の grill と最終レビューで担保する。

---

## 10. v1 の範囲と今後の拡張

**v1 に含む**: バスマトリクス／グレイン宣言／3 ファクト種別／conformed dimension／SCD Type 1 & 2／degenerate・role-playing dimension／加法性（additive/semi-additive/non-additive）／階層。

**今後（v1 対象外・必要になったら DimML スキーマを拡張）**: junk dimension（低カーディナリティのフラグ束）／mini-dimension（頻繁に変わる属性の切り出し）／bridge table（多対多・多値ディメンション）／factless fact（イベント発生の記録・カバレッジ）／outrigger（ディメンションが別ディメンションを参照）／SCD Type 0/3/4/6/7。

これらは概念としてセッション中に言及してよいが、DimML では `note` に記述して「今後の拡張」として印を付ける。
