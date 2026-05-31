---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見し DML（Domain Modeling Language）に情報圧縮する。**`docs/eventstorming/<session>.dml.yaml` 1 ファイルがモデル唯一の真実源**（v5 以降）。散文（`narratives` — v8 で旧 `story:` を統合、`kind: happy`/`alt` で区別）・次のアクション（`actions`）・オープンクエスチョン（`questions`）・BC 散文（`contexts[].description`）・リードモデル（`queries`）・意思決定ログ（`decisions`）・集約カード（`aggregates`）・コンテキスト言語（`contexts[].lang`）・依存方向（`contexts[].up/dn`）はすべて DML 内のトップレベル項目として保持される。`.md` は廃止された。

AI は **`scripts/dmlctl.py` 経由でしか** DML を読み書きできない（PreToolUse フック `hooks/block_direct_dml.py` が `Read`/`Edit`/`Write` を技術的にブロック）。新規作成は `dmlctl init`、参照は `dmlctl view --view=<name>`（観点別スライス）、編集は `dmlctl set/add/remove/update`。リスト要素の更新は `dmlctl update --where=<key=value>` を使う。dmlctl 経由の書き込みは内部で build + validate を自動実行する（`--no-postprocess` で抑止可能）。

**値の渡し方（落とし穴注意）**:

| 渡し方 | 評価 | 用途 |
|---|---|---|
| `--value=<lit>` / `--item=<lit>` | **YAML としてパース** | スカラー・配列・dict すべて。インラインで完結するならこれが第一選択 |
| `add --item-file=<path>` | **YAML としてパース** | 大型の構造化要素（dict/配列）をファイルから |
| `set --value-file=<path>` | **生テキスト（1 個の文字列）として埋め込む。YAML 評価しない** | **長文 prose の文字列値専用**。配列・dict には使わない |

- **配列・構造値を書くときに `set --value-file` を使ってはいけない**（YAML ソース全体が 1 個の文字列として格納され schema 違反になる）。配列なら `set --value='[...]'` か `add --item=` を 1 件ずつ。
- **`--value`/`--item` のインラインで足りるなら、一時ファイルを作らない**。`Write` ツールで `/tmp/*.yaml` 等を作ってから渡すのはアンチパターン。長文 prose 1 個を `--value-file` で渡す場合に限り一時ファイルが正当化される。

**ネスト・部分更新を効率よく書く（トークン節約）**:

- **リスト要素のネストへ直接 set** — `set --path='contexts[name=billing].lang.states' --value='{...}'`。`key[selKey=selVal]` でリスト要素をキー選択して配下に降りられる（`remove --path='contexts[name=x]'` も可）。`lang` 全体を再投入せず狙った枝だけ書ける。
- **`update --merge-yaml` は再帰マージ**（nested dict は保持・リーフは置換）。`--merge-yaml='{lang: {states: {...}}}'` で `lang.actors` 等を壊さず `states` だけ追加できる。dict 全体を置換したいときだけ `update --set-key`。
- **書く前に `--dry-run`** — `set/add/update/remove` に `--dry-run` を付けると、本体を書かずに編集後の schema 検証だけ実行して違反を返す。型・必須キーの違反でファイルを汚して書き直す往復を防ぐ。

**スキーマ落とし穴チートシート**（過去に往復リトライを生んだ実例）:

| 項目 | 正 | 誤りがち |
|---|---|---|
| `session.phase` | 文字列 `'"3"'`（enum `'1'..'7'`） | 数値 `3` → type 違反 |
| `queries[].users` | 文字列 `'受付・医師'` | リスト `[A, B]` → type 違反 |
| `aggregates[].transitions[]` | `via` 必須（命令が無い遷移は書けない） | `when` だけ → required 違反 |
| `policies[].name` / AGG・EVENT 名 | PascalCase `^[A-Z][A-Za-z0-9]*$` | 日本語名 → pattern 違反 |
| state 名の重複 | BC ごとに `lang.states` でラベル差別化 or 改名 | 同名放置 → cross_bc 衝突 |
| `merge-yaml` で `lang` 部分更新 | nested で渡す（再帰マージ） | 旧仕様は浅置換だった（現在は再帰）|

