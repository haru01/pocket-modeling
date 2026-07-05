# EventStorming 自動シミュレーション 作業ログ（2026-07-03）

## 概要

- **目的**: `eventstorming-facilitator` スキルをフェーズ1〜7で自動完走し、実際の摩擦を記録してスキル改善点を抽出する（シミュレーション駆動改善の初回）
- **題材**: EC 注文管理（注文〜決済〜在庫引当〜出荷〜キャンセル/返品）
- **体制**: ファシリテーター = メインループ（SKILL.md に忠実）／ドメインエキスパート = general-purpose サブエージェント（EC 事業の業務責任者ペルソナ）
- **セッションファイル**: `docs/eventstorming/eventstorming-20260703-2143.dml.yaml`
- **凡例**: 🔁 = dmlctl リトライ発生 ／ 💡 = hint 使用 ／ ⚠️ = 摩擦メモ（スキル改善の一次証拠）

---

## ターンログ

<!-- 各ターン: フェーズ / 質問 / 回答要旨 / dmlctl 操作と結果 / 摩擦メモ -->

### 準備

- `dmlctl init docs/eventstorming/eventstorming-20260703-2143.dml.yaml --session-id=ec-order-20260703 --domain=ec-order-management --goal='（フェーズ1で確定）'` → 一発成功（build + validate 自動実行）
- ⚠️ init 時点で goal が未確定なのにフラグが要求される気がして仮文字列を入れた。実際は `--goal` は optional なので不要だった（スキル手順では「フェーズ2で init」だが、セッションファイルを先に作りたい場合の goal の扱いが SKILL.md に明記されていない）

### T1（フェーズ1）

- **Q**: 今回一番明らかにしたいこと・困っていることは？
- **A 要旨**: 月2万件・キャンセル率3〜4%。①キャンセル受付と3PL出荷指示の競合（梱包開始後のキャンセルが週数件、システム外の電話・メールで調整）②CS「取消できました」と経理の返金未処理のずれ→「お金が戻らない」クレーム月数件
- **dmlctl**: なし
- メモ: 回答に2論点（キャンセル競合・返金ずれ）が含まれる。ゴールはこの2つを軸に確定する

### T2（フェーズ1 完了）

- **Q**: 対象範囲は「注文確定〜配送完了／返金完了」で合っているか？　カタログ・会員は対象外か？
- **A 要旨**: 範囲 OK。ただし配送後の返品（月150件、初期不良交換・イメージ違い）〜返金までは範囲に含めてほしい。法人まとめ買い（見積・請求書払い）は「お任せします」→ 合理的デフォルトで対象外とし Q1 に記録
- **dmlctl 操作**:
  - 💡 `hint --path=questions` / `hint --path=session.goal` → 期待型・example が明快。add の書式をそのまま流用できた
  - `set session.goal` ✅ ／ `advance --status=...` ✅（phase 1→2）
  - 🔁 `add --to=questions --dry-run` と本 add が **生 Python トレースバック `KeyError: 'questions'` でクラッシュ**。テンプレート由来の DML にトップレベルキー `questions` が存在しないため。`set --path=questions --value='[{...}]'` で回避（+1 コマンド往復）
- ⚠️ **摩擦（改善候補）**: `add --to=<未存在キー>` は (a) 空リストを自動作成して append するか、(b) 「`set --path=questions --value='[...]'` を使え」という親切なエラーにすべき。hint の example が `add --to=questions --item=...` を提示するのに、テンプレ直後の DML ではその example がそのまま失敗する、という不整合が特に混乱を招く。dry-run も同じクラッシュをするので「書く前の安全確認」として機能しなかった

### T3（フェーズ2）

