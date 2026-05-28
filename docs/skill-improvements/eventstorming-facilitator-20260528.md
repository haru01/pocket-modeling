# eventstorming-facilitator スキル改善メモ

> セッション中に気づいた改善点を随時記録する。セッション終了後に整理して取り込む想定。
> セッション: タップカメラドメイン（2026-05-28）

## ★ セッション末でセクション構成を再編（2026-05-28）

ユーザー指示によりスキル本体（SKILL.md / template.md / quality-check.md / causal-check.md / causal-check-agent.md / html-render-spec.md / dml-spec.md / chat-output-format.md / scripts/eventstorming_build.py）に反映済み。

### v1（11→4／7→5／8→6）

| 新 # | 旧 # | セクション |
|---:|---:|---|
| 4 | 11 | 用語集（前置き表として早めに置く） |
| 5 | 7 | オープンクエスチョン |
| 6 | 8 | 意思決定ログ |
| 7 | 4 | コンテキスト候補 |
| 8 | 5 | 集約候補 |
| 9 | 6 | リードモデル候補 |
| 10 | 9 | 次のアクション |
| 11 | 10 | DML |

### v2（10→5、§5〜§9 を 1 つずつ下げる）

| 新 # | v1 # | セクション |
|---:|---:|---|
| 4 | 4 | 用語集 |
| **5** | **10** | **次のアクション** ← v2 で §5 に昇格 |
| 6 | 5 | オープンクエスチョン |
| 7 | 6 | 意思決定ログ |
| 8 | 7 | コンテキスト候補 |
| 9 | 8 | 集約候補 |
| 10 | 9 | リードモデル候補 |
| 11 | 11 | DML |

**最終コンセプト**: **物語（§1〜§3）→ 用語集（§4・前置き）→ 次のアクション（§5・読者の次の動き）→ 横断課題（§6〜§7: 質問・決定）→ モデル層（§8〜§10: BC/AGG/QRY）→ メタ（§11: DML）** の読者導線。

ステークホルダーが最初に読みたいのは「**物語と次の動き**」であり、技術詳細（モデル層）はオプショナル。

以降、本メモ内の §N 表記は **v2 番号** を指す。

---

## I1. SKILL.md「ワークフロー（8フェーズ）」の番号不整合
- **発見箇所**: `SKILL.md` のワークフロー見出しが「8フェーズ」だが、表内の番号は `1, 2, 3, 4, 4.5, 4.6, 5, 6, 7` で **計 9 フェーズ**
- **問題**: 数えるたびにずれを意識する。「8フェーズ」と呼ぶ根拠が見えない
- **改善案**:
  - (a) 見出しを「ワークフロー（9フェーズ）」に変更
  - (b) `4.5/4.6` を `4` の subphase 表記に揃え、トップレベルは 7 のまま「7フェーズ + サブステップ」と明示
- **優先度**: 低（実害は無いが認知負荷）

## I2. domains subdomain `type` enum の命名が非対称で誤りを誘発
- **発見箇所**: `references/dml.schema.yaml` の subdomain.type
- **現状の enum**: `CORE_DOMAIN` / `SUPPORTING_DOMAIN` / `GENERIC_SUBDOMAIN`
- **問題**: 3つのうち `GENERIC` だけが `SUBDOMAIN`、他は `DOMAIN`。`subs[]` の中なのに `_SUBDOMAIN` 接尾辞があったり無かったりで認知負荷が高く、`SUPPORTING_SUBDOMAIN` と書く typo を **本セッションで実際に踏んだ**
- **改善案**:
  - (a) 3つとも `CORE_SUBDOMAIN` / `SUPPORTING_SUBDOMAIN` / `GENERIC_SUBDOMAIN` に統一（フィールド名 `subs` と整合）
  - (b) 3つとも `CORE` / `SUPPORTING` / `GENERIC` に短縮統一（subdomain 配下なのは文脈で明らか）
- **優先度**: 中（typo を呼ぶ実害あり）
- **副次効果**: schema 変更時は既存セッション DML（`eventstorming-20260515-1901.dml.yaml` 等）の参照箇所を grep して同時更新が必要