PostToolUse hook が `scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を再生成する（**AI は HTML を直接編集しない**）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code のチャット本文では SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください（半角 `?` でも可）。判断の軸を提示して一緒に考えます。

---

## ワークフロー（9フェーズ）

各フェーズの「書き出し対象」は **`.dml.yaml` のトップレベルフィールド**。AI は dmlctl 経由
（`init` / `set` / `add` / `remove` / `update`）で更新する。直接 `Read`/`Edit`/`Write` は PreToolUse フックで自動ブロックされるため不可。

| フェーズ | 書き出し対象（`.dml.yaml` フィールド） |
|---------|--------------------------------------|
| 1. スコープ確認 | `session`（id/domain/goal/status） |
| **2. ストーリー確認** | **`narratives[]`（`kind: happy` のハッピーパス散文 1 本 + `kind: alt` の代替シナリオ 2〜3 本）** → `Bash open <session>.html` |
| 3. イベント発見 | `scenarios[]` 仮 entries ＋ `contexts[].lang` 新規識別子 |
| 4. CMD→EVT→POLICY チェーン | `scenarios[]`（`next`/`brs[].terminal` 付き）／ `policies[]` / `narratives[]`（happy + 代替 1〜2 を `entry` 付きで）／ `contexts[]` の `up`/`dn` |
| 4.5. BC 境界 | `contexts[].lang` 充実（文脈で意味が変わる言葉を記録） |
| **4.6. 目的・背景・制約** | **`aggregates[]` の `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states` ＋ `contexts[].description`（BC 散文）** |
| **5. 不変条件・エラー＋属性・イベントペイロード** | **`scenarios[].rules[]`（rule/why）／`scenarios[].errs[]`（cond/err/when）／`aggregates[].transitions[]`／`aggregates[].attrs[]`／`aggregates[].events[].params[]` ＋ `queries[]`（リードモデル候補）** |
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
- **ポイント解説原則** — DDD／EventStorming の専門用語（EVT / CMD / POLICY / AGG / BC / SAME-TX / EVENTUAL-TX / ACL / Conformist など）が**初出のとき**は、`references/term-glossary.md` を引いて **2 行構成** で簡潔に添える。
  - **1 行目**: 「💡 **用語名** ＝ <日常の業務の言葉で 1 文。他の DDD／専門用語に依存しない>」
  - **2 行目**: 「例: <今回のドメインから「⚪️が起きたら△△する」形の具体例>」
  - **NG（専門用語で専門用語を説明）**: 「POLICY ＝ EVENTUAL-TX を表す反応」「BC ＝ Ubiquitous Language の境界」
  - **OK（業務語で言い切る）**: 「POLICY ＝ ある出来事が起きたら自動で次の処理が走るという約束事。例: 注文が確定したら在庫を引き当てる」
  - **1 ターンに 1〜2 用語まで**。3 つ以上重なる場合は、今のその問いに直結する 1 つだけに絞る（用語が多いと問いがぼやける）
  - **ユーザーが「もっとわかりやすく／噛み砕いて／？」と求めたら**、抽象定義をやめて **比喩・対比・小さな表** で再説明する（パターン: `references/term-glossary.md` §「噛み砕きパターン」）
  - 既出は繰り返さない。意思決定の議論では `why`/`why_not` を**業務文脈の言葉**で引き出し、抽象用語（「責務違反」「DDD 的に正しい」等）だけで終わらせない（良し悪し例: `references/term-glossary.md`）
- **毎ターン末尾** に `> 迷ったら \`？\` を送ってください`
- **git 操作の禁止** — セッション中は AI から `git commit` / `git push` / `git add` / `gh pr create` 等を**自発的に実行しない**。理由：モデルの粒度・ホットスポットの解決はユーザーの判断に依存し、AI が勝手にスナップショットを切るとセッションの一貫性が崩れるため。**ユーザーが「コミットして」「push して」と明示的に指示したときのみ実行**する。「フェーズ完了したから」「区切りが良いから」を理由にしたコミット提案も避ける（ユーザーが必要なら頼んでくる）

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

**(b) フェーズ完了** — Markdown + 構造化テーブル + DML 抜粋（`contexts[].lang` の追加識別子も含む）+ HTML パス案内：

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
<該当フェーズで確定した contexts/aggregates/scenarios/policies/flows/decisions のみ（YAML）>
```

### 新規ラベルの追加（DML `contexts[].lang`）
| 英語識別子 | 日本語ラベル | 所属 BC | 種別 |
|---|---|---|---|

### ホットスポット
- H{n}. [?] <設計判断>：<理由>

### 未確認事項
- Q{n}. <項目>：<確認内容>

---
**次のフェーズ: <次フェーズ名>**

ここで問いです。

<問い 1つ>

> 迷ったら `？` を送ってください
```