- **Q**: トラブルのない一番普通の注文の時系列は？
- **A 要旨**: 注文確定 → PSP 与信 OK → 受注確定＋確認メール（即時）→ **1日3回（9/13/17時）のバッチ**で 3PL へ出荷指示 → ピッキング・梱包 → ヤマト/佐川へ引き渡し＋送り状番号返却 → 「出荷済み」＋発送メール → **売上確定は出荷時**（与信と売上確定の2段階）→ 1〜3日で配達
- **dmlctl**: なし
- メモ: バッチが「キャンセル競合」の構造的原因であることが早くも見える。与信/売上確定の2段階は返金フローに効く

### T4（フェーズ2）

- **Q**: キャンセル依頼の流れは？（止められるケース／梱包開始後のケース）
- **A 要旨**: CS がメール/電話で受付（CS 用語は「取消」）。**バッチ前**: 受注管理で取消 → 次バッチから外れる → PSP へ与信取消で完結。**バッチ後**: 3PL 窓口へ電話依頼 → ピッキング前なら止まる/梱包後は間に合わない → **「取消依頼中」ステータスはシステムに存在せず担当者の Excel 管理**、システムは「出荷指示済み」のまま → 結果は 3PL からメール → 取消 or 「お届け後に返品扱い」案内に分岐
- **dmlctl**: なし
- メモ: 用語ゆれ（CS「取消」/物流「キャンセル」）を lang に記録する必要。「Excel 管理・ステータス不在」はモデルのギャップとして後で decisions/queries 候補

### T5（フェーズ2）

- **Q**: お届け後の返品〜返金の流れと、CS/経理のずれの発生箇所は？
- **A 要旨**: CS が理由確認（初期不良/顧客都合で送料負担が変わる）→ 返品受付番号発行 → 3PL 倉庫へ返送・検品 → 「返品入庫」連絡 → CS が返品確定＋「返金処理いたします」メール（**CS はここで対応完了扱い**）→ 実際の返金は経理が**週2回（火・金）バッチ**で PSP 管理画面から操作 → カード明細反映に1〜2週間 → 最悪3週間ギャップで再入電。コンビニ/銀振は口座確認が挟まりさらに遅い
- **dmlctl**: なし

### フェーズ2 完了（narratives 書き出し）

- **dmlctl 操作**: 💡 `hint --path=narratives` → `set --dry-run` → `set`（happy 1 + alt 3 本、マルチライン YAML を `--value` インラインで投入）→ `advance`（2→3）。**すべて一発成功**。dry-run→本書き込みの流れはスムーズ
- `open dist/...html` 初回起動 ✅、`Read` でプレビュー反映 ✅
- ⚠️ **摩擦（改善候補・ビルダーのバグ）**: ビルド済み HTML の `<title>` が `{{ドメイン名}}` のまま**未置換**（19行目）。本文 `<h1>` は「EventStorming — ec-order-management」と正しく生成されており、`<head>` 側だけテンプレ置換が漏れている
- ⚠️ **摩擦（改善候補・テンプレの陳腐化）**: 出力 HTML の冒頭コメント（1〜15行目）が「MD ファイルの対応セクションを HTML 化」「フェーズ2完了で Write 新規作成→ Edit で更新」という **v5 以前の廃止済みワークフロー説明のまま**出力に混入している。読者（と AI）を混乱させる
- ⚠️ **摩擦（軽微・スキル手順）**: フェーズ完了ごとに `Read dist/*.html` が必須だが、HTML は数千行あり全文 Read はコンテキストを圧迫する。プレビュー反映が目的なら「limit 付き Read で可」と SKILL.md に明記してほしい（今回は limit=60 で代替）

### T6（フェーズ3）

