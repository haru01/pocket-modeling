# eventstorming-facilitator スキル改善提案 — 自動シミュレーション初回（2026-07-03）

**出典**: EC 注文管理ドメインのフェーズ1〜7完走シミュレーション。一次証拠は [20260703-simulation-log.md](20260703-simulation-log.md) のターン番号（T*）で参照。
**体制**: ファシリテーター=メインループ（SKILL.md 忠実準拠）／ドメインエキスパート=サブエージェント。既存机上分析 [20260703-ddd-es-coverage-gaps.md](20260703-ddd-es-coverage-gaps.md) の未反映提案の実地検証を兼ねる。

---

## P1（品質に直結・優先）

### ① flow-causality view が brs 分岐を欠落させ、意味チェックが系統的に誤検知する（T16）— ✅ 反映済み（2026-07-04）

> 対応: views.py を branches[]（brs verbatim + taken）・sidetracks[]（非選択分岐の展開チェーン）・scenario-ref（合流参照）対応に書き換え、`terminal: false` 合成を廃止。checks md 2件と quality-check.md に読み方を追記。unittest 15ケース新設（smoke test に組込）。意味チェック2観点の再実行で誤検知4件が全て消滅し（alt-cancel-race は complete 判定へ転換）、指摘が本物のモデル課題のみになったことを確認。

- **事実**: view は scenario の `brs`（cond / 分岐 evt / 分岐先 next / terminal）を出力せず、evt を1つに潰し、`brs[].next` で繋いだ分岐先チェーン（欠品意向確認・検品NG協議・持ち戻り再送・入金期限切れ自動取消）を辿らない。さらに schema に存在しない `terminal: false` を合成表示する
- **影響**: saga-completeness / causal-chain-completeness の指摘の約1/3（今回4件以上）が「モデル済みなのに欠落」という誤検知。**意味チェックの信頼性は view の忠実性に律速される**。チェッカーが「terminal 宣言を付けよ」という schema 上実行不能な提案までしてくる
- **提案**: `dml_filters/views.py` の flow-causality を brs 込みの構造（step 内に branches: [{cond, evt, next, terminal}]）へ拡張し、brs[].next の先も steps に含める。terminal の合成をやめ「next 省略=終端」を明記

### ② `add`/`set` が未存在トップレベルキーで生 Python トレースバックを吐く（T2）— ✅ 反映済み（2026-07-05）

- **事実**: テンプレ直後の DML に `questions` が無い状態で `add --to=questions` → `KeyError: 'questions'` の生トレースバック。`--dry-run` も同様にクラッシュし安全確認として機能しない。**hint の example（`add --to=questions --item=...`）がそのまま失敗する**という不整合が混乱を増幅
- **提案**: add は未存在の親リストを自動作成して append（最小差分）。少なくとも「トップレベル `questions` が未作成です。`set --path=questions --value='[...]'` を使うか、この add に `--create` を付けてください」という誘導エラーに

> 対応: `cmd_add` を `_resolve_parent` ベースに書き換え、未存在の末端リストキーは空リストを自動生成。中間キー欠落・`_Selector` 不一致は exit 2 の友好エラー（Traceback 抑止で dry-run も機能）、トップレベルの typo キーは有効キー一覧つき exit 2 で即弾く。smoke test に回帰3ケース追加。

### ③ hint が条件付き必須（allOf/if-then）を表示しない（T9）— ✅ 反映済み（2026-07-05）

- **事実**: `hint --path=policies` は required=[name, ctx] のみ表示。実際は `bulk: true` のとき `qry` 必須で、書き込み時に「'qry' is a required property」という**理由の見えない**違反になった
- **提案**: hint に条件付き必須の要約行を追加（例: `conditional: bulk=true → qry 必須`）。validate のエラーにも該当 if-then のヒントを添える

> 対応: `hints.py` の `_describe` に allOf/if-then/not 解釈を追加し、hint に `conditional`（bulk: true のとき qry 必須／brMode のとき brs 必須）と `exclusive`（trg/trgs・evt/brs・next/terminal）を表示。`validate_dml.py` の required エラーにも条件付き必須のヒントを添付。unittest（test_hints.py）7ケース新設。

## P2（体験・表現力の改善）— 全件 ✅ 反映済み（2026-07-05）

### ④ 時間・期限・SLA の一級表現が無い — 机上ギャップ分析⑦を実地で強く裏付け（T9, T14, T16）