- H・Q 番号はセッション通じて通し（解決済みは欠番、再利用しない）
- 表内の付箋ラベルは付箋種別を絵文字＋カラム名で識別（特殊記号は使わない）
- **DML 全文はチャットに流さない**。フェーズごとの抜粋粒度: `chat-output-format.md` §5

### ③ HTML 出力（AI は触らない）

- **トリガー**: dmlctl 経由の書き込み（`init` / `set` / `add` / `remove` / `update`）→ dmlctl 自身が build + validate を自動実行 → `dist/eventstorming/<session>.html` 再生成。直接 `Edit`/`Write` は PreToolUse フックで自動ブロック
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
  - 書き込み：`python3 scripts/dmlctl.py set/add/remove <file> --path=... --value=...`（配列・dict は `--value='[...]'` か `add --item=` を使う。`set --value-file` は長文 prose 文字列専用で配列に使わない — 冒頭の「値の渡し方」表を参照）
  - 観点一覧：`dmlctl views` / `dmlctl checks`
- 直接 `Read`/`Edit`/`Write` は PreToolUse フック（`scripts/hooks/block_direct_dml.py`）で自動ブロック。`Bash python3 dmlctl.py ...` のみが I/O 経路。**一時ファイルの作成も `--value`/`--item` のインラインで代替できるなら避ける**（`Write` で `/tmp/*.yaml` を作るのはアンチパターン）
- フェーズ 2 で `dmlctl init <path> --session-id=... --domain=... [--goal=...]` で新規 DML を生成（テンプレートから session 入り空 DML を作成）
- 書き出し後は **必ず** Agent tool で品質チェックを起動（`references/quality-check-agent.md`）。HTML は派生物なのでチェック不要
- **ユーザーが DML を直接編集した場合**: 次ターン応答前に `dmlctl view` で観点別に再読み込みし変更を把握、必要なら品質チェックを起動

---

## Event Flow（DML 駆動・v6）

§3 のフロー図は **`narratives[].entry` を起点に `scenarios[].next` を辿り、`scenarios[].evt → policies[].trg` のマッチで policy を自動挿入してビルダーが自動生成**する。AI/人間が手書きの DSL を書く場面は無い。

```yaml
narratives:
  - id: happy
    title: ハッピーパス — イベント作成から参加確定まで
    kind: happy
    entry: 主催者がイベントを作成する         # フロー開始 scenarios[].name
    prose: |
      <ハッピーパス散文>
  - id: alt-waitlist
    title: 代替シナリオ — 残席ゼロで繰上待ち
    kind: alt
    entry: 参加者がイベントに参加申込する     # 任意。指定なし → §3 描画は省略
    prose: |
      <代替シナリオ散文>

scenarios:
  - name: 主催者がイベントを作成する
    cmd: CreateEvent
    evt: EventCreated
    next: 参加者がイベントに参加申込する      # 全フロー共通の次（文字列）

  - name: 参加者がイベントに参加申込する
    cmd: ApplyForEvent
    next: システムが申込を確定し監査記録する  # 通常分岐の継続先
    brs:
      - { cond: "...", evt: ParticipationApplied }
      - { cond: "...", evt: ParticipationWaitlisted, terminal: alt-waitlist }  # この分岐は alt-waitlist 終端

  - name: 注文確定（分岐点の例）
    cmd: PlaceOrder
    evt: OrderPlaced
    next:                                     # フロー分岐時は dict 形式
      happy: 旧機種発送
      alt-timeout: タイムアウト検知
```

- **scenarios[].next**: 文字列 = 全フロー共通の次／dict = `narratives[].id` ごとの次。省略 = フロー終端
- **scenarios[].brs[].terminal**: `<narratives[].id>` を指定すると「この brs 分岐が発火したらそのフローはここで終わる」と宣言
- 同一 `ctx` の連続ステップはビルダー側で **1 レーンに併合**され、`ctx` 変化やポリシー遷移は非同期矢印で描画
- POLICY が `trgs`（複数トリガー join）を持てば **BPMN シンクバー（Σ N）** で表現、`bulk: true` であれば **fanout（× N）** で描画
- 図の HTML 表現詳細は `references/html-render-spec.md` §5

---

## DML 記述ルール（要点）

DML は **`docs/eventstorming/<session>.dml.yaml`** 1 ファイルに **YAML 直書き**（フェンス不要）で書く。構文は `references/dml.schema.yaml`（JSON Schema）で機械検証。設計判断・哲学は `references/dml-spec.md`。