- **Q**: 在庫引当のタイミングと在庫不足時の扱いは？
- **A 要旨**: ⚠️ **同一質問に 2 通の回答が届き内容が食い違う**（シミュレーション基盤の都合で同一エージェントが2回走った模様）。共通部分: 注文確定時に受注管理側の帳簿在庫から引当／実在庫は 3PL 側にあり定期同期／ずれると出荷指示後に欠品連絡（月20〜40件）／欠品時は入荷待ち or キャンセルを顧客に確認。相違部分: 同期頻度（1時間ごと＋楽天併売説 vs 夜間1回突き合わせ＋棚卸差異説）。相違は Q2 として記録し後で確認。追加収穫: 入荷待ち中の与信期限切れリスク、セール時の売り越し、「欠品キャンセル」は CS 集計上の別区分（システム操作は同一）
- **dmlctl 操作**:
  - 💡 `hint --path=contexts` / `--path=scenarios` / `--path=contexts.lang` → 期待型・必須キー（scenarios は name/ctx/actor 必須）が事前に分かり有効
  - `set contexts`（6 BC + lang 識別子）dry-run → 本書き込み ✅ ／ `set scenarios`（仮21件・pivotal 4件）dry-run → 本書き込み ✅ ／ `add questions Q2` ✅（既存リストへの add は正常動作）
- ⚠️ **摩擦（軽微・dmlctl UX）**: `set --no-postprocess` は**成功時に何も出力しない**。dry-run は2行出すのに本書き込みが無言なので、成功か no-op か判別できず `view` で確認する往復が発生した。「✅ set contexts (6 items)」程度の確認行がほしい
- ⚠️ **観察（スキル設計）**: フェーズ3で scenarios[].ctx が必須のため、BC 境界を議論する前（フェーズ4.5より先）に暫定 BC 名を決めざるを得ない。SKILL.md に「フェーズ3の ctx は仮置きで良い・4.5 で見直す」という明示があると迷いが減る（今回は勝手に6 BC を仮置きした）

### T7（フェーズ3 完了）

- **Q**: イベント一覧の抜け・順序違いは？
- **A 要旨**: 4系統の抜けを指摘。①**前払い系（15%）**: コンビニ・銀振は入金確認まで受注確定せず、入金待ち1週間で自動キャンセル ②**返品検品NG**（月数件、揉め筋）: お断り返送 or 一部返金 ③**持ち戻り返送**（不在・受取拒否で月100件、返品とは別扱い）→ 再送 or 取消 ④**「配達された」はシステムで拾えていない**（配達完了データ未連携、CS が追跡ページ手動確認、社内的な終端は「出荷済み」）
- **dmlctl 操作**: `add scenarios ×4`・`update scenarios（note）`・`update contexts（lang merge-yaml）×4`・`add questions Q3`・`advance`（3→4）— 全て成功。`--merge-yaml` の再帰マージで lang の既存キーを壊さず追記できた（快適）
- ⚠️ **摩擦（軽微・dmlctl UX）**: 出力の非対称。`update` は `--no-postprocess` でも「✅ 1件更新しました」を出すが、**`add`/`set` は無言**。同一トランザクション内で成功確認の粒度が揃っておらず、無言コマンドの成否は最後の build/validate 行から間接推測するしかない
- メモ: 「配達完了イベントの不在」はモデリング的に面白い論点（システム境界の外の事実）。H2 相当として Q3 に記録

### T8（フェーズ4）

- **Q**: 返品確定後、経理はどうやって返金対象を知るか？
- **A 要旨**: **返金待ちステータス・一覧はシステムに無い**。CS が共有スプレッドシートに手動で1行記帳（注文番号・金額・決済方法・理由）→ 経理が火金にシートを上から見て PSP 管理画面で1件ずつ返金 →「済」記入。事故パターン: 書き忘れ（返金が永遠に停止）／催促で焦って二重記帳（二重返金未遂）／金額誤記／銀振返金の「口座待ち」が何週間も滞留（CS と経理がお互い様子見）
- **dmlctl**: なし（次ターンでまとめて反映）

### T9（フェーズ4）

