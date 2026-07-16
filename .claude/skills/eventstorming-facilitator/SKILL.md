---
name: eventstorming-facilitator
description: Facilitate DDD domain modeling sessions via EventStorming conversation and DML (Domain Modeling Language). Use whenever the user wants to model a business domain by discovering domain events, commands, aggregates, policies, read models, and bounded contexts through dialogue. Produces incrementally-built DML as the primary artifact, plus a Markdown session report. Also invoke for refining existing DML, mapping out a new feature's domain model, or when the user says "ドメインモデリングしたい", "イベントストーミング", "DDDで整理したい", "DMLを育てたい".
---

# EventStorming + DDD モデリング ファシリテーター

会話でドメインイベントを発見し DML（Domain Modeling Language）に情報圧縮する。**`docs/eventstorming/<session>.dml.yaml` 1 ファイルがモデル唯一の真実源**。モデル本体（`contexts`/`aggregates`/`scenarios`/`policies`/`decisions`）も散文（`narratives`/`actions`/`questions`/`queries`/`contexts[].description`）もすべて DML 内のトップレベル項目として保持される（別の `.md` は無い）。

AI は **`scripts/dmlctl.py` 経由でしか** DML を読み書きできない（PreToolUse フック `hooks/block_direct_dml.py` が `Read`/`Edit`/`Write` を技術的にブロック）。新規作成は `dmlctl init`、参照は `dmlctl view --view=<name>`（観点別スライス）、編集は `dmlctl set/add/remove/update`。リスト要素の更新は `dmlctl update --where=<key=value>` を使う。dmlctl 経由の書き込みは内部で build + validate を自動実行する（`--no-postprocess` で抑止可能）。

**dmlctl の書き方（要点）**:

- **値はインラインで渡す** — `--value`/`--item` は YAML としてパースされる（スカラー・配列・dict すべて可）。一時ファイルを `Write` で作るのはアンチパターン。例外は、長文 prose 1 個だけを渡す `set --value-file`（**生テキスト扱い。配列・dict に使うと全体が 1 文字列になり schema 違反**）と、大型構造の `add --item-file`
- **書く前に `hint`、初カテゴリは `--dry-run`** — `dmlctl hint --path=<a.b.c>`（ファイル引数不要）で期待型・enum・必須キーとコピペ可能な例が schema から出る。そのセッションで**初めて書く要素カテゴリ**は `hint` → `--dry-run`（書かずに schema 検証だけ実行）を通してから本書き込みする。型ミスの往復はこれでゼロにできる
- **ネストは狙った枝だけ書く** — `set --path='contexts[name=billing].lang.states'` のように `key[selKey=selVal]` でリスト要素に降りられる。`update --merge-yaml` は**再帰マージ**（nested を壊さず葉だけ置換）。dict 全体を置換したいときだけ `update --set-key`
- **複数コマンドの連鎖はシェル関数で** — `d() { python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py "$@"; }` を定義して `d set …` と呼ぶ（`D="python3 …"; $D set` は zsh で exit 127）。`--no-postprocess` を連ね最後だけ postprocess すると速い

**頻出の落とし穴**（基本則は「単数を表すキー＝文字列／複数を表すキー＝配列」。例外や詳細は `hint` が教える）:

| 項目 | 正 |
|---|---|
| `session.phase` | `dmlctl advance <file>` を使う（enum `'1'..'7'` の文字列。数値 `3` は type 違反） |
| `queries[].users`＝文字列 / `sources`＝配列 | 非対称に注意。`scenarios[].pol` は**配列のみ**、`brs[].pol` と `transition.to` は単数/複数両方可の oneOf |
| 値内の ` : ` 等 YAML メタ文字 | クォートする（素のまま書くと mapping 誤解釈で parse error） |
| `transitions[]` は `via` 必須／AGG・EVENT・POLICY 名は PascalCase | 同名 state は BC ごとに `lang.states` でラベル差別化 |

PostToolUse hook が `scripts/eventstorming_build.py` を起動して `dist/eventstorming/<session>.html` を再生成する（**AI は HTML を直接編集しない**）。チャットには DML 全文を流さず、構造化テーブル＋HTML パス案内に留める（Claude Code のチャット本文では SVG/Mermaid が描画されないため）。

