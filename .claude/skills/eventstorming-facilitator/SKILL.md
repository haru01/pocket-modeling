---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見し DML（Domain Modeling Language）に情報圧縮する。**`docs/eventstorming/<session>.dml.yaml` 1 ファイルがモデル唯一の真実源**（v5 以降）。物語（`story`）・代替シナリオ（`narratives`）・次のアクション（`actions`）・オープンクエスチョン（`questions`）・BC 散文（`ctxs[].description`）・リードモデル（`qrys`）・意思決定ログ（`decisions`）・集約カード（`aggs`）・フロー（`flows`）・コンテキスト言語（`ctxs[].lang`）・依存方向（`ctxs[].up/dn`）はすべて DML 内のトップレベル項目として保持される。`.md` は廃止された。

AI は **`scripts/dmlctl.py` 経由で観点別スライスだけ読み書き** する（全文 `Read`/`Edit` は避ける）。`dmlctl view --view=<name>` で必要な観点だけを取得、`dmlctl set/add/remove` で構造化された編集を行う。直接 `Edit` で書き換えるのも可能だが、テキストサイズが大きいと context を圧迫するため小さな変更でも dmlctl を優先する。

PostToolUse hook が `scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を再生成する（**AI は HTML を直接編集しない**）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code のチャット本文では SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください（半角 `?` でも可）。判断の軸を提示して一緒に考えます。

---

## ワークフロー（8フェーズ）

各フェーズの「書き出し対象」は **`.dml.yaml` のトップレベルフィールド**。AI は dmlctl 経由
（`set` / `add` / `remove`）で更新する。直接 Edit も可だが context 節約のため dmlctl 優先。

| フェーズ | 書き出し対象（`.dml.yaml` フィールド） |
|---------|--------------------------------------|
| 1. スコープ確認 | `session`（id/domain/goal/status） |
| **2. ストーリー確認** | **`story`（ハッピーパス散文）＋ `narratives[]`（代替シナリオ散文 2〜3 本）＋ `flows[]` の枠** → `Bash open <session>.html` |
| 3. イベント発見 | `scs[]` 仮 entries ＋ `ctxs[].lang` 新規識別子 |
| 4. CMD→EVT→POLICY チェーン | `scs[]` / `pols[]` / `flows[]`（happy + 代替 1〜2）／ `ctxs[]` の `up`/`dn` |
| 4.5. BC 境界 | `ctxs[].lang` 充実（文脈で意味が変わる言葉を記録） |
| **4.6. 目的・背景・制約** | **`aggs[]` の `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states` ＋ `ctxs[].description`（BC 散文）** |
| **5. 不変条件・エラー＋属性・イベントペイロード** | **`scs[].rules[]`（rule/why）／`scs[].errs[]`（cond/err/when）／`aggs[].transitions[]`／`aggs[].attrs[]`／`aggs[].events[].params[]` ＋ `qrys[]`（リードモデル候補）** |
| **6. 意思決定ログ** | **`decisions[]`**（id/topic/chosen/options/affects・options ごとに why/why_not） |
| 7. 整合性チェック → 出力 | `dmlctl check` を全観点実行 → 観点別 LLM 評価 → 確定版 `.dml.yaml` |

`.dml.yaml` の編集ごとに HTML は自動再生成されるが、**ブラウザの自動リロードはしない**（必要に応じて手動）。

---

## 毎ターンの行動

### ① 会話プロトコル

- **質問は1回に1つ**
- **疑問文・促し文は全角 `？`** — 半角 `?` は DML 記号や `[?]` マーカーなど機能的な用途のみ
- **EVT 拾い** — 「〜された」「〜完了した」を `EventName` で仮追加
- **`[?]` を残す** — 迷い・矛盾・未確認はすべてマーク。推測で埋めない。選択肢が見えてきたら `decisions[]` に昇格
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

HTML 更新・DML 抜粋は出さない。本文末尾は問い 1 つで終わる。

**(b) フェーズ完了** — Markdown + 構造化テーブル + DML 抜粋（`ctxs[].lang` の追加識別子も含む）+ HTML パス案内：

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

### 追加された DML
```dml
<該当フェーズで確定した ctxs/aggs/scs/pols/flows/decisions のみ（YAML）>
```

### 新規ラベルの追加（DML `ctxs[].lang`）
| 英語識別子 | 日本語ラベル | 所属 BC | 種別 |
|---|---|---|---|

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
- 表内の付箋ラベルは付箋種別を絵文字＋カラム名で識別（特殊記号は使わない）
- **DML 全文はチャットに流さない**。フェーズごとの抜粋粒度: `chat-output-format.md` §5

### ③ HTML 出力（AI は触らない）

- **トリガー**: `.dml.yaml` を Write/Edit（dmlctl 経由 or 直接）→ PostToolUse hook → `dist/eventstorming/<session>.html` 再生成
- **出力先**: `dist/eventstorming/`（`.dml.yaml` は `docs/`、HTML は `dist/`）
- **手動ビルド/全件/監視**: `python3 scripts/eventstorming_build.py <session>.dml.yaml` ／ `--all` ／ `--watch`
- **フェーズ2完了時のみ** `Bash open dist/eventstorming/<session>.html`。自動リロードはしない
- **Claude Code preview panel への反映** — フェーズ完了テンプレ末尾で `Read dist/eventstorming/<session>.html` を必ず呼ぶ
- **スマホアプリ案内** — HTML 新規/再生成のフェーズ完了テンプレに「📱 HTML をダウンロードしてブラウザで」を必ず添える
- **描画仕様詳細**: `references/html-render-spec.md`、テンプレ: `templates/event-flow.html`

### ④ DML ファイル管理（YAML-only）

- アクティブ: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.dml.yaml` 1 ファイル
- **基本操作は `dmlctl` 経由**：
  - 読み取り：`python3 scripts/dmlctl.py view <file> --view=<name>`（全文 Read を回避）
  - 書き込み：`python3 scripts/dmlctl.py set/add/remove <file> --path=... --value=...`
  - 観点一覧：`dmlctl views` / `dmlctl checks`