- **Q**: 出荷停止が成功した後の後始末は？（在庫の戻し含む）
- **A 要旨**: バッチ前取消は引当が自動で外れサイト在庫も即戻る（SAME-TX）。バッチ後の停止成功は 3PL が棚戻しして実在庫は正しくなるが、**受注管理は「出荷指示済み」のまま**なので CS が 3PL の停止完了メールを目視して手動取消。見落とすと帳簿在庫が引当のまま＝サイト在庫なし表示の機会損失。夜間同期は**差異アラートのみで自動補正なし**（Q2 の「夜間1回」説を裏付け）
- **dmlctl 操作（フェーズ4の一括反映）**:
  - バッチA: happy チェーン next ×7・narratives entry ×4・alt-prepaid narrative 追加 ✅
  - バッチB: 分岐 brs（前払い/欠品/停止/検品NG/持ち戻り）×8・scenario 統合削除 ×2・検品NG協議 scenario 追加 ✅（`brs[].next` で分岐ごとのルーティングが書けるのが判明し設計が素直になった）
  - バッチC: policies 5件・lang 追補・up/dn（rel: Customer-Supplier / Conformist を使用）・BC description 6件
- 🔁 **摩擦（hint の限界）**: バッチCで `policies/0: 'qry' is a required property` の schema 違反。原因は **`bulk: true` のとき `qry` 必須という条件付き必須**（schema の allOf/if-then）。💡 `hint --path=policies` は静的 required（name, ctx）しか表示せず、条件付き必須を予見できなかった。エラーメッセージも「なぜ qry が要るのか」（bulk との連動）を説明しない。※ dry-run を省略した自分の運用ミスでもある（初カテゴリ policies なのに dry-run を踏まなかった）
- ✅ **好材料**: `check --check=narrative_entry_consistency` の指摘メッセージが「dict 形式に書き換えるか brs[].terminal を使え」と修正方法まで具体的で、1発で直せた
- ⚠️ **観察（チェックの厳格さ）**: happy / alt-prepaid の分岐点は entry の1つ先（在庫引当）なのに、チェックは entry scenario 自体に dict を要求する。同値 dict（happy も alt-prepaid も同じ次先）を書かされるのはややノイズ。「分岐が下流にある場合は許容」の余地があるかも
- ⚠️ **観察（schema 表現力・ギャップ分析⑦の実証）**: 「入金なく1週間」「1日3回バッチ」「火金の週2回」「与信有効期限」— **時間・期限・SLA の一級表現が DML に無く**、すべて note と cond の散文に逃がした。EVENTUAL-TX の遅延許容（`within`）提案は実地でも必要性が裏付けられた

### T10（フェーズ4.5 完了）

- **Q**: 事業の勝負どころと「世間並みで良い」部分は？
- **A 要旨**: 速さ・価格では大手に勝てず、選ばれる理由は**「買ったあとの安心」（リピーター率4割超の源泉）＝キャンセル・返品・返金対応そのもの**。決済・倉庫内作業・配送は完全外部任せで良い。ただし委託先との**「境目」の判断権（出荷停止・返品可否）は自社が握る**必要があり、今その境目が電話とメールなのが問題。メーカー直仕入れは範囲外と自己申告
- **dmlctl 操作**: 💡 `hint --path=domains` → `hint --path=domains.subs`（**ネストの中身は2回目の hint が必要**だった。array<object> 表示で内側の型が見えない）→ `set domains`（CORE 1・SUPPORTING 2・GENERIC 2）→ `contexts[].sub` 割当 ×6 → 多義語 vos（在庫: 帳簿/実、完了: CS/経理、キャンセル: 取消/キャンセル、返品/持ち戻り）→ `check subdomain_classification` 0違反 ✅
- ⚠️ **摩擦（軽微・hint UX）**: `hint --path=domains` は `subs: array<object>` としか出ず、subs の中の required/enum を見るには `hint --path=domains.subs` の追加呼び出しが要る。ネスト構造は1回で展開表示してくれると往復が減る
- メモ: 「CORE=アフターケア」は goal と綺麗に整合。同一 EN 識別子 `Cancellation` を CS と物流の両 BC に意図的に置いた（用語ゆれの as-is 記録）— phase 7 の bc_vocabulary_collision チェックがこれをどう扱うか観察する