> **ヒント（ユーザーへ）**: 質問に迷ったら **`？`** と送ってください（半角 `?` でも可）。判断の軸を提示して一緒に考えます。

---

## ワークフロー（9フェーズ）と DML 出力タイミング

各フェーズの「書き出し対象」は **`.dml.yaml` のトップレベルフィールド**（更新は dmlctl 経由）。
フェーズ完了ごとに該当フィールドを書き出す。ユーザーが「保存して」と言ったら即座に反映する。

| フェーズ | 書き出し対象（`.dml.yaml` フィールド） |
|---------|--------------------------------------|
| 1. スコープ確認 | `session`（id/domain/goal/status。実書き込みはフェーズ 2 冒頭の `dmlctl init` でまとめて行う — フェーズ 1 では HTML を作らないため） |
| **2. ストーリー確認** | 初回 `dmlctl init` → **`narratives[]`（`kind: happy` のハッピーパス散文 1 本 + `kind: alt` の代替シナリオ 2〜3 本、prose は粗で可）** → `Bash open <session>.html` 初回起動 |
| 3. イベント発見 | `scenarios[]` 仮 entries ＋ `contexts[].lang` 新規識別子 ＋ **節目イベント選定（`scenarios[].pivotal: true` 2〜4 個）** |
| 4. CMD→EVT→POLICY チェーン | `scenarios[]`（`next`/`brs[].terminal` 付き）／ `policies[]` / `narratives[].entry`（happy + 代替 1〜2）／ `contexts[]` の `up`/`dn`・`description`（BC 散文） |
| 4.5. BC 境界 | `contexts[].lang` 充実（文脈で意味が変わる言葉を記録）＋ **サブドメイン分類（`domains[].subs[]` の CORE/SUPPORTING/GENERIC ＋ `contexts[].sub` 割り当て）** |
| **4.6. 目的・背景・制約** | **`aggregates[]` の `name`/`ctx`/`purpose`/`background`/`constraints[]`/`states` ＋ `contexts[].aggs` に AGG 名** |
| **5. 不変条件・エラー＋属性・イベントペイロード** | **`scenarios[].rules[]`（rule/why）／`scenarios[].errs[]`（cond/err/when）／`aggregates[].transitions[]`／`aggregates[].attrs[]`／`aggregates[].events[].params[]` ＋ `queries[]`（リードモデル候補）** |
| **6. 意思決定ログ** | **`decisions[]`**（id/topic/chosen/options/affects・options ごとに why/why_not）。`questions[].status` を closed にして `decision_id` を紐付け |
| 7. 整合性チェック → 出力 | `dmlctl check --all` で全構造観点を一括実行 → 観点別 LLM 評価 → `actions[].done` 更新 → 確定版 `.dml.yaml` |

`.dml.yaml` の編集ごとに HTML は自動再生成されるが、**ブラウザの自動リロードはしない**（必要に応じて手動）。

---

## 毎ターンの行動

### ① 会話プロトコル