- 直接 `Edit` も可だがテキストサイズが大きいときは dmlctl 優先（context 節約のため）
- フェーズ 2 で `.dml.yaml` を `Write` 新規作成（テンプレ: `references/template.dml.yaml`）
- 書き出し後は **必ず** Agent tool で品質チェックを起動（`references/quality-check-agent.md`）。HTML は派生物なのでチェック不要
- **ユーザーが DML を直接編集した場合**: 次ターン応答前に `dmlctl view` で観点別に再読み込みし変更を把握、必要なら品質チェックを起動

---

## Event Flow（DML 駆動）

§3 のフロー図は **`.dml.yaml` の `flows[]` ＋ `scs[]`/`pols[]` からビルダーが自動生成**する。AI/人間が手書きの DSL を書く場面は無い。

`flows[]` の各エントリは：

```yaml
flows:
  - id: happy
    title: ハッピーパス — 注文確定から発送まで
    kind: happy
    steps:
      - 主催者がコミュニティを作成する          # scs[].name（日本語）
      - 参加者がイベントに参加申込する          # scs[].name（日本語）
      - RequestPayment                          # pols[].name（PascalCase）
      - システムが申込を確定し監査記録する
  - id: alt-waitlist
    title: 代替シナリオ — 残席ゼロで繰上待ち
    kind: alt
    steps:
      - 参加者がイベントに参加申込する
      - NotifyWaitlistPromotion
```

- **`steps[]` の値は `scs[].name`（日本語）または `pols[].name`（PascalCase）の混在**。順序は因果連鎖と整合させる
- 同一 `ctx` の連続ステップはビルダー側で **1 レーンに併合**され、`ctx` 変化やポリシー遷移は非同期矢印で描画
- POLICY が `trgs`（複数トリガー join）を持てば **BPMN シンクバー（Σ N）** で表現、`bulk: true` であれば **fanout（× N）** で描画
- 図の HTML 表現詳細は `references/html-render-spec.md` §5

---

## DML 記述ルール（要点）

DML は **`docs/eventstorming/<session>.dml.yaml`** 1 ファイルに **YAML 直書き**（フェンス不要）で書く。構文は `references/dml.schema.yaml`（JSON Schema）で機械検証。設計判断・哲学は `references/dml-spec.md`。