### T11（フェーズ4.6 完了）

- **Q**: 受注管理の注文ステータス一覧と遷移可否は？
- **A 要旨**: 7値（入金待ち/受注確定/**保留**/出荷指示済み/出荷済み/取消/返品）。本線は 入金待ち→受注確定→出荷指示済み→出荷済み（カードは受注確定から開始）。**「取消」はどのステータスからも選べてしまう**（出荷済み誤取消の過去事故→運用ルールで縛るのみ）。**「保留」が何でも入れ**（欠品入荷待ち/不正確認/法人請求書。理由は備考欄頼み）。**「取消依頼中」「返金済み」が存在しない** — 返品ステータス≠返金完了が認識ずれの根っこ（本人も自覚）
- **dmlctl 操作**: 💡 `hint --path=aggregates` / `--path=aggregates.states` → **states は UPPER_SNAKE 配列で日本語ラベルは lang.states 側**という分担が hint で判明（往復ゼロ）→ `set aggregates`（6集約: Order/Payment/StockItem/Shipment/ReturnCase/RefundRequest、purpose/background/constraints/states）dry-run→本書き込み ✅ → `contexts[].aggs` 名簿＋`lang.states` ラベル ×6 ✅
- メモ: Payment 集約は「自社システムに実在しない（PSP 管理画面とシートが実体）」という as-is の歪みを background に明記。これが goal の認識ずれ問題の構造的説明になっている

### T12（フェーズ5 完了）

- **Q**: 受注確定にできない・しないケースは？（不正チェックの実態含む）
- **A 要旨**: ①与信NG＝その場でエラー・注文不成立 ②不正チェック: 転売容易商材×初回×複数個・届け先≠請求先・要注意リスト該当を**システムが自動保留フラグ＋受注チームが朝目視**。電話本人確認、3日不通で取消。**判断が属人的**（ベテランと新人で割れる）③住所不備は確認まで保留 ④注文直後の変更依頼も手動保留
- **dmlctl 操作**: 💡 hint ×5（transitions/events/rules/errs/queries）→ 集約6件へ transitions/attrs/events を merge-yaml ✅ → scenarios 8件へ rules/errs/agg を merge-yaml ✅ → FraudScreeningPolicy 追加 ✅ → queries 5件（シート/Excel 代替のリードモデル候補を as-is 課題直結で選定）✅ → validate/build 一発通過
- 💡 **好材料**: hint で `params: array<attribute>`・`transitions required [from,to,via]` が事前に分かり、フェーズ5の大量書き込み（merge-yaml 14連発）が**リトライゼロ**で通った。hint → dry-run → merge-yaml の運用が確立してからは型起因の往復が消えている
- ⚠️ **観察（スキル手順）**: フェーズ5は書く内容が多い（rules/errs/transitions/attrs/params/queries の6種）。SKILL.md には「どの scenario に rules/errs を書くべきか」の選定基準がなく、全 scenario に義務的に書くのか要所だけで良いのか迷った。今回は goal 直結の8 scenario に絞った（`coverage` view で後から穴が見える想定）

### T13（フェーズ6）

- **Q**: 在庫同期の2説はどちらが正しいか？（Q2 の直接確認）
- **A 要旨**: 「1時間ごと同期」は**本人が発言自体を否定**（シミュレーション基盤都合の二重回答による混入と確定）。正: 帳簿在庫は受注管理内で即時（注文で減・取消で戻）／3PL からの入庫データ取込は日中数回／実在庫との突き合わせは夜間1回・差異アラートのみ・翌朝人間が修正
- **dmlctl**: inventory description 修正・Q2 note 更新

### T14（フェーズ6 完了）

