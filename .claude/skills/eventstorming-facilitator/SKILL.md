---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見し DML（Domain Modeling Language）に情報圧縮する。MD ファイルが Single Source of Truth。AI は MD のみ `Write`/`Edit` し、PostToolUse hook が `scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を自動再生成する（**AI は HTML を直接編集しない**）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code のチャット本文では SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください（半角 `?` でも可）。判断の軸を提示して一緒に考えます。

---

## ワークフロー（7フェーズ）

| フェーズ | 内容 |
|---------|------|
| 1. スコープ確認 | 対象ドメイン・ゴール・制約を3問で確認 |
| **2. ストーリー確認** | **ハッピーパス（400〜600字）＋代替シナリオ（2〜3本）を提示しユーザー確認。確認後に MD を `Write` → `Bash open <session>.html`** |
| 3. イベント発見 | `references/domain-starters.md` から候補提示。追加・削除を確認 |
| 4. CMD→EVT→POLICY チェーン | フロー全体を1本ずつ確認。AGG・BC 境界も同時に拾う |
| 4.5. BC 境界 | 文脈で意味が変わる言葉を `LANGUAGE` として記録 |
| **4.6. 目的・背景・制約** | **各 AGG の `#### 目的`（必須・30字以上）／`#### 背景`／`#### 制約` を 3 つの問いで言語化。RULE/ERR の前に意図を固める。BC レベルは任意。詳細: `references/session-guide.md`** |
| 5. RULE・ERR | 各 AGG の不変条件・エラーケースを掘る。`RULE` 直下 `WHY "..."`、`ERR` 直下 `WHEN "..."` 併記（推奨） |
| 6. 整合性チェック → 出力 | DML 整合性を確認し Markdown レポートを最終更新 |

MD 編集ごとに HTML は自動再生成されるが、**ブラウザの自動リロードはしない**（必要に応じて手動）。

---

## 毎ターンの行動

### ① 会話プロトコル

- **質問は1回に1つ**
- **疑問文・促し文は全角 `？`** — 半角 `?` は DML 記号（`?ReadModel`）や `[?]` マーカーなど機能的な用途のみ
- **EVT 拾い** — 「〜された」「〜完了した」を `EventName` で仮追加
- **`[?]` を残す** — 迷い・矛盾・未確認はすべてマーク。推測で埋めない
- **`？` シグナル** — ユーザーが `？` を送ったら判断の軸を2〜3点提示（押しつけない）
- **「おまかせ」シグナル** — 合理的なデフォルトを判断理由1行付きで選んで進める
- **毎ターン末尾** に `> 迷ったら \`？\` を送ってください`

### ② チャット出力フォーマット

ターンごとに2モードを使い分け。完全テンプレ: `references/chat-output-format.md`。

**(a) フェーズ内往復** — Markdown のみ：

```
（ファシリテーション本文：確認・説明・1つの問い）

### ホットスポット (差分のみ)
- H{n}. [?] <設計判断>：<なぜ迷うか>

### 未確認事項 (差分のみ)
- Q{n}. <項目>：<確認したいこと>
```

HTML 更新・DML 抜粋・用語集は出さない。本文末尾は問い 1 つで終わる。

**(b) フェーズ完了** — Markdown + 構造化テーブル + DML 抜粋 + 用語集差分 + HTML パス案内：