## I3. SKILL.md「up/dn 必須」と schema 定義の不一致
- **発見箇所**: SKILL.md「DML 記述ルール」§要点 — *「`ctxs[]` に `up`/`dn` 必須（依存なしは空リスト `[]`、`rel` 併記）」*
- **schema 実態**: `references/dml.schema.yaml:208` の `context.required` は `[name]` のみ。`up`/`dn` は optional
- **問題**: 文書ルール（SKILL.md）と機械検証（schema）が異なる強度で運用されている。AI/人間が SKILL.md を真に受けて空配列を書いても schema は何も警告しないため、忘れても検出されない
- **改善案**:
  - (a) schema 側を強化（`context.required: [name, up, dn]`）して機械的に強制
  - (b) もしくは quality-check の D 系チェックに「ctxs[].up/dn 未記述」項目を追加
  - (c) 「依存なしを `[]` で明示」がそんなに大事でないなら SKILL.md 側を緩和（optional であると明記）
- **優先度**: 中（モデリングの厳密さに影響）

## I4. フェーズ 3「scs[] 仮 entries」のスコープが曖昧
- **発見箇所**: SKILL.md フェーズ完了表「フェーズ3完了 — scs[] 仮 entries」
- **問題**: scs スキーマは `name`/`ctx`/`actor` が必須。フェーズ 3 時点では BC が未確定（フェーズ 4 で BC 境界を拾うとされる）なのに、`ctx` が必須なため事実上 BC も同時に決めざるを得ない。「3 と 4 の境目」が運用上ぼやける
- **改善案**:
  - (a) フェーズ 3 では ctx を `unassigned` 等のプレースホルダ許容にし、4 で割り当てる運用にする（schema に enum 例外を追加）
  - (b) フェーズ 3 完了の説明文に「scs[] と同時に BC スケルトンも置く」と明示する
  - (c) フェーズ番号を再構成（3+4 を統合、または「BC ファースト」「EVT ファースト」で分岐ガイドを用意）
- **優先度**: 中（運用上のもやもや）

## I5. pols[] には agg を書けない（scs[] とのスキーマ非対称）
- **発見箇所**: `references/dml.schema.yaml` の `policy` 定義 — `agg` プロパティが無い
- **scs[] 側**: `agg: { $ref: pascalCase }` あり（任意）
- **問題**: POL も `cmd` を発行して AGG 状態を変える（例: `SettleOnAppraisalApproved` の `SettleTradeIn` cmd は `TradeIn` AGG を settled に遷移）。POL がどの AGG を変更するか追跡できないと、フェーズ 4.6/5 の `aggs[].transitions[]` を埋める際に、`pols[].cmd → scs?` の逆引きが必要になる
- **本セッションで実際に踏んだ**: フェーズ 4 で `pols[].agg` を 7 件書いて schema 違反
- **改善案**:
  - (a) `policy.properties` に `agg: { $ref: pascalCase }` を追加（scs と対称化）
  - (b) ルール上「POL は AGG を変更しない・配信専用」と定義し、状態遷移は受信側 scs で書く運用にする（dml-spec.md の明文化）
- **どちらかと言うと (a)** — POL の cmd 発行先 AGG は実装上明らかに必要な情報
- **優先度**: 中

## I6. quality-check が「§11 用語集に AGG 表が無い」を S7 ホットスポットで検出
- **発見箇所**: フェーズ 4 完了時の品質チェック agent 結果（`[?] S7_aggs-glossary`）
- **問題**: テンプレ `references/template.md` §11 には **アクター / コマンド / イベント / ポリシー / リードモデル** の 5 表しかなく、AGG 表が無い。一方、quality-check は scs[].agg の出現で `S7_aggs-glossary` を flag する仕様
- **本セッションで実際に踏んだ**: フェーズ 4 で `scs[].agg` を 12 件書いた時点でホットスポット化、フェーズ 4.6 を待たずに §11 へ AGG 表を追加して対応
- **改善案**:
  - (a) `references/template.md` §11 に「集約 (AGG)」表を最初から含める
  - (b) もしくは §11 から AGG 表を不要とする運用にし、quality-check 側で `S7_aggs-glossary` を緩める
- **優先度**: 低（テンプレ 1 行追加で解決）