- **Q**: 配達完了イベントの扱いは (a) 出荷済み終端＋注記 / (b) 業務イベントとして正式扱い？
- **A 要旨**: **(b) 採用**。理由3つ: ①返品受付期限が「商品到着から14日」なのに到着日をシステムが知らず CS が追跡ページで手数え ②持ち戻り月100件は「不在3回」時点の先回り連絡で相当防げる ③「届きましたか」問い合わせが1日20〜30件全部手動。名言「今できてないだけで、無い出来事ではない」
- **dmlctl 操作**: `set decisions`（D1〜D6）→ `update questions` ×3（closed + decision_id）→ 💡 `hint --path=actions` → `set actions`（A1〜A5）→ 返品期限14日ルールを rules に追記（merge-yaml はリーフ置換なので rules 全体を set し直し）→ `advance`（6→7）
- ⚠️ **観察（dmlctl UX）**: `--merge-yaml` はリーフ（配列）を**置換**するため、「既存 rules に1件追記」でも配列全体を再送する必要がある。`add --to=scenarios[name=…].rules --item=…` のようなネストリストへの append が効くか未検証だった（あとで確認したら効きそうな構文はある — セレクタ付き add の対応状況を findings で確認する）

### T15（フェーズ7・構造チェック）

- **`check --all`: 19観点中7観点で29違反** → 全件是正して **0違反**（2ラウンド）
- **検出内訳と評価**:
  - `orphan_agg` ×2（Payment/Shipment が scenario 未参照）→ 正当。agg 付与漏れを機械検出できた
  - `dangling_cmd` ×3（transitions の via が scenario 未宣言）→ 正当。ClearHold 等「会話に出たが scenario 化していない手動オペ」を炙り出し、scenario 3件の追加につながった（**チェックがモデルの穴を発見する好例**）
  - `language_coverage` ×12（AGG 6 + POL 6 が lang 未登録）→ 正当だが、**aggregates[] / policies[] の追加時に lang 登録も必要という2重管理**は書き手の負担。dmlctl 側で自動同期または警告があると楽
  - `state_reachability` ×1（AWAITING_ARRIVAL 未到達）→ 正当。わざと残した検証用の穴を正しく検出。REQUESTED に統合して解消
  - `dangling_lang_entry` ×4 → 正当。わざと残した ReportStockout（フェーズ4で brs に統合した際の残骸）を正しく検出
  - `decision_chosen_adopted` ×6 → **摩擦**: `chosen: <name>` と `options[].adopted: true` の**二重記載が要求される**。chosen だけで一意に決まる情報であり、スキーマか check どちらかで自動化・省略可能にすべき。6件全部同じ機械的修正だった
  - `bc_vocabulary_collision` ×1（Cancellation の BC 間ラベル差）→ 検出は正当（意図的に仕込んだ用語ゆれ）。ただし**メッセージの解消手段（「note で Conformist/ACL を明示」）が lang.vos の構造では実行不可能**（vos は key→string でエントリ単位の note フィールドが無い）。ラベル文字列を両 BC で同一にして回避した
- **好材料**: ネストセレクタ update（`--path='decisions[id=D1].options' --where='name=...'`）が期待通り動作。JSON 出力は `python3 -c` でのメッセージ抽出が必要（29件を生 JSON で読むのはノイズ）— `--format=summary` 的な人間向け出力があると良い

### T16（フェーズ7・意味チェック6観点 → 反映）

