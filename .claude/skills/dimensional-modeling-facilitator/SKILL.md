---
name: dimensional-modeling-facilitator
description: Facilitate Kimball-style dimensional (data warehouse / BI) modeling sessions through conversation, producing DimML (Dimensional Modeling Language, YAML) as the primary artifact plus a bus-matrix + star-schema HTML. Use whenever the user wants to design fact tables, dimensions, a star schema, or a bus matrix — declaring grain, choosing SCD types, identifying conformed dimensions and measures (additivity) — by grilling one step at a time. Also invoke for refining an existing DimML, or when the user says "ディメンショナル・モデリング", "ディメンションモデリング", "スタースキーマ", "バスマトリクス", "ファクト表を設計したい", "グレインを決めたい", "DimML を育てたい", "Kimball で整理したい".
---

# ディメンショナル・モデリング ファシリテーター

会話で Kimball 流のディメンショナル・モデル（データウェアハウス／BI 設計）を発見し、**DimML（Dimensional Modeling Language、YAML）に情報圧縮する**。**`docs/dimensional/<session>.dimml.yaml` 1 ファイルがモデル唯一の真実源**。ここからバスマトリクス＋スタースキーマの HTML が機械生成される。

このスキルは EventStorming ファシリテーターとは独立した別成果物。DDD ではなく **分析（アナリティクス）モデリング**を扱う。

## 最重要の運用原則

- **DimML が唯一の真実源**。HTML は派生物なので手で編集しない。AI は DimML を**直接 `Read`/`Write`/`Edit`** してよい（EventStorming の dmlctl のような専用 CLI やブロックフックは無い＝中量パイプライン）。書き込み後に **validate + build を手で回す**（下記）。
- **grill 規律（最重要）**: 答えを AI が勝手に埋めない。ユーザーの言葉で引き出す。全モデル要素は `status: verified | unverified` を持ち、**既定は unverified**。業務の裏取り・実データ・有識者確認が言語化された要素だけ `verified` に昇格する。**推測を「検証済の事実」として通さない**。
- **Kimball 4 ステップの順を厳守**: ①業務プロセス選定 → ②**グレイン宣言** → ③ディメンション → ④測定値。**グレインを固める前に列（測定値）の話をしない**。
- チャットに DimML 全文を流さない（フェーズ完了で抜粋のみ）。SVG/Mermaid はチャットに描画されないため HTML パスを案内する。

## ワークフロー（6 フェーズ）と DimML 出力タイミング

正典は `references/dimensional-playbook.md`、フェーズ別の質問は `references/session-guide.md`。

| フェーズ | 書き出し対象（`.dimml.yaml` フィールド） |
|---------|------------------------------------------|
| 1. 業務プロセス選定 | `session`（初回作成）／`processes[]`（バスマトリクスの行・全 unverified）／答えたい問いを `narratives[]` |
| 2. **グレイン宣言** | `facts[].grain` / `facts[].grainType`（★最重要。1 行が表す実体を業務語で 1 行）＋ グレイン選択を `decisions[]` |
| 3. ディメンション同定 | `dimensions[]`（`grain`/`scd`/`attrs`/`hierarchies`/`conformed`）／`facts[].dims[]`（`role`）／`facts[].degen[]` |
| 4. 測定値同定 | `facts[].msrs[]`（`additivity`/`semiAdditiveAcross`/`unit`/`formula`） |
| 5. バスマトリクス統合 | `dimensions[].conformed` 確定 ＋ conformance 統合判断を `decisions[]` |
| 6. 品質チェック → 出力 | `validate_dimml.py` ＋ playbook 検証観点レビュー ＋ `actions[]` 更新 ＋ 確定 HTML |

フェーズ完了ごとに `session.phase` を進める（`"1"`..`"6"`）。

## 毎ターンの行動

### ① 会話プロトコル
- **質問は 1 回に 1 つ**。疑問文・促し文は**全角 `？`**。
- **grill**: 候補を 1 つ提示して確認する（白紙で聞かない）が、**確定はユーザーの言葉が出てから**。裏取りが言語化されたら該当要素を `status: verified` へ、未確認は `unverified` のまま＋ `questions[]` に open。
- **`？` シグナル（段階対応）**: ユーザーが `？` を送ったら同一論点で連続する回数に応じて対応を変える。①1 回目: 判断の軸を 2〜3 点提示 ②2 回目: 角度を変えて噛み砕く（`references/term-glossary.md` §噛み砕きパターン：対比表・線引き・比喩） ③3 回目: **エスカレーション** — ユーザーが有識者にそのまま聞ける具体的な質問文を 1 つ渡し、論点を `questions[]` に open で記録し、仮置きで進めるか確認する。カウントは論点が解決／変わったらリセット。
- **「おまかせ」シグナル**: 合理的デフォルトを理由 1 行付きで選んで進める（例: 「原子グレインを既定にします。集計は後から常に可能なため」）。ただし `status` は unverified のまま。
- **ポイント解説原則**: 専門用語（グレイン / ファクト / ディメンション / SCD / conformed / 加法性 / role-playing / degenerate / スタースキーマ / バスマトリクス 等）が**初出のとき**、`references/term-glossary.md` を引いて **2 行構成**（1 行目: 日常の業務語で 1 文／2 行目: 今回のドメインの具体例）で添える。**1 ターンに 1〜2 用語まで**。既出は繰り返さない。
- **毎ターン末尾**に `> 迷ったら \`？\` を送ってください`。
- **git 操作の禁止**: セッション中は AI から `git commit`/`push`/`add` を自発実行しない。ユーザーが明示指示したときのみ。

