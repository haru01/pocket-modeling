---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見し DML（Domain Modeling Language）に情報圧縮する。**`docs/eventstorming/<session>.dml.yaml` がモデル唯一の真実源**。`.md` は物語（§1 ハッピーパス / §2 代替シナリオ）・用語集（§4）・次のアクション（§5）・オープンクエスチョン（§6）・コンテキスト候補（§8）・リードモデル（§10）など、**散文と用語の補足を担う**。フロー図（§3）・意思決定ログ（§7）・集約カード（§9・属性/イベントペイロード/不変条件/エラー）はビルダーが **`.dml.yaml` から自動生成**する。

AI は `.md` と `.dml.yaml` の 2 ファイルを `Write`/`Edit` し、PostToolUse hook が `scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を再生成する（**AI は HTML を直接編集しない**）。**書き込み順は `.dml.yaml` を先・`.md` を後**（モデル拡張は DML 側だけで完結することが多い）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code のチャット本文では SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください（半角 `?` でも可）。判断の軸を提示して一緒に考えます。

---

## ワークフロー（8フェーズ）

| フェーズ | 内容 |
|---------|------|
| 1. スコープ確認 | 対象ドメイン・ゴール・制約を3問で確認 |
| **2. ストーリー確認** | **ハッピーパス（400〜600字）＋代替シナリオ（2〜3本）を提示しユーザー確認。確認後に `.md` を `Write` → `Bash open <session>.html`** |
| 3. イベント発見 | `references/domain-starters.md` から候補提示。追加・削除を確認 |
| 4. CMD→EVT→POLICY チェーン | フロー全体を1本ずつ確認。AGG・BC 境界も同時に拾う。同時に `.dml.yaml` の `flows[]`（happy / 代替 1〜2 本）に **scs[].name（日本語）または pols[].name（PascalCase）の列**として書き留める |
| 4.5. BC 境界 | 文脈で意味が変わる言葉を `LANGUAGE` として記録 |
| **4.6. 目的・背景・制約** | **各 AGG の「目的（必須・30字以上）／背景／制約」を 3 つの問いで言語化し、`.dml.yaml` の `aggs[]` に `name`/`ctx`/`purpose`/`background`/`constraints`/`states` を反映**。詳細: `references/session-guide.md` |
| **5. 不変条件・エラー＋属性・イベントペイロード** | **各 AGG の不変条件は `scs[].rules[]`（`rule`/`why`）、エラーは `scs[].errs[]`（`cond`/`err`/`when`）、属性は `aggs[].attrs[]`（`name`/`type`/`required`/`note`）、emit する EVT は `aggs[].events[].params[]` に書く**。Zod ブロックは廃止 |
| **6. 意思決定ログ** | **複数の選択肢から採用/不採用理由を言語化し `.dml.yaml` の `decisions[]` に記録**（id/topic/chosen/options/affects）。`[?]` で保留してきた判断のうち、選択肢が見えてきたものを昇格させる |
| 7. 整合性チェック → 出力 | DML 整合性を確認し Markdown レポートを最終更新 |

`.md` または `.dml.yaml` の編集ごとに HTML は自動再生成されるが、**ブラウザの自動リロードはしない**（必要に応じて手動）。

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

### 追加された DML
```dml
<該当フェーズで確定した ctxs/aggs/scs/pols/flows/decisions のみ（YAML）>
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
- 表内の付箋ラベルは付箋種別を絵文字＋カラム名で識別（特殊記号は使わない）
- **DML 全文はチャットに流さない**。フェーズごとの抜粋粒度: `chat-output-format.md` §5

### ③ HTML 出力（AI は触らない）

- **トリガー**: `.md` または兄弟 `.dml.yaml` を Write/Edit → PostToolUse hook → `dist/eventstorming/<session>.html` 再生成
- **出力先**: `dist/eventstorming/`（`.md`/`.dml.yaml` は `docs/`、HTML は `dist/`）
- **手動ビルド/全件/監視**: `python3 scripts/eventstorming_build.py <session>.md`（`.dml.yaml` を渡しても兄弟 `.md` を解決）／ `--all` ／ `--watch`
- **フェーズ2完了時のみ** `Bash open dist/eventstorming/<session>.html`。自動リロードはしない
- **Claude Code preview panel への反映** — フェーズ完了テンプレ末尾で `Read dist/eventstorming/<session>.html` を必ず呼ぶ
- **スマホアプリ案内** — HTML 新規/再生成のフェーズ完了テンプレに「📱 HTML をダウンロードしてブラウザで」を必ず添える
- **描画仕様詳細**: `references/html-render-spec.md`、テンプレ: `templates/event-flow.html`