- **実行**: 6観点を general-purpose Agent 並列で起動（各観点 `checks/*.md` + 指定 view のスライス）。全観点が構造化された指摘を返した（計24件前後）
- **⚠️ 最重要発見（view のバグ/制約による系統的誤検知）**: `flow-causality` view が **`brs`（分岐 cond/evt/分岐先 next/terminal）を完全に落とし、分岐先チェーンも辿らない**ことを実測で確認。scenario の evt は brs のどれか1つに潰され、欠品意向確認・検品NG協議・持ち戻り再送確認・入金期限切れ自動取消の各チェーンが view 上「存在しない」ことになっていた。結果、saga-completeness / causal-chain-completeness の指摘のうち少なくとも次の4件は**モデル済みなのに欠落と誤指摘**: ①前払いタイムアウト分岐 ②出荷停止の成功分岐 ③検品NG分岐 ④停止失敗→返品への誘導。**意味チェックの信頼性は view の忠実性に律速される**という構造的知見
- **正当な指摘（反映済み）**:
  - 与信NGエラーの配置矛盾（PlaceOrder→AuthorizePayment へ移動）— フロー因果を読んだ的確な指摘
  - StockoutAtWarehouse の二重表現（バッチ送信 err を削除しピッキング brs に一本化）
  - RefundNeverQueued は「cmd が起動されない」ので errs の型に合わない（削除し policy note へ）＋ DuplicateRefundAttempted / ReturnWindowExpired の rule↔err 対応を追加
  - 「客が商品を返送する」step の欠落（scenario 追加）
  - FraudScreeningPolicy の帰結イベント不在（evt: OrderHeld 付与）
  - constraints の性格ずれ（Order の備考欄問題・RefundRequest の火金バッチを background へ）
  - decisions の affects 実在性（D4 が存在しない識別子 `Cancellation` を参照）・粒度・why の具体性 → 全是正、Hold 同語異義は D7 に昇格
  - `refs`/`rename` で ClearHold→ReleaseHold を一括改名（辞書キー・cmd 値・transitions via の3箇所を dry-run 付きで正確に置換。**体験が非常に良い**）
- ⚠️ **摩擦（schema 表現力）**: RefundSheetRegistrationPolicy への複数トリガー（ReturnConfirmed / RedeliveryCancelled / PartialRefundAgreed の **OR**）が表現できない。`trgs` は join（Σ・AND）専用で、OR は policy を経路別に分割するしかない
- ⚠️ **摩擦（チェック仕様）**: causal チェッカーが「最終 step に terminal 宣言を」と提案したが、schema 上 scenario に terminal キーは無く（brs 分岐のみ）、「next 省略=終端」が正。**view が terminal: false を合成表示する**ことが誤解の元
- **最終状態**: `check --all` 0違反 / schema OK / HTML 9セクション生成 / D1〜D7・A1〜A5 / coverage 上の残欠は補助 scenario 4件の rules/errs のみ（goal 非直結のため意図的に省略）

---

## シミュレーション基盤に関する注記（スキル外）

- SendMessage でのエキスパート継続時、**同一質問に2回回答が走り内容が食い違う**事象が1回発生（T6）。偶然だが「証言ゆれ→ホットスポット→Q2→本人確認→D2 で解消」という現実さながらの検証ループの練習になり、スキルの `[?]`→questions→decisions 導線が正しく機能することを確認できた

---

## 定量指標

| 指標 | 値 | 備考 |
|---|---|---|
| エキスパートとの対話ターン | 14（T1〜T14） | フェーズ別: P1=2 / P2=3 / P3=2 / P4=2 / P4.5=1 / P4.6=1 / P5=1 / P6=2（P7 は対話なし） |
| dmlctl 書き込みエラー（真のリトライ） | **2件** | ① `add --to=questions` の KeyError（未存在キー） ② `bulk: true`→`qry` 条件付き必須の schema 違反 |
| hint 使用回数 | 16 | 型起因の書き直しは hint 導入後ゼロ |
| dry-run 使用回数 | 6 | narratives / contexts / scenarios / aggregates / actions / rename |
| 構造チェック違反の推移 | 途中 1（narrative_entry_consistency）→ フェーズ7 で **29 → 0**（2ラウンド） | 29件中、意図的に仕込んだ検証用の穴 3件を全て検出 |
| 意味チェック指摘 | 6観点で約24件 → **正当≈14 / view 起因の誤検知≈8 / 実行不能提案 2** | 誤検知の主因は flow-causality view の brs 欠落 |
| 成果 DML 規模 | contexts 6 / aggregates 6 / scenarios 26 / policies 6 / queries 5 / decisions 7 / questions 3(全closed) / actions 5 / narratives 5 | schema OK・check --all 0違反 |