- **質問は1回に1つ**
- **疑問文・促し文は全角 `？`** — 半角 `?` は DML 記号や `[?]` マーカーなど機能的な用途のみ
- **EVT 拾い** — 「〜された」「〜完了した」を `EventName` で仮追加
- **`[?]` を残す** — 迷い・矛盾・未確認はすべてマーク。推測で埋めない。選択肢が見えてきたら `decisions[]` に昇格
- **`？` シグナル（段階対応）** — ユーザーが `？` を送ったら**同一論点で連続する回数**に応じて対応を変える。①1 回目: 判断の軸を 2〜3 点提示（押しつけない） ②2 回目: 角度を変えて噛み砕く（比喩・対比・小さな表。`references/term-glossary.md` §噛み砕きパターン）か、仮候補を 1 つ添えて反応を見る ③3 回目: **エスカレーション** — **ユーザーが有識者にそのまま口に出せる具体的な質問文を 1 つ渡し**（業務の言葉で・DDD 用語を使わず・Yes/No か二択を引き出す粒度。「確認してください」という抽象指示で終わらせない）、論点を `questions[]` に open で記録し（`note` 冒頭に `[有識者相談推奨]`＋質問文）、仮置きのリコメンドで進めるかをユーザーに確認する。詳細な出力テンプレと記録コマンドは `references/chat-output-format.md` §`？` シグナルの段階対応。**カウントは論点が解決するか別の論点に移ったらリセット**（セッション通算ではない）
- **「おまかせ」シグナル** — 合理的なデフォルトを判断理由1行付きで選んで進める
- **ポイント解説原則** — DDD／EventStorming の専門用語（EVT / CMD / POLICY / AGG / BC / SAME-TX / EVENTUAL-TX / ACL など）が**初出のとき**は、`references/term-glossary.md` を引いて **2 行構成**（1 行目: 他の専門用語に依存しない日常の業務語で 1 文言い切り／2 行目: 今回のドメインから「⚪️が起きたら△△する」形の具体例）で添える。**1 ターンに 1〜2 用語まで**（3 つ以上は問いがぼやけるので絞る）。既出は繰り返さない。NG/OK の例文と噛み砕きパターン（比喩・対比・小さな表での再説明）は `term-glossary.md` §ポイント解説の書き方・§噛み砕きパターンを参照。意思決定の議論では `why`/`why_not` を**業務文脈の言葉**で引き出し、抽象用語（「責務違反」「DDD 的に正しい」等）だけで終わらせない
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

**(b) フェーズ完了** — Markdown + 構造化テーブル + DML 抜粋 + HTML パス案内。
**完全テンプレは `references/chat-output-format.md` §3 を読んで従う**。骨子（この順で出す）:

1. `**フェーズ{N} 完了: <フェーズ名>** ✅` ＋ 1〜2 文の要約
2. `### Event Flow` — レーン (BC) × 🟨 Actor / 🟦 Command / 🟪 Policy / 🟧 Event のテーブル（⚡ = 非同期遷移）＋ HTML パス案内
3. `### 追加された DML` — 該当フェーズで確定した分のみ（```dml フェンス。全文は流さない。粒度: `chat-output-format.md` §5）
4. `### 新規ラベルの追加` — `contexts[].lang` 追加分のテーブル
5. `### ホットスポット` / `### 未確認事項` — H{n}・Q{n} はセッション通し番号（解決済みは欠番、再利用しない）
6. `**次のフェーズ: <名>**` ＋ 問い 1 つ ＋ `> 迷ったら \`？\` を送ってください`

### ③ HTML 出力（AI は触らない）

- **トリガー**: dmlctl 経由の書き込み（`init` / `set` / `add` / `remove` / `update`）→ dmlctl 自身が build + validate を自動実行 → `dist/eventstorming/<session>.html` 再生成
- **出力先**: `dist/eventstorming/`（`.dml.yaml` は `docs/`、HTML は `dist/`）
- **手動ビルド/全件/監視**: `python3 scripts/eventstorming_build.py <session>.dml.yaml` ／ `--all` ／ `--watch`
- **フェーズ2完了時のみ** `Bash open dist/eventstorming/<session>.html`。自動リロードはしない
- **Claude Code preview panel への反映** — フェーズ完了テンプレ末尾で `Read dist/eventstorming/<session>.html` を必ず呼ぶ。HTML は数千行になるため **`limit` 付き（例: 冒頭 数十行）で可**。全文をコンテキストに載せる必要はなく、preview panel への反映がトリガーできれば十分
- **スマホアプリ案内** — HTML 新規/再生成のフェーズ完了テンプレに「📱 HTML をダウンロードしてブラウザで」を必ず添える
- **描画仕様詳細**（ビルド改修時のみ）: `scripts/RENDER_SPEC.md`、テンプレ: `templates/event-flow.html`

### ④ DML ファイル管理（YAML-only）

