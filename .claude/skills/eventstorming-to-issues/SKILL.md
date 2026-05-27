---
name: eventstorming-to-issues
description: EventStorming のモデリング結果 (docs/eventstorming/*.md) から GitHub Issue 一覧を作るとき。BC を大項目、集約を中項目とし、1 AGG = 1 self-contained Epic = 1 PR を AI エージェントに丸ごと任せる粒度で起票プランを出す。CMD/QRY/受信 POLICY の詳細は Epic 本文に inline。「DDDセッション結果をIssueにしたい」「ドメインモデルを起票したい」「イベントストーミングからチケット切りたい」「集約単位で AI エージェントに任せたい」と言われたときに必ず使う。
---

# EventStorming → GitHub Issue 化

EventStorming セッション成果物 (`docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md`) を入力に、**集約を単位とした self-contained Epic** + **AGG 跨ぎ統合 Issue** を生成する。Epic は CMD / QRY / 受信 POLICY / 発信 EVT の詳細を inline で持ち、1 つ読めば AI エージェントが PR を書けるよう設計する。

## 設計の核心 — 1 AGG = 1 PR

| 単位 | 表現 | 役割 |
|---|---|---|
| 境界づけられたコンテキスト (BC) | Label `bc:xxx`（**大項目**） | チーム / 担当範囲の分類 |
| 集約 (AGG) | Label `agg:Xxx` + **AGG Epic Issue**（**中項目**） | **トランザクション境界 = オーナーシップ = 1 PR = AI 1 担当** |
| CMD / QRY | AGG Epic 本文に **inline** 記述 | 詳細スキーマ・RULE・ERR・EVT を Epic 内に集約 |
| 受信 POLICY | AGG Epic 本文に **inline**（CMD 所属 AGG に紐付け） | 他 AGG / BC からの非同期入力。cross-BC は明示マーキング |
| 発信 EVT | AGG Epic 本文に **inline**（EVT 発火元 AGG に紐付け） | 下流 POLICY 消費先をトレース |
| AGG 跨ぎ SCENARIO | **統合 Issue**（独立） | 複数 AGG を跨ぐ E2E フロー |
| Cross-BC Saga | 独立 Issue + `cross-bc` ラベル | BC 境界を越える連鎖の単一窓口 |

「**1 AGG Epic = 1 PR = AI エージェント 1 担当**」を実現する単位。CMD/QRY 単位の Sub-issue は廃止（DML パーサが CMD レベル詳細を持たないため、Sub-issue 単位で投げても情報不足になりがちで、Epic を再読することになる）。

### Step 1: 入力 MD を特定
- 引数指定があればそれ
- なければ `docs/eventstorming/eventstorming-*.md` のうちタイムスタンプ最新のもの

### Step 2: パース
```bash
python3 .claude/skills/eventstorming-to-issues/scripts/parse_eventstorming_md.py \
  <md_path> > /tmp/es-parsed.json
```
- BC / AGG / SCENARIO / QRY / フロー / 状態遷移を JSON 化
- DML（YAML）の policies / scenarios も抽出し `policies` / `dml_scenarios` キーに格納
- MD セクション抽出は `eventstorming-facilitator/scripts/eventstorming_build.py` の `parse_md()` を再利用。DML（YAML）は **`<md_path>` の兄弟ファイル `<session>.dml.yaml`（純 YAML）から読む**（無ければ旧来の `.md` §9 埋め込み ` ```dml ` フェンスにフォールバック）。`yaml.safe_load` でパースして既存の dict 構造へ正規化（`parse_dml_blocks`）

### Step 3: 依存グラフ構築 + Mermaid 生成
```bash
python3 .claude/skills/eventstorming-to-issues/scripts/build_dependency_graph.py \
  /tmp/es-parsed.json > docs/issues/<session-id>/dependency-graph.md
```
- BC UPSTREAM/DOWNSTREAM を Mermaid graph に
- 集約ごとの状態遷移図 (stateDiagram-v2) を個別生成

### Step 4: Issue MD ドラフト生成
```bash
python3 .claude/skills/eventstorming-to-issues/scripts/generate_issue_drafts.py \
  /tmp/es-parsed.json --output docs/issues/<session-id>/
```
出力ファイル（AGG 単位 + 統合 Issue のみ。Sub-issue は廃止）:
- `epics/<bc>__<AGG>.md`: **AGG Epic（self-contained）**。**ビジネス背景と制約（目的・背景・制約 + BC 共通の方針）**・Zod スキーマ・不変条件（rule）・エラー（error）・状態遷移・CMD/QRY 詳細（`rules[].why` / `errors[].when` を併記）・受信 POLICY・発信 EVT・受け入れ条件・モジュール構造提案を 1 ファイルに集約
- `integration/<scenario>.md`: AGG 跨ぎ統合 SCENARIO
- `cross-bc/<saga>.md`: Cross-BC Saga（現状未実装、将来拡張）
- `_index.md`: BC（大項目）× AGG（中項目）ナビ
- `_labels.md`: 必要なラベル一覧（`bc:` / `agg:` / `type:aggregate` / `type:scenario` / `type:saga` / `cross-bc`）
- `_state.json`: es-key → issue 番号マップ（初期は空）

未解決 POLICY（CMD/TRIGGER EVT が AGG に紐付かない）がある場合は stderr に warning + `_index.md` 末尾に列挙される。

### Step 5: ユーザー確認
ドラフトをレビューしてもらう。必要なら直接 MD を編集してから次のステップへ。

### Step 6: 冪等起票
```bash
python3 .claude/skills/eventstorming-to-issues/scripts/create_issues.py \
  docs/issues/<session-id>/ [--dry-run] [--repo owner/repo]
```
- 必要 Label を `gh label create` で冪等作成
- 各 MD ファイルの先頭 HTML コメント `<!-- es-key: ... -->` で既存検索
  - なければ `gh issue create --body-file ...`
  - あれば `gh issue edit --body-file ...`（タイトルは変更しない）
- 起票対象は **AGG Epic / 統合 SCENARIO / Cross-BC Saga のみ**（Sub-issue 連結 `addSubIssue` は廃止）
- レート制限回避のため 1-2 秒スリープ
- `_state.json` に es-key → issue 番号を記録

## 重要な規約

すべての詳細は references/ を参照:

- **ラベル命名規則**: `references/label-conventions.md`
  - 3 系統: `bc:` / `agg:` / `type:`（`aggregate` / `scenario` / `saga`）+ 特殊 `cross-bc`
- **es-key 安定キー仕様**: `references/es-key-spec.md`
  - 形式: `bc/<bc-slug>/agg/<AggName>` (Epic) または `bc/<bcs>/scenario/<name>` (統合)
  - HTML コメント `<!-- es-key: ... -->` を本文先頭に必ず埋め込む
- **依存判定ルール**: `references/dependency-rules.md`
  - AGG 跨ぎ SCENARIO の判定、POLICY ルーティング規則
- **Issue 本文テンプレート**: `references/issue-templates.md`
  - AGG Epic（self-contained）/ 統合 SCENARIO / Saga
- **gh CLI レシピ**: `references/gh-cli-recipes.md`
  - Label / Issue / 重複検出

## タイトル規約

すべての Issue タイトル先頭に **`[bc:<...>][agg:<...>]`** を付ける。集約スコープでの即時識別のため。

| 種別 | 例 |
|---|---|
| AGG Epic | `[bc:event-planning][agg:Event] Event 集約（イベント）` |
| 統合 SCENARIO | `[bc:registration+payment][agg:Application+Payment] 申込み確定` |
| Saga | `[bc:registration→payment] 申込支払 Saga` |

CMD/QRY/POLICY は Epic 内のセクションタイトルで識別する（個別 Issue は作らない）。

## 出力先

```
docs/issues/<session-id>/
├── _index.md
├── _state.json
├── _labels.md
├── dependency-graph.md
├── epics/             — AGG Epic (1 AGG = 1 ファイル = 1 PR)
├── integration/       — AGG 跨ぎ統合 SCENARIO
└── cross-bc/          — Cross-BC Saga (将来拡張)
```

`<session-id>` は入力 MD のファイル名から `eventstorming-` を除いた部分（例: `20260515-1901`）。

## Mermaid プレビューのトラブルシュート

`dependency-graph.md` および `epics/*.md` の状態遷移セクションは Mermaid (`graph LR` / `stateDiagram-v2`) で記述される。VS Code でレンダリングするには `bierner.markdown-mermaid` 拡張が必要（リポジトリの `.vscode/extensions.json` で推奨済み）。

拡張導入済みでも Markdown Preview でコードブロックのまま表示される場合の診断手順:

1. **最小再現** — `/tmp/mermaid-test.md` に Mermaid フェンスと `graph TD\nA-->B` だけを書いて Cmd+Shift+V でプレビュー。これがレンダリングされなければ拡張側の問題。
2. **プレビュー Security** — Cmd+Shift+P → `Markdown: Change Preview Security Settings` → `Allow insecure content`（ワークスペース単位で記憶）。
3. **拡張リロード** — Cmd+Shift+P → `Developer: Reload Window`。拡張機能パネルで `bierner.markdown-mermaid` が Workspace 側で無効化されていないかも確認。
4. **競合拡張** — `Markdown Preview Enhanced` / `Markdown All in One` / `Markdown Editor` 等が独自プレビューを開いていないか確認。標準の `Markdown: Open Preview` で開く。
5. **派生エディタ** — `which code` で Cursor 等の派生を起動していないか確認。Mermaid 拡張は VS Code 公式版が最も安定。

ラベル側の予防策は `scripts/build_dependency_graph.py` の `sanitize_mermaid_label()` で実装済み。`+` 等の特殊文字はスペースに置換される。