- **事実**: 「1日3回バッチ」「入金なく1週間」「返金は火金の週2回」「返品は到着から14日」「本人確認3日不通」— ドメインの核心的な時間制約がすべて note / cond の散文に逃げた。タイマー起点の policy は trg を期限切れイベントで代用
- **提案**: 机上分析⑦の `policies[].within` に加え、`brs[].after`（タイムアウト分岐）程度の最小表現を検討。HTML §3 で ⏱ 表示できると競合問題（バッチ遅延窓）が視覚化される

> 対応（最小実装）: schema に `policies[].within`（遅延許容 SLA）と `brs[].after`（タイムアウト待機）を追加。`flow_causality` view が両フィールドを出力。dml-spec に節を追加。HTML の ⏱ 描画は将来対応（値は保持・未描画でも壊れない）。

### ⑤ policy の複数トリガー OR が表現できない（T16）

- **事実**: 返金シート記帳は ReturnConfirmed / RedeliveryCancelled / PartialRefundAgreed の**いずれか**で発火するが、`trgs` は join（AND・Σ）専用。OR は policy を経路別に複製するしかなく、「複数経路が同一シートに合流する＝二重記帳の温床」という構造こそ描きたいのに描けない
- **提案**: `trgs.mode` に or（exclusive）を許すか、`trg: [A, B]`（配列=OR）を導入

> 対応（Route B）: `branchMode` とは別に `triggerMode` enum を新設し `trgs.mode` に `all`(AND join)/`any`|`or`(OR) を許可（旧 `concurrent` 等は後方互換で温存）。trgs.evts 走査は全箇所が既に配列対応のためコード変更ゼロ。Route A（trg 配列化）は checks/views/build 5箇所を壊すため不採用。OR の意味論妥当性は saga-completeness の LLM 観点に委任。

### ⑥ decision_chosen_adopted が二重記載を強制する（T15）

- **事実**: `chosen: <name>` があるのに `options[].adopted: true` を別途要求され、6件全部が同一の機械的修正だった。情報として冗長
- **提案**: ビルド/チェック側で chosen から adopted を導出し、check は「chosen と adopted の**不一致**」だけを検出する仕様に変更

> 対応: `decision_chosen_adopted` の「adopted 0件」違反を削除し adopted を任意化（ビルダーは既に `adopted is None → name == chosen` で導出）。検査は `chosen ∈ options[].name`（必須）＋ adopted 明示時のみ「複数採用/不一致」を検出、に縮退。

### ⑦ bc_vocabulary_collision の解消ガイダンスが実行不可能（T15）

- **事実**: 指摘メッセージは「意図的な流用なら note で Conformist/ACL を明示」と言うが、`lang.vos` は key→string の辞書でエントリ単位の note フィールドが存在しない。ラベル文字列を両 BC で完全一致させる回避しかなかった
- **提案**: メッセージを実行可能な手段（ラベル統一 or 識別子分離 or `contexts[].note`）に書き換えるか、lang エントリの値に `{label, note}` 形式を許す

> 対応（メッセージ改善ルート）: 同名異義・異名同義の両メッセージを実行可能な3手段（①ラベル統一 ②`dmlctl rename` で識別子分離 ③`contexts[].note` に Conformist/ACL 明記＝lang エントリ単位の note は持てない旨も明示）に書き換え。`{label,note}` schema 化は費用対効果が低いため見送り。

### ⑧ HTML ビルダーのバグ2件（フェーズ2完了時に発見）

- `<title>` がテンプレの `{{ドメイン名}}` のまま未置換（本文 `<h1>` は正しい）
- 出力 HTML 冒頭に「MD ファイルを HTML 化」「Edit で該当セクション更新」という **v5 以前の廃止済みワークフロー説明コメント**が混入
- **提案**: build 時に title を session.domain で置換し、テンプレ冒頭コメントは出力から strip する

> 対応: `render_html` に `<title>` 置換と `<!DOCTYPE html>` 直後の冒頭コメント strip の re.sub を追加。（DML 全文ハイライト中に現れる `{{主人公}}` は DML ソース自身のコメントで、これは正しい忠実表示。）

### ⑨ dmlctl の成功出力が非対称（T7, T13）