### ④ MD / DML ファイル管理

- アクティブ: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md`（物語・用語集）＋兄弟 `eventstorming-YYYYMMDD-HHMM.dml.yaml`（モデル本体・純 YAML）
- **モデル拡張は基本的に `.dml.yaml` だけを編集する**。`.md` を編集するのは §1 / §2 / §4 / §5 / §6 / §8 / §10（物語・用語集・次アクション・質問・BC・QRY）のみ
- フェーズ2で `.md` を `Write`、以降は両ファイルとも `Edit` で差分更新（**`.dml.yaml` を先に書いてから `.md` を編集**）
- 書き出し後は **必ず** Agent tool で品質チェックを起動（`references/quality-check-agent.md`）。HTML は派生物なのでチェック不要
- **ユーザーが MD/DML を直接編集した場合**: 次ターン応答前に `Read` で再読み込みし兄弟 `.dml.yaml` を照合。差分があれば `Edit` で同期し品質チェック起動

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

DML は **`.md` とは別の兄弟ファイル `docs/eventstorming/<session>.dml.yaml`** に **YAML 直書き**（フェンス不要）で書く。`.md` の §11 はこの `.dml.yaml` へのリンク参照のみ。構文は `references/dml.schema.yaml`（JSON Schema）で機械検証。設計判断・哲学は `references/dml-spec.md`。

- **トップレベルは `ctxs` / `aggs` / `scs` / `pols` の 4 リスト**（任意で `domains` / **`flows` / `decisions`**）。`#` によるセクション区切りは使わない。`scs`/`pols`/`aggs` の各要素は `ctx:` で所属 BC を参照
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

## MD / DML 出力タイミング

**モデル拡張は基本的に `.dml.yaml` だけを Edit する**。`.md` の編集は §1〜§2 の物語、§4（用語集）、§5（次アクション）、§6（質問）、§8（BC）、§10（QRY）に絞られる。

| タイミング | 操作 |
|-----------|------|
| フェーズ2完了 | `.md` を `Write` 新規作成（§1〜§2 ＋ §4/§5/§6/§8/§10 のスケルトン。§3/§7/§9/§11 は DML 駆動で空 or リンク参照のみ）→ `Bash open <session>.html` 初回起動 |
| フェーズ3完了 | `.dml.yaml` を `Write`/`Edit`（scs[] 仮 entries）→ `.md` §4（用語集）を `Edit` |
| フェーズ4完了 | `.dml.yaml` を `Edit`（scs/pols/`flows[]` の happy + 代替 1〜2）→ `.md` §4（用語集）・§8（BC）を `Edit` |
| フェーズ4.5完了 | `.dml.yaml`（`lang`）を `Edit` |
| **フェーズ4.6完了** | **`.dml.yaml` のトップレベル `aggs[]` に `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states` を、`ctxs[].aggs` に AGG 名（PascalCase）を追加** |
| **フェーズ5完了** | **`.dml.yaml` に `scs[].rules[]`（`rule`/`why`）／`scs[].errs[]`（`cond`/`err`/`when`）／`aggs[].transitions[]`／`aggs[].attrs[]`／`aggs[].events[].params[]` を追加** → `.md` §10（QRY カード）を `Edit` |
| **フェーズ6完了（意思決定ログ）** | **`.dml.yaml` に `decisions[]` を追加**（id/topic/chosen/options/affects・options ごとに why/why_not） |
| フェーズ7（最終） | `.dml.yaml` 完成版 → `.md` 全セクション完成版を `Edit` |
| ユーザーが「保存して」 | 即座に `.dml.yaml` → `.md` の順で書き出す |