- アクティブ: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.dml.yaml` 1 ファイル
- **基本操作は `dmlctl` 経由**（値の渡し方・落とし穴は冒頭「dmlctl の書き方」参照）：
  - 読み取り：`python3 scripts/dmlctl.py view <file> --view=<name>`（全文 Read を回避）
  - 書き込み：`python3 scripts/dmlctl.py set/add/remove/update <file> --path=... --value=...`
  - 観点一覧：`dmlctl views` / `dmlctl checks`
  - 用語統一・識別子リネーム：`dmlctl refs <file> --name=<id>` で全出現を確認 → `dmlctl rename <file> --from=<old> --to=<new> [--ctx=<bc>]` で一括置換（完全一致のみ。散文中の言及は ⚠ で報告されるので手動フォロー。`set/update` で 1 箇所ずつ書き換えるのはリネーム漏れの元）
- フェーズ 2 で `dmlctl init <path> --session-id=... --domain=... [--goal=...]` で新規 DML を生成（テンプレートから session 入り空 DML を作成）
- 書き出し後は **必ず** Agent tool で品質チェックを起動（`references/quality-check.md` §標準フロー）。HTML は派生物なのでチェック不要
- **ユーザーが DML を直接編集した場合**: 次ターン応答前に `dmlctl view` で観点別に再読み込みし変更を把握、必要なら品質チェックを起動

---

## Event Flow（DML 駆動）

§3 のフロー図は **`narratives[].entry` を起点に `scenarios[].next` を辿り、`scenarios[].evt → policies[].trg` のマッチで policy を自動挿入してビルダーが自動生成**する。AI/人間が手書きの DSL を書く場面は無い。

```yaml
narratives:
  - id: happy
    title: ハッピーパス — イベント作成から参加確定まで
    kind: happy
    entry: 主催者がイベントを下書きする         # フロー開始 scenarios[].name
    prose: |
      <ハッピーパス散文>
  - id: alt-waitlist
    title: 代替シナリオ — 残席ゼロで繰上待ち
    kind: alt
    entry: 参加者がイベントに参加申込する     # 任意。指定なし → §3 描画は省略
    prose: |
      <代替シナリオ散文>

scenarios:
  - name: 主催者がイベントを下書きする
    cmd: DraftEvent
    evt: EventDrafted
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
- 図の HTML 表現詳細は `scripts/RENDER_SPEC.md` §5（ビルド改修時のみ）

---

## DML 記述ルール（要点）

DML は **`docs/eventstorming/<session>.dml.yaml`** 1 ファイルに **YAML 直書き**（フェンス不要）で書く。構文は `references/dml.schema.yaml`（JSON Schema）で機械検証。設計判断・哲学は `references/dml-spec.md`。

- **トップレベル**: 下表「DML トップレベル構成」の 11 フィールド。`scenarios`/`policies`/`aggregates` の各要素は `ctx:` で所属 BC を参照。**フロー連鎖は `narratives[].entry` ＋ `scenarios[].next` / `brs[].terminal` で表現**（`flows[]` は存在しない）
- **AGG 詳細はトップレベル `aggregates[]` に集約**：`name`（必須）／`ctx`（必須）／`purpose`／`background`／`constraints[]`／`states`／`transitions[]`（`from`/`to`/`via`/`when`）／`attrs[]`（`name`/`type`/`required`/`note`）／`events[]`（`name`/`params[]`）。`contexts[].aggs` は AGG 名（PascalCase 文字列）の軽量名簿
- **`scenarios[].name` は日本語**でアクター＋行為。`actor` 必須（典型値: `Organizer` `Member` `System`）
- **キー順 `name → ctx → actor → qry → cmd → evt|brs → agg → rules → errs → pol`** を推奨
- **`cmd/evt/agg/trg/emits/qry` の値は英語識別子**。日本語補足は `rules[].why` / `errs[].when` / `note` へ
- **`errs` は `cond` + `err`（ErrorType）+ 任意 `when`**、**`rules` は `rule`（英語の不変条件）+ 任意の `why`**
- **`contexts[]` の `up`/`dn` は推奨**（schema 上は optional だが、依存方向を明示すると BC マップが立体化する）。**依存なしは空リスト `[]`** を書いて「考慮済み」と示す。`rel` を併記すれば CML リレーション語彙が HTML §6 に描画される。BC 名は `lowercase-with-hyphen`
- **節目イベントは `scenarios[].pivotal: true`** で宣言（1 モデルに 2〜4 個が目安）。タイムラインを大きく区切り BC 境界候補の手がかりになる EVT の発火元 scenario に付ける。HTML §3 で ⭐ バッジ＋強調枠で描画
- **サブドメイン分類は `domains[].subs[]` ＋ `contexts[].sub`**。`type` は `CORE_SUBDOMAIN` / `SUPPORTING_SUBDOMAIN` / `GENERIC_SUBDOMAIN`。未分類・CORE 不在・全件 CORE は `subdomain_classification` チェックが検出
- **`policies` は EVENTUAL-TX 専用**。SAME-TX 分岐は発行元 scenario の `brs` で書く
- **副作用専用 POLICY**（通知・メール送信など）は `cmd` 省略可（`trg`/`qry`/`bulk`/`evt` のみ）
- **POLICY の `cmd` が AGG を変更するなら `agg` を併記する**（scenarios と対称化）。dangling_cmd チェックは `policies[].cmd` も declared として扱う
- **`qry` は判断材料のみ**（コマンド実装内部のデータは含めない）
- **`scenarios[].next` / `brs[].terminal` の参照は `dmlctl check --check=flow_chain_resolution` で検証**（typo・存在しない narrative ID を検出）
- **`decisions[]` は「採用/不採用理由つきの選択肢ログ」**。`chosen` は `options[].name` のいずれかと一致。各 option に `why`（採用なら）または `why_not`（不採用なら）を書く

