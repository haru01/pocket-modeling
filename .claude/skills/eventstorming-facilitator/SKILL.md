---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見しながら DML（Domain Modeling Language）として情報圧縮する。MD ファイルが Single Source of Truth。AI は MD のみ `Write` / `Edit` し、PostToolUse hook が `.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を自動再生成する（**AI は HTML を直接編集しない**）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code の CLI/PC/スマホアプリではチャット本文の SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください。判断の軸を提示して一緒に考えます（半角 `?` でも可、全角 `？` 推奨）。

---

## ワークフロー（7フェーズ）

| フェーズ | 内容 |
|---------|------|
| 1. スコープ確認 | 対象ドメイン・ゴール・制約を3問で確認 |
| **2. ストーリー確認** | **ハッピーパスストーリー（400〜600字）＋代替シナリオ（2〜3本）を提示してユーザー確認。確認後に MD/HTML を生成し、`Bash open` で HTML をブラウザ表示** |
| 3. イベント発見 | `references/domain-starters.md` から候補提示。追加・削除を確認して合意 |
| 4. CMD→EVT→POLICY チェーン | フロー全体のつながりを1本ずつ確認。AGG・BC 境界も同時に拾う |
| 4.5. BC 境界 | 同じ言葉が文脈で意味が変わるサインを `LANGUAGE` として記録 |
| **4.6. 目的・背景・制約** | **各 AGG の `#### 目的`（必須・30字以上）／`#### 背景` ／`#### 制約` を 3 つの問いで言語化。RULE/ERR を引き出す前に意図を固める。BC レベルは任意。詳細は `references/session-guide.md` §「80〜85分」** |
| 5. RULE・ERR | 各 AGG の不変条件・エラーケースを掘る。`RULE` 直下に `WHY "..."`、`ERR` 直下に `WHEN "..."` を併記（推奨） |
| 6. 整合性チェック → 出力 | DML 整合性を確認してから Markdown レポートを最終更新 |

フェーズ2完了直後に MD ファイル `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md` を `Write` で生成（hook が HTML を自動生成）。初回のみ `Bash open dist/eventstorming/<session>.html` でブラウザ表示。以降の MD 編集で HTML は再生成されるが、**ブラウザの自動リロードは行わない**（必要に応じて手動で再読み込み）。

---

## 毎ターンの行動

### ① 会話プロトコル

- **質問は1回に1つ** — 複数投げると思考が拡散する
- **疑問文・促し文は全角 `？`** — 半角 `?` は DML 記号（`?ReadModel`）や `[?]` マーカーなど機能的な記号としてのみ残す
- **EVT 拾い** — 「〜された」「〜完了した」を `EventName` で拾い DML に仮追加
- **`[?]` を残す** — 迷い・矛盾・未確認はすべてマーク。推測で埋めない（マーカーは半角 `?` 固定）
- **`？` シグナル** — ユーザーが `？`（半角 `?` 含む）を送ったら判断の軸を2〜3点提示（答えを押しつけない）
- **「おまかせ」シグナル** — 合理的なデフォルトを判断理由1行付きで選んで進める
- **毎ターン末尾** に `> 迷ったら \`？\` を送ってください` を添える

### ② チャット出力フォーマット

ターンごとに2モードを使い分ける。詳細は `references/chat-output-format.md`。

**(a) フェーズ内往復** — Markdown のみ：

```
（ファシリテーション本文：確認・説明・1つの問い）

### ホットスポット (差分のみ)
- H{n}. [?] <設計判断>：<なぜ迷うか>

### 未確認事項 (差分のみ)
- Q{n}. <項目>：<確認したいこと>
```

HTML 更新・DML 抜粋・用語集は出さない。本文末尾は問い 1 つで終わる。

**(b) フェーズ完了** — Markdown + 構造化テーブル + DML 抜粋 + 用語集差分 + HTMLパス案内：