- **トップレベル**（v5）: モデル本体 `ctxs` / `aggs` / `scs` / `pols` / `flows` / `decisions` ＋ 散文系 `session` / `story` / `narratives` / `actions` / `questions` / `qrys` ＋ 任意 `domains`。`scs`/`pols`/`aggs` の各要素は `ctx:` で所属 BC を参照
- **AGG 詳細はトップレベル `aggs[]` に集約**：`name`（必須）／`ctx`（必須）／`purpose`／`background`／`constraints[]`／`states`／`transitions[]`（`from`/`to`/`via`/`when`）／`attrs[]`（`name`/`type`/`required`/`note`）／`events[]`（`name`/`params[]`）。`ctxs[].aggs` は AGG 名（PascalCase 文字列）の軽量名簿
- **`scs[].name` は日本語**でアクター＋行為。`actor` 必須（典型値: `Organizer` `Member` `System`）
- **キー順 `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`** を推奨
- **`cmd/evt/agg/trg/emits/qry` の値は英語識別子**。日本語補足は `rules[].why` / `errs[].when` / `note` へ
- **`errs` は `cond` + `err`（ErrorType）+ 任意 `when`**、**`rules` は `rule`（英語の不変条件）+ 任意の `why`**
- **`ctxs[]` に `up`/`dn` 必須**（依存なしは空リスト `[]`、`rel` 併記）。BC 名は `lowercase-with-hyphen`
- **`pols` は EVENTUAL-TX 専用**。SAME-TX 分岐は発行元 scenario の `brs` で書く
- **副作用専用 POLICY**（通知・メール送信など）は `cmd` 省略可（`trg`/`qry`/`bulk`/`evt` のみ）
- **`qry` は判断材料のみ**（コマンド実装内部のデータは含めない）
- **`flows[].steps[]` は実在 scs / pols を参照**（typo は causal-check で検出）
- **`decisions[]` は「採用/不採用理由つきの選択肢ログ」**。`chosen` は `options[].name` のいずれかと一致。各 option に `why`（採用なら）または `why_not`（不採用なら）を書く

---

## DML 出力タイミング（YAML-only）

すべての更新は **`.dml.yaml` 1 ファイル** に対して行う。書き込み手段は `dmlctl set/add/remove`
（推奨）または直接 `Edit`。

| タイミング | 更新するフィールド |
|-----------|--------------------|
| フェーズ 2 完了 | `session` / `story` / `narratives[]` / `flows[]` の枠（初回 `Write`、テンプレ: `references/template.dml.yaml`） → `Bash open <session>.html` 初回起動 |
| フェーズ 3 完了 | `scs[]` 仮 entries ＋ `ctxs[].lang` の新規識別子 |
| フェーズ 4 完了 | `scs[]` / `pols[]` / `flows[]`（happy + 代替 1〜2）／ `ctxs[].lang` ／ `ctxs[].up`/`dn` ／ `ctxs[].description`（BC 散文） |
| フェーズ 4.5 完了 | `ctxs[].lang` を充実 |
| **フェーズ 4.6 完了** | **`aggs[]` の `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states`、`ctxs[].aggs` に AGG 名** |
| **フェーズ 5 完了** | **`scs[].rules[]`（rule/why）／`scs[].errs[]`（cond/err/when）／`aggs[].transitions[]`／`aggs[].attrs[]`／`aggs[].events[].params[]` ＋ `qrys[]`** |
| **フェーズ 6 完了** | **`decisions[]`**（id/topic/chosen/options/affects・options ごとに why/why_not）。`questions[].status` を closed にして `decision_id` を紐付け |
| フェーズ 7（最終） | `dmlctl check` 全観点クリア → 観点別 LLM 評価 → `actions[].done` 更新 |
| ユーザーが「保存して」 | 即座に該当フィールドに反映 |

**書き出し後の品質チェック（必須）**: 詳細は `references/quality-check.md`。

1. **構造チェック**（LLM 不要）— `dmlctl check <file> --check=<name>` を全観点で
2. **意味チェック**（観点別 Agent 起動）— `references/checks/*.md` を 1 観点ずつ

**途中保存と再開**: `session.status` フィールドにフェーズ進捗を書く（例: `"Phase 4.6 完了"`）。
再開時は `dmlctl view --view=session-meta` でフェーズを確認、`actions[].done` で進捗を引き継ぐ。

### DML トップレベル構成（v5）