- **事実**: `update`/`remove(要素)` は「✅ 1件更新/削除しました」を出すが、`add`/`set` は `--no-postprocess` 時に**完全無言**。成功か no-op か判別できず `view` での確認往復が発生した
- **提案**: 全書き込みコマンドで「✅ set contexts (6 items)」相当の1行確認を出す

> 対応: `cmd_set`（✅ 設定＋件数）・`cmd_add`（✅ 追加＋計件数）・`cmd_remove` の _Selector/単一フィールド分岐に確認行を追加。全書き込みコマンドが stderr に ✅ を出すよう対称化。

## P3（明文化・小改善）— 全件 ✅ 反映済み（2026-07-05）

- **⑩ フェーズ3の ctx 仮置きの明文化**（T6）→ ✅ SKILL.md の DML出力タイミング表直下に脚注（仮置き→4.5 で `rename --ctx` 一括見直し）
- **⑪ フェーズ5の rules/errs 選定基準**（T12）→ ✅ dml-spec §2 に新サブ節＋SKILL.md 脚注（全 scenario 義務でない・coverage 残欠は意図的許容と未着手を区別）
- **⑫ `Read dist/*.html` の limit 許容**（フェーズ2完了）→ ✅ SKILL.md 167行・chat-output-format.md に「limit 付きで可、preview 反映がトリガーできれば十分」
- **⑬ language_coverage の2重管理**（T15）→ ✅ doc リマインダで対応（template.dml.yaml の AGG/POLICY 節・session-guide フェーズ4.6・SKILL.md 脚注に「lang.aggs/lang.pols へ同時登録」）。自動登録コードは今回見送り
- **⑭ hint のネスト非展開**（T10）→ ✅ `_short` に depth を追加し1階層展開（`subs: array<object{name, type, vision}>`）。unittest 2ケース追加
- **⑮ check --all の人間向け出力**（T15）→ ✅ `check --all --format=summary`（観点×件数＋message 行）を追加。既定は json（後方互換）
- **⑯ narrative_entry_consistency の過剰要求**（T15 直前）→ ✅ `_diverges_downstream`（visited でサイクルガード）を追加し、下流に分岐点があれば合流区間の単一 next を許容。真に区別されないケースは引き続き検出

## 机上ギャップ分析（20260703-ddd-es-coverage-gaps.md）の実地検証結果

| 提案 | 実地検証の結果 |
|---|---|
| ② コンテキストマップ語彙のフル活用 | **schema は既に対応済み**（up/dn の rel enum に ACL/OHS/PL/Partnership あり）。今回 Customer-Supplier / Conformist を自然に使えた。残るのは「フェーズ4で rel を必ず問う」という**手順への組み込みのみ**（提案を縮小して反映可） |
| ④ 外部システムの一級表現（EXTERNAL） | **中程度の裏付け**。PSP・3PL・配送会社を BC の note で代用したが、「payment BC は実体としては外部 PSP への窓口」という説明が毎回 note 頼み。EXTERNAL マークがあれば HTML §6 で委託境界（今回の goal の核心「境目」）が一目になる |
| ⑤ Reverse Narrative チェック | **①の view 修正が先**。補償欠落（在庫解放）の検出は saga チェックが部分的に果たしたが、view の brs 欠落で精度が落ちており、7観点目を足す前に土台を直すべき |
| ⑥ 集約サイジング | **今回は裏付け弱**。競合・トランザクション境界の議論は自然発生しなかった（保留→D6 で代替） |
| ⑦ EVENTUAL-TX の遅延許容 SLA | **強く裏付け**（上記④参照。時間制約が5箇所すべて散文逃げ） |

## うまく機能した点（維持すべき設計）

- **hint → dry-run → merge-yaml の三点セット**: 確立後は型起因のリトライがゼロに（フェーズ5の merge 14連発も無事故）
- **`refs` / `rename`**: ClearHold→ReleaseHold の一括改名が辞書キー・cmd 値・transitions via を dry-run 付きで正確に置換。体験が非常に良い
- **構造チェックの検出力**: 意図的に仕込んだ穴3件（dangling lang、未到達 state、用語衝突）を全て検出。dangling_cmd は「会話に出たが scenario 化されていない手動オペ」を炙り出しモデルを実際に改善した
- **`[?]` → questions → decisions の導線**: 証言ゆれ（在庫同期）を Q2→本人確認→D2 で解消する流れが自然に機能
- **ネストセレクタ**（`decisions[id=D1].options` への update）と `advance` の enum 検証