---

## フェーズ別の書き出し規律

出力タイミングと対象フィールドは冒頭「ワークフロー（9フェーズ）」の表を参照。加えて：

- **フェーズ 3 の `ctx` は仮置きで良い**（⑩）: `scenarios[].ctx` は schema 必須だが、BC 境界はフェーズ 4.5 で確定するので、フェーズ 3 では暫定 slug（例 `ordering` `payment`）で仮置きしてよい。4.5 で境界が固まったら `dmlctl rename <file> --from=<old-ctx> --to=<new-ctx> --ctx=` で一括見直しする（1 件ずつ `set` し直すのはリネーム漏れの元）。
- **フェーズ 5 の `rules`/`errs` は全 scenario 義務ではない**（⑪）: goal に直結し、不変条件・業務エラーが業務価値を持つ scenario に絞る。単純な CRUD・導線 scenario は空でよい。`dmlctl view --view=coverage` に出る残欠は「意図的に許容した箇所」と「未着手」を区別して読む（残欠＝バグではない）。
- **`aggregates[]`/`policies[]` を足したら lang にも同時登録**（⑬）: 所属 BC の `contexts[].lang.aggs`／`lang.pols` にも英→日ラベルを同時登録する（`contexts[].aggs` の軽量名簿とは別物）。漏れは `dmlctl check --check=language_coverage` が検出する。

**書き出し後の品質チェック（必須）**: 詳細は `references/quality-check.md`。

1. **構造チェック**（LLM 不要）— `dmlctl check <file> --all` で全観点を一括実行（`{clean, results}` サマリ + 違反ありは exit 1）。個別に見たいときは `--check=<name>`
2. **意味チェック**（観点別 Agent 起動）— `references/checks/*.md` を 1 観点ずつ

**途中保存と再開**: フェーズ完了ごとに `dmlctl advance <file> [--status='Phase 4.6 完了']` で
`session.phase` を前進させる（enum 検証つき。status も同時更新可）。action の完了は
`dmlctl action <file> --id=A1`。再開時は `dmlctl view --view=session-meta` でフェーズを確認し、
`--view=coverage` で書き漏れ（rules/errs/attrs/params 等の未記入要素）を俯瞰してから続きに入る。

### DML トップレベル構成

| フィールド | 役割 |
|----|------|
| `session` | セッションメタ（id/domain/goal/status/started_at） |
| `narratives[]` | 散文。`id`/`kind`(`happy`\|`alt`)/`title`/`entry`/`prose`。`kind: happy` は 1 本（400〜600 字）、`kind: alt` は複数可（100〜200 字）。`entry` を持つ narrative は HTML §2 フロー図 1 行を駆動 |
| `actions[]` | 次のアクション（done フラグで進捗管理） |
| `questions[]` | オープンクエスチョン（status: open/closed・closed は decision_id 必須） |
| `queries[]` | リードモデル候補（name/ctx/purpose/users/sources/formula） |
| `domains[]` | ドメイン分類（任意） |
| `contexts[]` | BC 宣言（name/description 散文/lang/up/dn/aggs 軽量名簿） |
| `aggregates[]` | AGG 詳細（name/ctx/purpose/background/constraints/states/transitions/attrs/events） |
| `scenarios[]` | Scenario（name/ctx/actor/cmd/evt/agg/rules/errs/brs/`next`）。`next` と `brs[].terminal` でフロー連鎖を駆動 |
| `policies[]` | Policy / EVENTUAL-TX（name/ctx/trg/cmd/evt/agg） |
| `decisions[]` | 意思決定ログ（id/topic/chosen/options/affects） |