```
**フェーズ{N} 完了: <フェーズ名>** ✅

<1〜2文の要約>

### Event Flow (<図のタイトル>)

| レーン (BC) | 🟨 Actor | 🟦 Command | 🟪 Policy | 🟧 Event |
|---|---|---|---|---|
| **store-front** | 客 | 注文する | — | 注文が入った ⚡ |
| **kitchen** | — | 盛り付ける | 調理開始 | 料理ができた ⚡ |

⚡ = 次レーンへの非同期遷移

> 詳細描画: [<session>.html](dist/eventstorming/<session>.html)
>
> 📱 スマホアプリの場合は HTML をダウンロードしてブラウザで開く（Artifact 化希望は「Artifact 化」と送信）

### 追加された DML
```dml
<該当フェーズで確定した SCENARIO/POLICY/CONTEXT のみ>
```

### 用語集の追加
| 日本語 | 英語 | 種別 |
|---|---|---|

### ホットスポット
- H{n}. [?] <設計判断>：<理由>

### 未確認事項
- Q{n}. <項目>：<確認内容>

---
**次のフェーズ: <次フェーズ名>**

<最初の問い 1つ>

> 迷ったら `？` を送ってください
```

- H・Q 番号はセッション通じて通し（解決済みは欠番、再利用しない）
- 表内の付箋ラベルは **DSL 記号（`@!$[]`）を削除**。種別は表ヘッダーの絵文字＋カラム名で識別
- **DML 全文はチャットに流さない**。フェーズごとの抜粋粒度: `chat-output-format.md` §5
- 初回 DML 出力時に記法凡例を1回だけ添える（後述「DSL 記号」「DML キーワード」）

### ③ HTML 出力（AI は触らない）

- **トリガー**: MD を Write/Edit → PostToolUse hook → `dist/eventstorming/<session>.html` 再生成
- **出力先**: `dist/eventstorming/`（MD は `docs/`、HTML は `dist/`）
- **手動ビルド/全件/監視**: `python3 scripts/eventstorming_build.py <session>.md` / `--all` / `--watch`
- **フェーズ2完了時のみ** `Bash open dist/eventstorming/<session>.html`。自動リロードはしない
- **Claude Code preview panel への反映** — フェーズ完了テンプレ末尾で `Read dist/eventstorming/<session>.html` を必ず呼ぶ
- **スマホアプリ案内** — HTML 新規/再生成のフェーズ完了テンプレに「📱 HTML をダウンロードしてブラウザで」を必ず添える
- **描画仕様詳細**: `references/html-render-spec.md`、テンプレ: `templates/event-flow.html`

### ④ MD ファイル管理

- アクティブ: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md`（Single Source of Truth）
- フェーズ2で `Write`、以降は `Edit` で該当セクションのみ差分更新
- 書き出し後は **必ず** Agent tool で品質チェックを起動（`references/quality-check-agent.md`）。HTML は派生物なのでチェック不要
- **ユーザーが MD を直接編集した場合**: 次ターン応答前に `Read` で再読み込みし §3（フロー DSL）と §9（DML）を照合。差分があれば `Edit` で同期し品質チェック起動

| フロー DSL の変化 | DML への対応 |
|---|---|
| `@アクター > !コマンド > [イベント]` 追加 | 対応 SCENARIO 追加 |
| `?リードモデル名` 追加 | SCENARIO に `QRY QueryName` 追加 |
| `$ポリシー名` 追加 | 対応 POLICY 追加 |
| フロー項目削除 | SCENARIO/POLICY 削除（迷う場合 `[?]`） |
| レーン名（BC 名）変更 | CONTEXT 宣言と SCENARIO のモジュール名を更新 |

フロー図は日本語ラベル、DML は英語識別子（例：`!コミュニティを作成` ↔ `CMD CreateCommunity`）。新しい日本語ラベルが現れたら §10（用語集）に英語識別子を追記。

---

## Event Flow 記法（DSL）

ハッピーパスと各代替シナリオを `` ```event-flow-svg `` フェンスで MD §3 に保存（散文のみ不可）。

````markdown
```event-flow-svg
title: <タイトル>
flow:
|BC名|: <フロー起点の文脈説明>
  @アクター > ?リードモデル > !コマンド > [イベント]
  > !コマンド > [イベント] >>
|BC名|: <遷移の境界説明>
  $ポリシー > !コマンド > [イベント]
```
````

**改行ルール**: フロー行は `[イベント]` 直後で改行、次行は `  > ` で始める（インデント 2 スペース）。