- **トップレベル**（v8）: モデル本体 `contexts` / `aggregates` / `scenarios` / `policies` / `decisions` ＋ 散文＋フロー定義 `session` / `narratives`（v8 で `story:` を統合・`kind: happy`/`alt` で区別） / `actions` / `questions` / `queries` ＋ 任意 `domains`。`scenarios`/`policies`/`aggregates` の各要素は `ctx:` で所属 BC を参照。**フロー連鎖は `narratives[].entry` ＋ `scenarios[].next` / `brs[].terminal` で表現**（旧 `flows[]` は廃止）
- **AGG 詳細はトップレベル `aggregates[]` に集約**：`name`（必須）／`ctx`（必須）／`purpose`／`background`／`constraints[]`／`states`／`transitions[]`（`from`/`to`/`via`/`when`）／`attrs[]`（`name`/`type`/`required`/`note`）／`events[]`（`name`/`params[]`）。`contexts[].aggs` は AGG 名（PascalCase 文字列）の軽量名簿
- **`scenarios[].name` は日本語**でアクター＋行為。`actor` 必須（典型値: `Organizer` `Member` `System`）
- **キー順 `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`** を推奨
- **`cmd/evt/agg/trg/emits/qry` の値は英語識別子**。日本語補足は `rules[].why` / `errs[].when` / `note` へ
- **`errs` は `cond` + `err`（ErrorType）+ 任意 `when`**、**`rules` は `rule`（英語の不変条件）+ 任意の `why`**
- **`contexts[]` の `up`/`dn` は推奨**（schema 上は optional だが、依存方向を明示すると BC マップが立体化する）。**依存なしは空リスト `[]`** を書いて「考慮済み」と示す。`rel` を併記すれば CML リレーション語彙が HTML §6 に描画される。BC 名は `lowercase-with-hyphen`
- **`policies` は EVENTUAL-TX 専用**。SAME-TX 分岐は発行元 scenario の `brs` で書く
- **副作用専用 POLICY**（通知・メール送信など）は `cmd` 省略可（`trg`/`qry`/`bulk`/`evt` のみ）
- **POLICY の `cmd` が AGG を変更するなら `agg` を併記する**（v7 追加。scenarios と対称化）。dangling_cmd チェックは `policies[].cmd` も declared として扱う
- **`qry` は判断材料のみ**（コマンド実装内部のデータは含めない）
- **`scenarios[].next` / `brs[].terminal` の参照は `dmlctl check --check=flow_chain_resolution` で検証**（typo・存在しない narrative ID を検出）
- **`decisions[]` は「採用/不採用理由つきの選択肢ログ」**。`chosen` は `options[].name` のいずれかと一致。各 option に `why`（採用なら）または `why_not`（不採用なら）を書く

---

## DML 出力タイミング（YAML-only）

すべての更新は **`.dml.yaml` 1 ファイル** に対して行う。書き込み手段は `dmlctl set/add/remove`
（必須・直接 `Edit`/`Write` はフックで遮断）。

| タイミング | 更新するフィールド |
|-----------|--------------------|
| フェーズ 2 完了 | `session` / `narratives[]`（`id`/`title`/`kind`/`entry`/`prose` — `kind: happy` 1 本 + `kind: alt` 2〜3 本、prose は粗で可）（初回 `dmlctl init` → 続けて `dmlctl set narratives` 等で narratives を追加） → `Bash open <session>.html` 初回起動 |
| フェーズ 3 完了 | `scenarios[]` 仮 entries ＋ `contexts[].lang` の新規識別子 |
| フェーズ 4 完了 | `scenarios[]`（`next` / `brs[].terminal` を含む）／ `policies[]` ／ `narratives[].entry`（happy + 代替 1〜2）／ `contexts[].lang` ／ `contexts[].up`/`dn` ／ `contexts[].description`（BC 散文） |
| フェーズ 4.5 完了 | `contexts[].lang` を充実 |
| **フェーズ 4.6 完了** | **`aggregates[]` の `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states`、`contexts[].aggs` に AGG 名** |
| **フェーズ 5 完了** | **`scenarios[].rules[]`（rule/why）／`scenarios[].errs[]`（cond/err/when）／`aggregates[].transitions[]`／`aggregates[].attrs[]`／`aggregates[].events[].params[]` ＋ `queries[]`** |
| **フェーズ 6 完了** | **`decisions[]`**（id/topic/chosen/options/affects・options ごとに why/why_not）。`questions[].status` を closed にして `decision_id` を紐付け |
| フェーズ 7（最終） | `dmlctl check` 全観点クリア → 観点別 LLM 評価 → `actions[].done` 更新 |
| ユーザーが「保存して」 | 即座に該当フィールドに反映 |