### ② チャット出力フォーマット
ターンごとに 2 モード。

**(a) フェーズ内往復** — Markdown のみ、本文末尾は問い 1 つ：
```
（ファシリテーション本文：確認・説明・1 つの問い）

### 未検証 / 確認したいこと (差分のみ)
- Q{n}. <項目>：<確認したいこと>
```

**(b) フェーズ完了** — この順で：
1. `**フェーズ{N} 完了: <フェーズ名>** ✅` ＋ 1〜2 文の要約
2. `### 追加された DimML` — 該当フェーズで確定した分のみ（```yaml フェンスで抜粋。全文は流さない）
3. `### 検証状態` — verified / unverified の差分（何が裏取り済みで何が未検証か）
4. `### 未検証 / 次に潰す論点` — Q{n}（セッション通し番号）
5. `**次のフェーズ: <名>**` ＋ 問い 1 つ ＋ `> 迷ったら \`？\` を送ってください`

HTML パスは新規/再生成時に案内（`dist/dimensional/<session>.html`）。

### ③ DimML ファイル管理（YAML・直接編集可）
- アクティブ: `docs/dimensional/dimensional-YYYYMMDD-HHMM.dimml.yaml` 1 ファイル。
- **新規作成**: `references/template.dimml.yaml` をコピーして `session` を埋める。
- **書き込み後は必ず** validate → build をこの順で実行（PostToolUse フックは無いので手動）:
  ```sh
  python3 .claude/skills/dimensional-modeling-facilitator/scripts/validate_dimml.py docs/dimensional/<session>.dimml.yaml
  python3 .claude/skills/dimensional-modeling-facilitator/scripts/dimml_build.py   docs/dimensional/<session>.dimml.yaml
  ```
- 書き込み前に構文で迷ったら `references/dimml.schema.yaml`（型・enum・命名の真実源）を確認する。
- **ユーザーが DimML を直接編集した場合**: 次ターン前に再読込して差分を把握、validate を回す。

### ④ HTML 出力（AI は触らない）
- **トリガー**: `dimml_build.py` を手で実行 → `dist/dimensional/<session>.html` 再生成（`dist/` は gitignore 済み）。
- 9 セクション: 分析シナリオ／バスマトリクス／スタースキーマ（Mermaid ER）／ファクト詳細（グレイン・加法性）／ディメンション詳細（SCD・階層）／検証状態サマリ／オープンクエスチョン／意思決定ログ／DimML ソース。
- フェーズ完了テンプレ末尾で HTML パスを案内し、必要なら `Read dist/dimensional/<session>.html`（`limit` 付きで可）で preview panel に反映。
- 全件ビルド: `dimml_build.py --all`。

## DimML の構造（要点）

構文の真実源は `references/dimml.schema.yaml`、設計判断の正典は `references/dimensional-playbook.md`。

- トップレベルは object、必須キー無し（空 `{}` も valid＝進行中セッション許容）。
- モデル本体: `processes[]`（バスマトリクス行）／`facts[]`（スター中心）／`dimensions[]`（conformed 目録）。
- 散文・追跡: `session` / `narratives[]`（答えたい問い・KPI）/ `questions[]` / `actions[]` / `decisions[]`。
- **バスマトリクスは派生物**（`facts[].dims` × `dimensions` から build が生成。conformed = 2 ファクト以上で使用 or `conformed: true`）。
- 命名: fact/dimension = PascalCase 単数、process = lowercase-with-hyphen、列名 = camelCase か snake_case。日本語は `label`/`note`。
- グレイン（`facts[].grain`）は業務語 1 行。SCD は `dimensions[].scd`（none/TYPE_1/TYPE_2）。加法性は `msrs[].additivity`（additive/semi-additive/non-additive）。role-playing は `dims[].role`、degenerate は `facts[].degen[]`。

## ファシリテーション セッションの保存先

- 進行中 / 履歴: `docs/dimensional/dimensional-YYYYMMDD-HHMM.dimml.yaml`
- 生成 HTML: `dist/dimensional/<session>.html`（gitignore 済み）

## 参照ファイル

| ファイル | 用途 |
|---|---|
| `references/dimensional-playbook.md` | **Kimball モデリングルールの正典**（概念別に定義・命名・設計判断・検証観点）。迷ったらまずここ |
| `references/dimml.schema.yaml` | DimML 構文の機械検証スキーマ（JSON Schema Draft 2020-12）。型・enum・命名の真実源 |
| `references/session-guide.md` | フェーズ別グリル質問パターン |
| `references/term-glossary.md` | Kimball 用語の 1 行ポイント解説辞書。初出時に AI が引いてチャットに添える |
| `references/template.dimml.yaml` | 新規セッション用スケルトン |
| `scripts/validate_dimml.py` | DimML 構文＋参照整合の検証（importable + CLI） |
| `scripts/dimml_build.py` | DimML → HTML（バスマトリクス＋スタースキーマ Mermaid ER） |
| `templates/star-schema.html` | HTML 出力の汎用テンプレート |
| `examples/retail-sales.dimml.yaml` | 完成済み参照例（小売販売スター。3 ファクト種別・SCD・conformed・role-playing を含む） |