## I9. quality-check agent が §4 を誤って「DML 自動生成セクション」マーカーに変更（実害あり）
- **発見箇所**: フェーズ 4 完了時の quality-check agent（S6 自動修正）が `/docs/eventstorming/<session>.md` §4「コンテキスト候補」を、テンプレ規約の `### english-slug（日本語名）` 本文形式から、§3/§5/§8 と同じ DML 自動生成マーカー文言に書き換えた
- **問題**: SKILL.md と `references/template.md` 両方で §4 は **AI/人間編集セクション**（`### english-slug（日本語名）` 必須）と明記されているのに、quality-check が「§3/§5/§8 と同じスタイル統一」とみなして自動上書きしてしまった
- **本セッションで実際に踏んだ**: ユーザーが HTML を開いた際「§4 が出力されない」と指摘してくれて発覚。書き直し対応が必要に
- **改善案**:
  - (a) `references/quality-check.md` の S6 ルールに「§4 は AI/人間編集セクション。マーカーへの自動上書き禁止」を明記
  - (b) quality-check agent プロンプトに「自動修正対象は **明確な表記違反のみ**。本文を空 / マーカーに置換する変更は自動修正で行わず、ホットスポット候補に降格する」と明記
  - (c) `template.md` の §4 説明に「このセクションは AGG 候補と並び `.md` 本文を書く側。フェーズ 4 完了時に必ず充足すること」と強調
- **副次効果**: §3/§5/§8 と §4 の責務（DML 駆動 vs .md 駆動）が混在しているため、quality-check 実装側で「.md 駆動セクションの ID 一覧」を schema 化する案も検討余地あり
- **優先度**: 高（agent 誤動作で本文消失 → ユーザー指摘で発覚というワークフロー破壊）

## I7. 因果チェック (C4) で「孤立 EVT」が正常運用と区別できない
- **発見箇所**: causal-check の C4（孤立イベント検出）結果
- **検出された孤立 EVT**: `EstimateCalculated` / `TradeInItemShipped` / `TradeInItemReceived` / `InspectionCompleted` / `DifferentialAuthorized` / `ShipmentInstructed` / `TradeInCancelled`
- **問題**: これらは「次工程に進めるはずなのに POL/EVT 連鎖が無い」場合と、「業務上ここで一旦止まる（人手判断 or 観測のみ）」場合の **両方を孤立として平等に flag する**。後者は意図的でモデルとして正しいが、毎回 Q として追記され続けて誤検出（false positive）になる
  - 例: `EstimateCalculated` は会員の判断待ち（ECらしい正常な離脱可能ポイント）
  - 例: `DifferentialAuthorized` は与信の完了状態、次工程は会員の発送行動待ち（人間が動く）
- **改善案**:
  - (a) scs/pols に `terminal: true` のような明示フラグを追加し、孤立判定から除外可能にする
  - (b) `note` に特定マーカー（`[terminal]`, `[await-human]`）を書いた場合は C4 をスキップ
  - (c) causal-check のレポートを「孤立（要確認）」と「孤立（明示 terminal）」に分けて出す
- **副次的提案**: 連続セッションで Q が増殖し続けるのを抑える運用ガイドが必要
- **優先度**: 中（false positive で開発者の信頼を損なう可能性）

## I8. render_progress の regex が Status 表記揺れ（半角スペース）でマッチ失敗 ★本セッションで修正済み
- **発見箇所**: `scripts/eventstorming_build.py` `render_progress()` (line 786-805)
- **問題**: regex `r"フェーズ4"`（スペース無し）が、実運用の Status 表記 `フェーズ 4 完了`（半角スペース有り）にマッチせず、全フェーズが「未到達」扱いで先頭「1. スコープ」が current に固定化されていた
- **本セッションで実際に踏んだ**: フェーズ 2〜4 完了を経ても HTML 進捗バーが「1. スコープ current」のままだった（ユーザーがスクリーンショットで指摘）
- **修正内容**: 9 件の regex を `r"フェーズ\s*N"` に変更し、半角/全角スペースを許容
- **副次対応**: 既存セッション（`20260515-1901` / `20260525-1331`）も同じ問題を抱えていた可能性あり → `eventstorming_build.py --all` で再ビルドして反映
- **再発防止案**:
  - (a) `references/template.md` に「Status 行の表記は `フェーズN 完了（説明）` でスペースは任意」と明記する
  - (b) Status 行のパースをより厳格に：例えば `re.search(r"フェーズ\s*([0-9](?:\.[0-9])?)", status)` で数値を抽出して比較
  - (c) ビルダーに warning を出す（status が認識できないときに stderr に出力）
- **優先度**: ★高（コア機能の見た目バグ）→ 修正済み・再発防止策は (b) を本命に検討