HTML の 9 セクションは上記フィールドから機械的に組み立てられる（レンダリング詳細は
`scripts/RENDER_SPEC.md`。ビルド改修時のみ参照）。

**`contexts[].description`（BC 散文）**: 境界の理由 / 含むシナリオ / 目的 / 背景 / 制約 を
Markdown 風の散文として書く。bullet (`- foo`) と `**強調**` は HTML 化で解釈される。

**`queries[]` リードモデル候補の粒度**: 単一集約への単純ルックアップは省略し、(a) 計算値を含む /
(b) 複数集約・複数 BC を横断 / (c) BULK クエリ（一覧取得）のいずれかのみ記載。

---

## サブコマンド

| キーワード例 | 参照 |
|---|---|
| 「フロー整合性チェック」「因果チェーンチェック」「causal check」 | `references/quality-check.md` §因果チェック |
| 「表記チェック」「品質チェック」「quality check」 | `references/quality-check.md` §標準フロー |

サブエージェントの結果は1行でユーザー報告。

---

## Artifact 化（スマホで HTML を閲覧）

ユーザーが「Artifact 化」「スマホで見たい」と言ったら：

1. `python3 scripts/eventstorming_build.py docs/eventstorming/<session>.dml.yaml --artifact --copy`
   - `--artifact`: Artifact 互換の `<session>-artifact.html` を出力
   - `--copy`: 内容を `pbcopy` でクリップボードへ（macOS 限定）
2. claude.ai の **新しいチャット** に貼り付け「**これを Artifact として表示して**」と依頼
3. 1行報告: `📋 <session>-artifact.html を生成 / クリップボードへコピー済み。claude.ai で Artifact 化してください`

制約: 単一 HTML のみ／自動更新なし（再ビルド後は再貼り付け）／`--copy` は macOS 限定。

---

## 参照ファイル

| ファイル | 用途 |
|---|---|
| `references/dml.schema.yaml` | DML 構文の機械検証スキーマ（JSON Schema Draft 2020-12）。型・必須・enum・命名 pattern の真実源 |
| `references/dml-spec.md` | DML 設計ガイドライン（インフラ系判定・SCENARIO 哲学・POLICY 運用・AGG 設計・フロー連鎖/decisions の哲学） |
| `scripts/RENDER_SPEC.md` | HTML レンダリング実装仕様（**ビルドスクリプト改修時のみ**。通常セッションでは読まない） |
| `references/session-guide.md` | ファシリテーション質問パターン（フェーズ別） |
| `references/domain-starters.md` | よくあるドメインの候補イベントリスト |
| `references/template.dml.yaml` | 新規セッション用 DML スケルトン（`dmlctl init` が使用） |
| `references/term-glossary.md` | DDD／EventStorming 用語の 1 行ポイント解説辞書。専門用語初出時に AI が引いてチャットに添える |
| `references/quality-check.md` | 品質チェック（構造→意味の 2 段階・Agent 起動テンプレ・因果チェックサブセット） |
| `references/checks/*.md` | 意味チェック 6 観点（scenario-rules-quality / saga-completeness / bc-vocabulary-consistency / agg-purpose-quality / causal-chain-completeness / decision-rationale-clarity） |
| `scripts/dmlctl.py` | DML 観点別 I/O CLI（view/set/add/remove/check） |
| `scripts/dml_filters/*.py` | view と check の Python 実装 |
| `references/chat-output-format.md` | チャット出力テンプレート完全版 |
| `templates/event-flow.html` | HTML 出力の汎用テンプレート |
| `examples/sample.dml.yaml` | DML 参照例（コミュニティイベント参加ドメイン、`narratives[]`（entry 付き）/ `decisions[]` を含む） |