```
**フェーズ{N} 完了: <フェーズ名>** ✅

<1〜2文の要約>

### Event Flow (<図のタイトル>)

| レーン (BC) | 🟨 Actor | 🟦 Command | 🟪 Policy | 🟧 Event |
|---|---|---|---|---|
| **store-front** | 客 | 注文する | — | 注文が入った ⚡ |
| **kitchen** | — | 盛り付ける | 調理開始 | 料理ができた ⚡ |
| **store-front** | 客 | 会計する | — | 会計が完了した |

⚡ = 次レーンへの非同期遷移

> 詳細描画: [eventstorming-YYYYMMDD-HHMM.html](dist/eventstorming/eventstorming-YYYYMMDD-HHMM.html) （ブラウザで自動更新）
>
> 📱 スマホアプリでご覧の場合は HTML ファイルをダウンロードしてブラウザで開いてください（claude.ai 上で Artifact 化したい場合は「Artifact 化」と送ってください）

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
- DML 抜粋の粒度はフェーズごと（`chat-output-format.md` §5）。**DML 全文はチャットに流さない**
- 初回 DML 出力時に記法凡例を1回だけ添える（DML: `CONTEXT` `LANGUAGE` `UPSTREAM` `DOWNSTREAM` `EVT` `CMD` `AGG` `QRY` `POLICY` `TRIGGER` `WHEN` / フロー図: `|BC|` `@Actor` `?ReadModel` `!Command` `[Event]` `$Policy` `>` `>>` `*>`（BULK fanout） `&>>`（Join 遷移））
- 表内の付箋ラベルは **DSL 記号（`@!$[]`）を削除して書く**。種別は表ヘッダーの絵文字＋カラム名で識別
- `POLICY` ブロックは EVENTUAL-TX 専用。SAME-TX の分岐は発行元 SCENARIO の `WHEN` としてインライン記述（`references/dml-spec.md` 参照）

### ③ HTML 出力ルール（AI は触らない）

HTML は `scripts/eventstorming_build.py` が MD から自動生成する派生物。AI は HTML を Write/Edit しない。

- **トリガー**: `docs/eventstorming/*.md` を Write/Edit すると PostToolUse hook が起動 → `dist/eventstorming/<session>.html` を再生成
- **出力先**: `dist/eventstorming/`（MD は `docs/`、HTML は `dist/` で責務分離）
- **描画内容**: CSS 付箋風 div + Big Picture グリッド（時系列=横、BC=縦）、Zod スキーマシンタックスハイライト、コンテキストマップ自動生成、進捗バー
- **付箋ラベル**: DSL 記号（`@!$[]`）は HTML 表示時に自動削除
- **手動ビルド / 全件 / 監視**: `python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <session>.md` / `--all` / `--watch`
- **Artifact 化（スマホ閲覧）**: `--artifact --copy` で `<session>-artifact.html` を生成しクリップボードへコピー。詳細は「Artifact 化」セクション
- **テンプレート**: `templates/event-flow.html`、詳細仕様: `references/html-render-spec.md`
- **フェーズ2完了時のみ** `Bash open dist/eventstorming/<session>.html` で外部ブラウザを起動。自動リロードはしない（meta refresh / AppleScript リロードは撤去済み）
- **Claude Code preview panel への反映** — フェーズ完了テンプレ末尾で `Read dist/eventstorming/<session>.html` を必ず呼ぶ
- **スマホアプリ版への案内** — HTML を新規/再生成したフェーズ完了時、テンプレに「📱 スマホアプリでご覧の場合は HTML ファイルをダウンロードしてブラウザで開いてください」を必ず添える。Artifact 化希望は後述セクションへ誘導

### ④ MD ファイル管理

- アクティブファイル: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md`（DML/フロー DSL の Single Source of Truth）
- HTML ファイル: `dist/eventstorming/eventstorming-YYYYMMDD-HHMM.html`（MD から派生）
- フェーズ2完了で `Write`（新規作成）、以降のフェーズ完了ごとに `Edit`（該当セクションのみ差分更新）
- 書き出し後は **必ず** 品質チェックサブエージェントを起動（`references/quality-check-agent.md`。HTML は派生物なのでチェック不要）
- **ユーザーが MD ファイルを直接編集した場合**: 次ターン応答前に `Read` で再読み込みし §3（フロー DSL）と §9（DML）を照合。差分があれば DML を `Edit` で同期し、品質チェック起動

| フロー DSL の変化 | DML への対応 |
|---|---|
| `@アクター > !コマンド > [イベント]` 追加 | 対応 SCENARIO を追加 |
| `?リードモデル名` 追加 | 対応 SCENARIO に `QRY QueryName` を追加 |
| `$ポリシー名` 追加 | 対応 POLICY を追加 |
| フロー項目削除 | SCENARIO/POLICY を削除（迷う場合は `[?]` でマーク） |
| レーン名（BC 名）変更 | CONTEXT 宣言と SCENARIO のモジュール名を更新 |

フロー図は日本語ラベル、DML は英語識別子（例：`!コミュニティを作成` ↔ `CMD CreateCommunity`）。新しい日本語ラベルが現れたらセクション10（用語集）にも対応英語識別子を追記。

---

## Event Flow 記法（DSL — Single Source of Truth）

ハッピーパスと各代替シナリオをそれぞれ `` ```event-flow-svg `` フェンスで MD ファイル §3 に保存（散文のみは不可）。フェンス名が `svg` でも内容は中立 DSL で HTML レンダラーが解釈。

````markdown
```event-flow-svg
title: <タイトル>
flow:
|BC名|: <フロー起点の文脈説明（アクター・起動条件など）>
  @アクター > ?リードモデル > !コマンド > [イベント]
  > !コマンド > [イベント] >>
|BC名|: <遷移の境界説明（何をきっかけに次のレーンへ移るか）>
  $ポリシー > !コマンド > [イベント]
```
````

**改行ルール**: フロー行は `[イベント]` 直後で改行し、次行は `  > ` で始める（インデント 2 スペース）。

| 記号 | 意味 | 付箋色 | HTML での扱い |
|------|------|--------|----|
| `\|BC名\|: 説明` | レーン（swim lane）ヘッダー行。説明必須 | グレートーン | `.lane-name.bc-{slug}` |
| `@アクター名` | アクター付箋 | 黄 | `.note.actor` |
| `?クエリ名` | Read Model 付箋。「これを見なければコマンドを発行できない」情報のみ | 緑 | `.note.readmodel` |
| `!コマンド名` | コマンド付箋（`!` 省略可） | 青 | `.note.command` |
| `[イベント名]` | イベント付箋（過去形） | 橙 | `.note.event` |
| `$ポリシー名` | ポリシー付箋 | 紫 | `.note.policy` |
| `>` | 同期フロー（直接連鎖） | — | `.arrow-h` |
| `>>` | 非同期遷移（レーン切り替え）— 前レーン最後の行末 | — | `.arrow-v down/up` |
| `*>` | **BULK Fork**。直後の CMD/EVT が N 個並列インスタンスのうちの 1 つ | — | `.note.fanout` (3 枚スタック + ×N) / `.arrow-h.fork` |
| `&>>` | **Join + 非同期遷移**。N→1 合流の `>>` 版 — 前レーン最後の行末 | — | `.sync-bar down/up` (BPMN 黒太線 + Σ N) |

**ラベルの日本語化方針：** コマンド=動詞句、イベント=過去形、ポリシー=目的名詞句、アクター=役割名、BC 名=英語のまま。DML コードブロック（§9）は英語維持。HTML 表示時は DSL 記号（`@!$[]`）を削除。

---

## DML 記述ルール

- **SCENARIO 名は日本語**でアクター＋行為（例：`SCENARIO 主催者がコミュニティを作成する`）
- **SCENARIO 内フィールド順序は `ACTOR → QRY → CMD → EVT → AGG → RULE → ERR → POL`** を厳守
- **ACTOR は必須**。SCENARIO 先頭に `ACTOR <アクター名>`（典型値：`Organizer` `Member` `System`）
- **CONTEXT 宣言に `UPSTREAM` / `DOWNSTREAM` を必須記載**（依存なしは `(none)` 明示、関係タイプを行末コメント）
- **POLICY ブロックは EVENTUAL-TX 専用** — SAME-TX の分岐は発行元 SCENARIO の `WHEN` インライン記述
- **POLICY は対応 SCENARIO 直後・CONTEXT 内に配置** — ファイル末尾にまとめない。`SCENARIO` 内の `POL` はポリシー名参照、`POLICY` ブロックが定義
- **RULE / ERR / POLICY の日本語補足は上行に `#` コメントで分離**
- **ポリシー後の Command は原則必須** — `$Policy > !Command > [Event]`。**例外:** 副作用専用 POLICY（外部通知/メール送信 等、AGG 更新を伴わない infrastructure 呼び出し）に限り `$Policy > [Event]` を許容（対応 SCENARIO を書かず、POLICY ブロックの `CMD` フィールドも省略。TRIGGER / QRY / BULK / EVT のみ）。例: `$会場変更時の通知 *> [変更が通知された]`
- **EVT / CMD / AGG / QRY は英語のみ**（`EVT OrderPlaced`、`AGG Order`、`QRY GetEventDetails` — `()` や `<<>>` は不要）
- **QRY は判断に必要なデータのみ** — アクター（「このコマンドを発行するか」）またはポリシー（「どのコマンドを発行するか・誰に対して」）の判断材料のみ。コマンド実装内部で必要なデータ（BULK の実行対象リスト等）はコマンドの責務（詳細は `references/dml-spec.md`）
- **BC（CONTEXT）名は `lowercase-with-hyphen`** で略さず
- **インフラ系ドメイン（通知・スケジューラ・決済等）は「BC 昇格 vs POLICY 留置」を判定** — データモデルがあるのに CONTEXT 宣言がない「宙吊り」状態を禁止（判定基準は `references/dml-spec.md`）

---

## MD 出力タイミング

| タイミング | 操作 |
|-----------|------|
| フェーズ2完了 | MD を `Write` 新規作成 → `Bash open <file>.html` で初回起動 |
| フェーズ3完了 | `Edit` で §3（フロー DSL）・§9（DML）・§10（用語集）更新 |
| フェーズ4完了 | `Edit` で §3・§4（コンテキスト）・§9・§10 更新 |
| フェーズ4.5完了 | `Edit` で §4（コンテキスト名・LANGUAGE）と §9 更新 |
| **フェーズ4.6完了** | **`Edit` で §4（BC カードの `#### 目的/背景/制約` 任意）と §5（AGG カードの `#### 目的`（必須）/`#### 背景`/`#### 制約`）更新** |
| フェーズ5完了 | `Edit` で §5（集約・Zod スキーマ・RULE/ERR）・§6（リードモデル）・§9（RULE 直下 `WHY` / ERR 直下 `WHEN` 併記）更新 |
| フェーズ6（最終） | `Edit` で全セクション完成版を保存 |
| ユーザーが「保存して」 | 即座に MD を書き出す |

**書き出し後の品質チェック（必須）：** MD を Write/Edit したら **必ず** Agent tool で品質チェックサブエージェントを起動（`references/quality-check-agent.md`）。HTML は派生物なのでチェック不要。

品質チェックは 2 段階:
- **表記チェック (D / F / S 系)**: 形式違反は自動修正
- **モデリング意味チェック (M 系)**: CMD/EVT 名の業務概念整合性・CRUD 命名検出・Saga 完了状態など、命名と業務概念の整合をチェック。意味判断を伴うため自動修正せず、`[?] M_N` ホットスポット候補として列挙。ユーザーと協議して採否決定。

**途中保存と再開：** `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md` に `## 再開ポイント` セクションを付けて保存。再開時は読み込んで継続、H・Q 番号は前回から引き継ぐ。

### MD ファイル出力形式

- 見出し1: `# EventStorming 風味のドメインモデリング - <ドメイン名>`

| # | セクション | 記載タイミング |
|---|-----------|--------------|
| 1 | ハッピーパスストーリー（400〜600字） | フェーズ2 |
| 2 | 代替シナリオ（散文のみ、図はセクション3に集約） | フェーズ2 |
| 3 | Event Walkthrough（`` ```event-flow-svg `` 図） | フェーズ2以降 |
| 4 | コンテキスト候補（**`### english-slug（日本語名）` 形式必須**、`UPSTREAM`/`DOWNSTREAM` 依存方向必須、任意で `#### 目的`/`#### 背景`/`#### 制約` サブセクション） | フェーズ4完了後（背景系はフェーズ4.6） |
| 5 | 集約候補（**`### EnglishName（日本語名）` 形式必須**、`#### 目的`（必須・30字以上）/`#### 背景`/`#### 制約` サブセクション、属性を Zod スキーマで記述・不変条件・状態遷移必須） | `#### 目的/背景/制約` はフェーズ4.6完了後、Zod・不変条件はフェーズ5完了後 |
| 6 | リードモデル候補（**`### QRYName（日本語名）` 形式必須**） | フェーズ4〜5完了後 |
| 7 | オープンクエスチョン | 随時 |
| 8 | 次のアクション | 随時 |
| 9 | DML（` ```dml ` コードブロック全文） | 随時 |
| 10 | 用語集（日本語フロー図ラベル ↔ 英語 DML 識別子の対応表） | フェーズ3以降・随時 |

**セクション6 リードモデル候補の書き方：**

フロー図（§3）と DML の `QRY` から収集。ただし**単一集約への単純ルックアップは省略**し、以下のいずれかに該当するもののみ記載：

- 計算値を含む（例：定員 − 承認数 = 残席数）
- 複数集約・複数 BC を横断する
- BULK クエリ（一覧取得）

各エントリの形式：

```markdown
### QRY名（日本語名）
- **利用者**: アクター名 または ポリシー名（対応 SCENARIO/POLICY への参照）
- **目的**: 何を確認して何を決めるか（1行）
- **ソース**: どの集約・BC からデータを取るか
- **算出**: 計算式・取得条件・ソート順など（単純ルックアップなら省略可）
```

未完成セクションは `<!-- TODO: フェーズN完了後に追記 -->` プレースホルダーで保持（HTML 側では `.todo-placeholder` クラスで表示）。

---

## サブコマンド

| キーワード例 | 参照ファイル |
|------------|------|
| 「フロー整合性チェック」「因果チェーンチェック」「整合性チェック」「causal check」 | `references/causal-check-agent.md` |
| 「表記チェック」「品質チェック」「quality check」 | `references/quality-check-agent.md` |

サブエージェントの結果を受け取ったら、内容をユーザーに1行で報告する。

---

## Artifact 化（スマホで HTML を閲覧する）

`dist/eventstorming/<session>.html` はローカルファイルなのでそのままではスマホから見られない。**claude.ai の Artifact 機能**でスマホ（Web/アプリ）から確認可能。

ユーザーが「Artifact 化」「スマホで見たい」と言ったら：

1. **Artifact 互換 HTML を生成**:
   ```bash
   python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py \
       docs/eventstorming/<session>.md --artifact --copy
   ```
   - `--artifact`: meta-refresh / リロード案内を除去した `<session>-artifact.html` を出力
   - `--copy`: 生成内容を `pbcopy` でクリップボードへ（macOS 限定）
2. **貼り付け先案内**: claude.ai の **新しいチャット** を開き、クリップボードの HTML を貼り付け「**これを Artifact として表示して**」と依頼
3. **チャットに 1 行報告**: `📋 dist/eventstorming/<session>-artifact.html を生成 / クリップボードへコピー済み。claude.ai に貼り付けて Artifact 化してください`

制約：単一 HTML のみ（外部 CSS/JS/画像なし） / 自動更新は機能しない（再ビルド後は再貼り付け必要） / `--copy` は macOS 限定（Linux/Windows は手動で `pbpaste`/ファイル参照）。

| 用途 | パス |
|---|---|
| ローカルブラウザ閲覧（手動リロード） | `dist/eventstorming/<session>.html` |
| Artifact 用（claude.ai 貼り付け用） | `dist/eventstorming/<session>-artifact.html` |

---

## 参照ファイル

| ファイル | 用途 |
|---------|------|
| `references/dml-spec.md` | DML 記法仕様（SCENARIO・POLICY・QRY 完全仕様） |
| `references/session-guide.md` | ファシリテーション質問パターン |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.md` | Markdown レポートテンプレート |
| `references/quality-check.md` | DDD/EventStorming 品質チェックルール（D1〜D10 表記 / F1〜F6 フロー記法 / S1〜S7 セクション完全性 / M1〜M5 モデリング意味） |
| `references/causal-check.md` | DML 因果チェーンチェックルール |
| `references/quality-check-agent.md` | 品質チェックサブエージェント起動プロンプト |
| `references/causal-check-agent.md` | フロー整合性サブエージェント起動プロンプト |
| `references/html-render-spec.md` | Event Flow HTML レンダリング仕様（CSS 付箋風 div + Big Picture グリッド、DSL→HTML 変換ルール） |
| `references/chat-output-format.md` | チャット出力テンプレート（フェーズ完了／往復モード、編集指示語彙、フォールバックモード） |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