| フィールド | 編集者 | 役割 |
|----|--------|------|
| `session` | AI/人間 | セッションメタ（id/domain/goal/status/started_at） |
| `story` | AI/人間 | ハッピーパス散文（400〜600 字） |
| `narratives[]` | AI/人間 | 代替シナリオ散文（`flow_id` で `flows[]` と紐付け） |
| `actions[]` | AI/人間 | 次のアクション（done フラグで進捗管理） |
| `questions[]` | AI/人間 | オープンクエスチョン（status: open/closed・closed は decision_id 必須） |
| `qrys[]` | AI/人間 | リードモデル候補（name/ctx/purpose/users/sources/formula） |
| `domains[]` | AI/人間 | ドメイン分類（任意） |
| `ctxs[]` | AI/人間 | BC 宣言（name/description 散文/lang/up/dn/aggs 軽量名簿） |
| `aggs[]` | AI/人間 | AGG 詳細（name/ctx/purpose/background/constraints/states/transitions/attrs/events） |
| `scs[]` | AI/人間 | Scenario（name/ctx/actor/cmd/evt/agg/rules/errs/brs） |
| `pols[]` | AI/人間 | Policy / EVENTUAL-TX（name/ctx/trg/cmd/evt） |
| `flows[]` | AI/人間 | フロー（id/title/kind/steps[]）— HTML §3 を駆動 |
| `decisions[]` | AI/人間 | 意思決定ログ（id/topic/chosen/options/affects） |

HTML の 10 セクションは上記フィールドから機械的に組み立てられる。レンダリング詳細は
`references/html-render-spec.md` 参照。

**`ctxs[].description`（BC 散文）**: 境界の理由 / 含むシナリオ / 目的 / 背景 / 制約 を
Markdown 風の散文として書く。bullet (`- foo`) と `**強調**` は HTML 化で解釈される。

**`qrys[]` リードモデル候補の粒度**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む /
(b) 複数集約・複数 BC を横断 / (c) BULK クエリ（一覧取得）のいずれかのみ記載。

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

1. `python3 scripts/eventstorming_build.py docs/eventstorming/<session>.dml.yaml --artifact --copy`
   - `--artifact`: meta-refresh 等を除去した `<session>-artifact.html` を出力
   - `--copy`: 内容を `pbcopy` でクリップボードへ（macOS 限定）
2. claude.ai の **新しいチャット** に貼り付け「**これを Artifact として表示して**」と依頼
3. 1行報告: `📋 <session>-artifact.html を生成 / クリップボードへコピー済み。claude.ai で Artifact 化してください`

制約: 単一 HTML のみ／自動更新なし（再ビルド後は再貼り付け）／`--copy` は macOS 限定。

---

## 参照ファイル

| ファイル | 用途 |
|---|---|
| `references/dml.schema.yaml` | DML 構文の機械検証スキーマ（JSON Schema Draft 2020-12）。v5 で session/story/narratives/questions/actions/qrys と ctxs[].description を追加 |
| `references/dml-spec.md` | DML 設計ガイドライン（インフラ系判定・SCENARIO 哲学・POLICY 運用・AGG v3・flows/decisions の哲学・付箋色・最小実例） |
| `references/html-render-spec.md` | HTML レンダリング仕様（DML → HTML マッピング、フロー Big Picture グリッド、属性表、意思決定ログ） |
| `references/session-guide.md` | ファシリテーション質問パターン（フェーズ別） |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.dml.yaml` | 新規セッション用 DML スケルトン（旧 template.md を置き換え） |
| `references/quality-check.md` | 品質チェック方針（構造→意味の 2 段階） |
| `references/causal-check.md` | DML 因果連鎖チェック方針 |
| `references/quality-check-agent.md` | 品質チェック起動プロンプト |
| `references/checks/*.md` | 意味チェック 6 観点（scenario-rules-quality / saga-completeness / bc-vocabulary-consistency / agg-purpose-quality / causal-chain-completeness / decision-rationale-clarity） |
| `scripts/dmlctl.py` | DML 観点別 I/O CLI（view/set/add/remove/check） |
| `scripts/dml_filters/*.py` | view と check の Python 実装 |
| `references/causal-check-agent.md` | フロー整合性起動プロンプト |
| `references/chat-output-format.md` | チャット出力テンプレート完全版 |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
| `examples/sample.dml.yaml` | DML 参照例（コミュニティイベント参加ドメイン、`flows[]` / `decisions[]` を含む） |