**書き出し後の品質チェック（必須）**: 詳細は `references/quality-check.md`。

1. **構造チェック**（LLM 不要）— `dmlctl check <file> --check=<name>` を全観点で
2. **意味チェック**（観点別 Agent 起動）— `references/checks/*.md` を 1 観点ずつ

**途中保存と再開**: `session.status` フィールドにフェーズ進捗を書く（例: `"Phase 4.6 完了"`）。
再開時は `dmlctl view --view=session-meta` でフェーズを確認、`actions[].done` で進捗を引き継ぐ。

### DML トップレベル構成（v8）

| フィールド | 編集者 | 役割 |
|----|--------|------|
| `session` | AI/人間 | セッションメタ（id/domain/goal/status/started_at） |
| `narratives[]` | AI/人間 | 散文（v8 で旧 `story:` を統合）。`id`/`kind`(`happy`\|`alt`)/`title`/`entry`/`prose`。`kind: happy` は 1 本（400〜600 字）、`kind: alt` は複数可（100〜200 字）。`entry` を持つ narrative は HTML §2 フロー図 1 行を駆動 |
| `actions[]` | AI/人間 | 次のアクション（done フラグで進捗管理） |
| `questions[]` | AI/人間 | オープンクエスチョン（status: open/closed・closed は decision_id 必須） |
| `queries[]` | AI/人間 | リードモデル候補（name/ctx/purpose/users/sources/formula） |
| `domains[]` | AI/人間 | ドメイン分類（任意） |
| `contexts[]` | AI/人間 | BC 宣言（name/description 散文/lang/up/dn/aggregates 軽量名簿） |
| `aggregates[]` | AI/人間 | AGG 詳細（name/ctx/purpose/background/constraints/states/transitions/attrs/events） |
| `scenarios[]` | AI/人間 | Scenario（name/ctx/actor/cmd/evt/agg/rules/errs/brs/`next`）。`next` と `brs[].terminal` でフロー連鎖を駆動 |
| `policies[]` | AI/人間 | Policy / EVENTUAL-TX（name/ctx/trg/cmd/evt/agg） |
| `decisions[]` | AI/人間 | 意思決定ログ（id/topic/chosen/options/affects） |

HTML の 9 セクション（v8 で §1/§2 統合）は上記フィールドから機械的に組み立てられる。レンダリング詳細は
`references/html-render-spec.md` 参照。

**`contexts[].description`（BC 散文）**: 境界の理由 / 含むシナリオ / 目的 / 背景 / 制約 を
Markdown 風の散文として書く。bullet (`- foo`) と `**強調**` は HTML 化で解釈される。

**`queries[]` リードモデル候補の粒度**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む /
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
| `references/dml.schema.yaml` | DML 構文の機械検証スキーマ（JSON Schema Draft 2020-12）。v5 で session/narratives/questions/actions/queries と contexts[].description を追加、v8 で旧 `story:` を `narratives[]` に統合 |
| `references/dml-spec.md` | DML 設計ガイドライン（インフラ系判定・SCENARIO 哲学・POLICY 運用・AGG v3・flows/decisions の哲学・付箋色・最小実例） |
| `references/html-render-spec.md` | HTML レンダリング仕様（DML → HTML マッピング、フロー Big Picture グリッド、属性表、意思決定ログ） |
| `references/session-guide.md` | ファシリテーション質問パターン（フェーズ別） |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.dml.yaml` | 新規セッション用 DML スケルトン（旧 template.md を置き換え） |
| `references/term-glossary.md` | DDD／EventStorming 用語の 1 行ポイント解説辞書。専門用語初出時に AI が引いてチャットに添える |
| `references/quality-check.md` | 品質チェック方針（構造→意味の 2 段階） |
| `references/causal-check.md` | DML 因果連鎖チェック方針 |
| `references/quality-check-agent.md` | 品質チェック起動プロンプト |
| `references/checks/*.md` | 意味チェック 6 観点（scenario-rules-quality / saga-completeness / bc-vocabulary-consistency / agg-purpose-quality / causal-chain-completeness / decision-rationale-clarity） |
| `scripts/dmlctl.py` | DML 観点別 I/O CLI（view/set/add/remove/check） |
| `scripts/dml_filters/*.py` | view と check の Python 実装 |
| `references/causal-check-agent.md` | フロー整合性起動プロンプト |
| `references/chat-output-format.md` | チャット出力テンプレート完全版 |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
| `examples/sample.dml.yaml` | DML 参照例（コミュニティイベント参加ドメイン、`narratives[]`（entry 付き）/ `decisions[]` を含む） |