**書き出し後の品質チェック（必須）**: Agent tool で `references/quality-check-agent.md` を起動。
- **表記チェック (D/F/S 系)**: 形式違反は自動修正
- **モデリング意味チェック (M 系)**: CMD/EVT 命名・CRUD 検出・Saga 完了状態など、命名と業務概念の整合。意味判断のため自動修正せず `[?] M_N` ホットスポット候補として列挙

**途中保存と再開**: MD に `## 再開ポイント` セクションを追加。再開時は読み込んで継続、H・Q 番号は引き継ぐ。

### MD セクション構成

完全テンプレ: `references/template.md`。**§3 / §7 / §9 は `.dml.yaml` から HTML が自動生成するため、`.md` には書かない**（リンク参照や注記のみ）。

セクション順は **「物語 → 用語集 → 次のアクション（読者の次の動き）→ 横断課題（オープン Q／意思決定）→ モデル層（BC／AGG／QRY）→ メタ（DML）」** という読者導線に沿う。

| # | セクション | 編集者 | 内容 |
|---|-----------|--------|------|
| 1 | ハッピーパスストーリー（400〜600字） | AI/人間 | `.md` に散文 |
| 2 | 代替シナリオ（散文のみ） | AI/人間 | `.md` に散文（図は §3 が DML から生成） |
| 3 | Event Walkthrough | **DML 生成** | `.md` には注記のみ。`.dml.yaml` の `flows[]` + `scs[]`/`pols[]` から HTML §3 が自動生成 |
| 4 | 用語集（日本語 ↔ 英語 DML 識別子） | AI/人間 | `.md` にカテゴリ別テーブル。**§8〜§10 を読む前の前置き表** |
| 5 | 次のアクション | AI/人間 | `.md` に箇条書き。**読者の次の動きをトップ近くに置く** |
| 6 | オープンクエスチョン | AI/人間 | `.md` に Q 番号で列挙。因果チェック自動検出分も追記 |
| 7 | 意思決定ログ | **DML 生成** | `.md` には注記のみ。HTML §7 が `decisions[]` から採用/不採用の比較カードを自動描画。`decisions[]` が空なら HTML §7 は非表示 |
| 8 | コンテキスト候補 | AI/人間 | `### english-slug（日本語名）`、`UPSTREAM`/`DOWNSTREAM` 必須、任意で `#### 目的/背景/制約` |
| 9 | 集約候補 | **DML 生成** | `.md` には注記のみ。HTML §9 が `aggs[]` から属性表・ペイロード表・不変条件・エラー・状態遷移を自動描画 |
| 10 | リードモデル候補（`### QRYName（日本語名）`） | AI/人間 | `.md` に詳細（QRY は scs[].qry に紐づく Read Model の説明） |
| 11 | DML | `.dml.yaml` へのリンク参照のみ | DML 全文は別ファイル |

**§10 リードモデル候補**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む / (b) 複数集約・複数 BC を横断 / (c) BULK クエリ（一覧取得）のいずれかのみ記載。

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
| `references/dml.schema.yaml` | DML 構文の機械検証スキーマ（JSON Schema Draft 2020-12）。`ctxs`/`aggs`/`scs`/`pols`/`flows`/`decisions` |
| `references/dml-spec.md` | DML 設計ガイドライン（インフラ系判定・SCENARIO 哲学・POLICY 運用・AGG v3・flows/decisions の哲学・付箋色・最小実例） |
| `references/html-render-spec.md` | HTML レンダリング仕様（DML → HTML マッピング、フロー Big Picture グリッド、属性表、意思決定ログ） |
| `references/session-guide.md` | ファシリテーション質問パターン（フェーズ別） |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.md` | `.md` レポートテンプレート（DML 駆動セクションは注記のみ） |
| `references/quality-check.md` | 品質チェックルール（D/F/S/M 系） |
| `references/causal-check.md` | DML 因果チェーンチェックルール |
| `references/quality-check-agent.md` | 品質チェック起動プロンプト |
| `references/causal-check-agent.md` | フロー整合性起動プロンプト |
| `references/chat-output-format.md` | チャット出力テンプレート完全版 |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
| `examples/sample.dml.yaml` | DML 参照例（コミュニティイベント参加ドメイン、`flows[]` / `decisions[]` を含む） |