**DSL 記号**: `|BC|:` レーンヘッダー（説明必須）／`@Actor`／`?ReadModel`（コマンド発行判断に必要な情報のみ）／`!Command`（`!` 省略可）／`[Event]`（過去形）／`$Policy`／`>` 同期連鎖／`>>` 非同期遷移（前レーン行末）／`*>` BULK Fork（N 個並列の 1 つ）／`&>>` Join+非同期遷移（N→1 合流の `>>` 版・前レーン行末）。色・HTML マッピング詳細: `references/html-render-spec.md` §6-3。

**ラベル日本語化方針**: コマンド=動詞句、イベント=過去形、ポリシー=目的名詞句、アクター=役割名、BC 名=英語。DML コードブロック（§9）は英語維持。HTML 表示時は DSL 記号（`@!$[]`）を削除。

---

## DML 記述ルール（要点）

完全仕様: `references/dml-spec.md`。

- **SCENARIO 名は日本語**でアクター＋行為（例：`SCENARIO 主催者がコミュニティを作成する`）。先頭に `ACTOR <名前>` 必須（典型値: `Organizer` `Member` `System`）
- **SCENARIO 内フィールド順序 `ACTOR → QRY → CMD → EVT → AGG → RULE → ERR → POL`** 厳守
- **`EVT/CMD/AGG/QRY` は英語識別子**（`EVT OrderPlaced` 等。`()` や `<<>>` 不要）。RULE/ERR/POLICY の日本語補足は上行に `#` コメント
- **CONTEXT 宣言に `UPSTREAM`/`DOWNSTREAM` 必須**（依存なしは `(none)` 明示、関係タイプを行末コメント）。BC 名は `lowercase-with-hyphen`
- **POLICY ブロックは EVENTUAL-TX 専用** — 対応 SCENARIO 直後・CONTEXT 内に配置。SAME-TX 分岐は発行元 SCENARIO の `WHEN` インライン
- **ポリシー後の Command は原則必須**（`$Policy > !Command > [Event]`）。**例外**: 副作用専用 POLICY（外部通知/メール送信など AGG 更新を伴わない）は `$Policy > [Event]` 許容、対応 SCENARIO 省略、POLICY ブロックの `CMD` も省略（TRIGGER/QRY/BULK/EVT のみ）
- **QRY は判断材料のみ** — アクターまたはポリシーの判断（どのコマンドを誰に発行するか）に必要なデータ。コマンド実装内部のデータ（BULK の対象リスト等）は含めない
- **インフラ系ドメイン（通知・スケジューラ・決済等）は「BC 昇格 vs POLICY 留置」を判定** — データモデルがあるのに CONTEXT がない「宙吊り」禁止

---

## MD 出力タイミング

| タイミング | 操作 |
|-----------|------|
| フェーズ2完了 | `Write` 新規作成 → `Bash open <session>.html` 初回起動 |
| フェーズ3完了 | `Edit` で §3・§9・§10 |
| フェーズ4完了 | `Edit` で §3・§4・§9・§10 |
| フェーズ4.5完了 | `Edit` で §4（LANGUAGE）・§9 |
| **フェーズ4.6完了** | **`Edit` で §4（BC `#### 目的/背景/制約` 任意）・§5（AGG `#### 目的`必須/`#### 背景`/`#### 制約`）** |
| フェーズ5完了 | `Edit` で §5（Zod・RULE/ERR）・§6・§9（`WHY`/`WHEN` 併記） |
| フェーズ6（最終） | `Edit` で全セクション完成版 |
| ユーザーが「保存して」 | 即座に MD を書き出す |

**書き出し後の品質チェック（必須）**: Agent tool で `references/quality-check-agent.md` を起動。
- **表記チェック (D/F/S 系)**: 形式違反は自動修正
- **モデリング意味チェック (M 系)**: CMD/EVT 命名・CRUD 検出・Saga 完了状態など、命名と業務概念の整合。意味判断のため自動修正せず `[?] M_N` ホットスポット候補として列挙し、ユーザーと協議

**途中保存と再開**: MD に `## 再開ポイント` セクションを追加。再開時は読み込んで継続、H・Q 番号は引き継ぐ。

### MD セクション構成

完全テンプレ（見出しレベル・サブセクション形式）: `references/template.md`。

| # | セクション | タイミング |
|---|-----------|-----------|
| 1 | ハッピーパスストーリー（400〜600字） | フェーズ2 |
| 2 | 代替シナリオ（散文のみ、図は §3） | フェーズ2 |
| 3 | Event Walkthrough（`` ```event-flow-svg `` 図） | フェーズ2〜 |
| 4 | コンテキスト候補（`### english-slug（日本語名）`、`UPSTREAM`/`DOWNSTREAM` 必須、任意で `#### 目的/背景/制約`） | フェーズ4〜（4.6 で背景） |
| 5 | 集約候補（`### EnglishName（日本語名）`、`#### 目的`（必須・30字以上）/`#### 背景`/`#### 制約`、Zod スキーマ・不変条件・状態遷移） | 4.6 で目的系、5 で Zod |
| 6 | リードモデル候補（`### QRYName（日本語名）`） | フェーズ4〜5 |
| 7 | オープンクエスチョン | 随時 |
| 8 | 次のアクション | 随時 |
| 9 | DML（` ```dml ` 全文） | 随時 |
| 10 | 用語集（日本語ラベル ↔ 英語 DML 識別子） | フェーズ3〜 |

**§6 リードモデル候補**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む / (b) 複数集約・複数 BC を横断 / (c) BULK クエリ（一覧取得）のいずれかのみ記載。各エントリは `利用者`／`目的`／`ソース`／`算出` を1行ずつ。

未完成セクションは `<!-- TODO: フェーズN完了後に追記 -->` で保持（HTML 側 `.todo-placeholder` 表示）。

---

## サブコマンド

| キーワード例 | 参照 |
|---|---|
| 「フロー整合性チェック」「因果チェーンチェック」「causal check」 | `references/causal-check-agent.md` |
| 「表記チェック」「品質チェック」「quality check」 | `references/quality-check-agent.md` |

サブエージェントの結果は1行でユーザー報告。

---

## Artifact 化（スマホで HTML を閲覧）

ユーザーが「Artifact 化」「スマホで見たい」と言ったら：

1. `python3 scripts/eventstorming_build.py docs/eventstorming/<session>.md --artifact --copy`
   - `--artifact`: meta-refresh 等を除去した `<session>-artifact.html` を出力
   - `--copy`: 内容を `pbcopy` でクリップボードへ（macOS 限定）
2. claude.ai の **新しいチャット** に貼り付け「**これを Artifact として表示して**」と依頼
3. 1行報告: `📋 <session>-artifact.html を生成 / クリップボードへコピー済み。claude.ai で Artifact 化してください`

制約: 単一 HTML のみ／自動更新なし（再ビルド後は再貼り付け）／`--copy` は macOS 限定。

---

## 参照ファイル

| ファイル | 用途 |
|---|---|
| `references/dml-spec.md` | DML 完全仕様（SCENARIO・POLICY・QRY・DSL 記号・記述ルール・フル例） |
| `references/session-guide.md` | ファシリテーション質問パターン |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.md` | MD レポート完全テンプレート（§1〜§10 詳細） |
| `references/quality-check.md` | 品質チェックルール（D/F/S/M 系） |
| `references/causal-check.md` | DML 因果チェーンチェックルール |
| `references/quality-check-agent.md` | 品質チェック起動プロンプト |
| `references/causal-check-agent.md` | フロー整合性起動プロンプト |
| `references/html-render-spec.md` | HTML レンダリング仕様（色・DSL→HTML 変換） |
| `references/chat-output-format.md` | チャット出力テンプレート完全版 |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
