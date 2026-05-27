# Event Flow HTML レンダリング仕様

EventStorming セッションの全情報を **CSS 付箋風 HTML** として書き出してブラウザでリッチに表示するための仕様。

**重要：AI は HTML を直接編集しない。** Python ビルダー（`.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py`）が `.md` ＋ 兄弟 `.dml.yaml` を解析して HTML を自動生成する。AI が編集するソース・オブ・トゥルースは `.md`（ストーリー/フロー/用語集）と兄弟 `.dml.yaml`（モデル本体）の 2 ファイル。

Claude Code の CLI/PC/スマホアプリではチャット本文の生 `<svg>` も Mermaid フェンスも描画されないため、別ファイル（HTML）として書き出してブラウザに任せる方針。

---

## 1. ファイル構成

| ファイル | 役割 |
|---|---|
| `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.md` | ストーリー / フロー DSL / 用語集の **Single Source of Truth**（§9 は `.dml.yaml` へのリンク参照のみ）。AI と人間がここを編集 |
| `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.dml.yaml` | DML（モデル本体）の **Single Source of Truth**。純 YAML 直書き（フェンス不要）。AI と人間がここを編集 |
| `dist/eventstorming/eventstorming-YYYYMMDD-HHMM.html` | Python ビルダーが `.md` ＋ 兄弟 `.dml.yaml` から自動生成する派生ファイル。AI も人間も直接編集しない |
| `.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` | MD → HTML 変換スクリプト（Python 3 標準ライブラリのみ） |
| `.claude/skills/eventstorming-facilitator/templates/event-flow.html` | テンプレート HTML（CSS とプレースホルダー入り） |

---

## 2. 自動再生成のフロー

```
.md または兄弟 .dml.yaml を Write/Edit (AI または人間)
  ↓
PostToolUse hook 起動 (.claude/settings.json)
  ↓
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <path>
  （.dml.yaml を渡された場合は兄弟 .md を解決。ビルダーは .md ＋ 兄弟 .dml.yaml を読む）
  ↓
dist/eventstorming/<session>.html 再生成
  ↓
ブラウザの meta-refresh (3秒) で自動再表示
```

PostToolUse hook の設定: `.claude/settings.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c '...' "
          }
        ]
      }
    ]
  }
}
```

hook 内で `tool_input.file_path` を判定し、`docs/eventstorming/*.{md,dml}` の場合のみビルドを実行する（正規表現 `docs/eventstorming/.+\.(md|dml)$`）。

---

## 3. ビルダーの CLI

```bash
# 個別ビルド
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py docs/eventstorming/eventstorming-20260514-2054.md

# 全件ビルド (docs/eventstorming/*.md すべて → dist/eventstorming/*.html)
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --all

# 監視モード（ファイル変更を検知して自動再ビルド）
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --watch

# 出力ディレクトリ変更
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <md> --out custom/dir/
```

---

## 4. HTML が含むセクション（MD と 1 対 1）

| # | セクション | HTML 表現 |
|---|---|---|
| 0 | 進捗バー | MD ヘッダーの `Status: フェーズN完了` を自動パースして `done`/`current` クラスを設定 |
| 1 | ハッピーパスストーリー | `.story` 黄背景の散文 |
| 2 | 代替シナリオ | `.scenario-card` カード（複数） |
| 3 | Event Walkthrough | `.flow > .grid` Big Picture 形式（§5 参照） |
| 4 | コンテキスト候補 | `.bc-card` ＋ **コンテキストマップ SVG**（自動生成、UPSTREAM/DOWNSTREAM から） |
| 5 | 集約候補 | `.bc-card` ＋ `pre.code` で **Zod スキーマシンタックスハイライト** ＋ **エラーケースは `.err-section` で赤背景**、バックティックで囲んだエラー識別子は `.err-code` でハイライト |
| 6 | リードモデル候補 | `.bc-card`（緑左ボーダー） |
| 7 | オープンクエスチョン / ホットスポット | `.question`（青）`.hotspot`（赤）、`[CLOSED]` は緑背景 |
| 8 | 次のアクション | `.next-actions` 緑カード |
| 9 | DML（YAML） | `pre.code` ダークテーマ + 役割ベース意味色ハイライト（キー `.yk`、値 `.v-actor`/`.v-cmd`/`.v-evt`/`.v-qry`/`.v-pol`/`.v-err`/`.v-str`、コメント `.cm`） |
| 10 | 用語集 | `table.glossary` カテゴリ別テーブル |

未完成セクションは MD で `<!-- TODO: フェーズN完了後に追記 -->` プレースホルダー → HTML 側で `.todo-placeholder` に変換。

---

## 5. Event Flow グリッド（Big Picture 形式）

### 5-1. レイアウト原則

- **時系列 = 横軸（列）**、**BC = 縦軸（行）**
- 同じ BC が複数回出現しても **同じ行に統合** する
- 矢印は **CSS 描画**（`<div>` の塗り + 三角形）で付箋同士を視覚的に繋ぐ
- 横幅が画面を超える場合は **`overflow-x: auto`** で横スクロール

### 5-2. ビルダーの DSL → HTML 変換ロジック

`.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` の `render_flow()` 関数が以下を行う：

1. フロー DSL（` ```event-flow-svg ` フェンス内）をライン単位でパース
2. `|BC名|: 説明` を Lane オブジェクトに、`@! $? [...]` を Note オブジェクトに変換
3. 同じ BC を 1 grid-row に統合
4. 時系列順に grid-column を連番付与
5. レーン間遷移（`>>` の検出）を `.arrow-v down/up` として 2 行を跨ぐ縦矢印で描画
6. 同レーン内遷移を `.arrow-h` 横矢印で描画
7. **BULK fanout (`*>`)**: 後続 Note に `is_fanout=True` を付与 → `.note.fanout` クラスで 3 枚スタック + `× N` バッジ描画。fanout 入口の同期矢印は `.arrow-h.fork`（1 → 3 分岐）で描画
8. **Join 遷移 (`&>>`)**: 行末 Lane の `joins_into_next=True` を検出 → 次レーン遷移時に `.arrow-v` の代わりに `.sync-bar`（BPMN 風シンクバー）+ `Σ N` ラベルを描画

### 5-3. 付箋ラベルのルール

**DSL 記号（`@` `!` `$` `[` `]` `?`）は HTML 表示時にビルダーが自動削除する。** 種別は `<span class="kind">` のラベル（Actor/Command/Event/Policy/Read Model）と背景色で識別。

| DSL | HTML 表示 |
|---|---|
| `@客` | 客 |
| `!注文する` | 注文する |
| `[注文が入った]` | 注文が入った |
| `$調理開始` | 調理開始 |
| `?残席数` | 残席数 |

---

## 6. 色とフォント

### 6-1. 付箋色

| 種別 | DSL 記号 | クラス | fill | border | text |
|---|---|---|---|---|---|
| Actor | `@` | `.note.actor` | `#FFF59D` | `#F9A825` | `#4E342E` |
| Command | `!` | `.note.command` | `#90CAF9` | `#1565C0` | `#0D47A1` |
| Event | `[...]` | `.note.event` | `#FFAB40` | `#E65100` | `#7f2700` |
| Policy | `$` | `.note.policy` | `#CE93D8` | `#7B1FA2` | `#4A148C` |
| Read Model | `?` | `.note.readmodel` | `#A5D6A7` | `#2E7D32` | `#1B5E20` |

### 6-2. レーン色

```
.lane-name.bc-default-1 → #37474F
.lane-name.bc-default-2 → #455A64
.lane-name.bc-default-3 → #546E7A
.lane-name.bc-default-4 → #607D8B
.lane-name.bc-default-5 → #78909C
```

BC ごとに異なるグレートーン。最大 5 BC まで標準パレット、それを超える場合はループ。

### 6-3. 矢印色

| 種類 | 色 | 形状 |
|---|---|---|
| 同期 `→`（同レーン） | `#546E7A` | 横線 + 右向き三角 |
| 非同期 `⚡↓ / ⚡↑`（レーン跨ぎ） | `#7B1FA2` | 縦線 + 三角、`async-label` 表示 |
| BULK Fork `*>` | `#7B1FA2` | 単線 → 3 本に分岐（`.arrow-h.fork`） |
| Join シンクバー `&>>` | `#263238` | 黒太線 + Σ N ラベル（BPMN sync bar） |

### 6-3.2. Fanout (`.note.fanout`) 視覚仕様

BULK POLICY 由来の `*>` 直後 Note に付くクラス。

| 要素 | 表現 |
|---|---|
| 本体 | 通常 Note と同じ色（`.note.command` 等）。`box-shadow` で背後 2 枚のカードを `#FFF` 抜き + 種別 border 色で重ねる |
| オフセット | 右下 +4px, +8px（2 段スタック） |
| バッジ | 右上 `× N`（`#F3E5F5` 背景 / `#7B1FA2` 文字、`::after` で生成） |
| マージン | `margin-right: 14px; margin-bottom: 14px;` でスタック分の余白確保 |

### 6-3.3. Sync Bar (`.sync-bar`) 視覚仕様

`&>>` 後段に挿入される BPMN 風 Join バー。

| 要素 | 表現 |
|---|---|
| バー本体 | 縦 6px 幅 × 高さ可変の `#263238` 黒太線 |
| 矢印 | `down` または `up` で 10px の三角（バーの先端） |
| ラベル | バー中央に `Σ N` 文字（`#ECEFF1` 背景 / `#263238` 文字） |
| 配置 | `align-self: stretch` で行をまたぎ、上下バー両端は `top/bottom: 8px` で内側に少し収める |

### 6-3.1. 不変条件・エラーケース色（対比表示）

集約 §5 のサブセクションは意味別に色分けする：

| サブセクション | クラス | 背景 | 左ボーダー | ラベル色 | 絵文字 |
|---|---|---|---|---|---|
| **目的** | `.purpose-section` | `#FFF3E0` | `#EF6C00` | `#EF6C00` | — |
| **背景** | `.background-section` | `#E3F2FD` | `#1565C0` | `#1565C0` | — |
| **制約** | `.constraints-section` | `#F3E5F5` | `#6A1B9A` | `#6A1B9A` | — |
| **不変条件** | `.inv-section` | `#E8F5E9` | `#2E7D32` | `#2E7D32` | `✓` |
| **エラーケース** | `.err-section` | `#FFEBEE` | `#C62828` | `#C62828` | `⚠` |
| その他（状態遷移・派生イベント・備考） | inline style | — | — | `#37474F` | なし |

**読み順:** AGG / BC カード内では `目的 → 背景 → 制約 → Zod → 不変条件 → エラーケース → 状態遷移 → 派生イベント → 備考` の順に並ぶ。読み手はまず「なぜこの単位で切るか（目的・背景・制約）」を把握してから、形式仕様（Zod・不変条件・エラー）に進む。

エラーケース内のバックティック識別子は **`.err-code`** で更にハイライト：
- background `#FFCDD2` / text `#B71C1C` / 等幅フォント

MD 記法例（不変条件は箇条書きのみ、エラーケースは識別子をバックティックで囲む）：

```markdown
#### 不変条件
- items は 1 品以上
- status が `PAID` 以降は items / totalAmount を変更不可

#### エラーケース
- `AmountMismatch`: Payment.amount ≠ Order.totalAmount
- `EmptyOrder`: items が空のまま PlaceOrder が呼ばれた
```

### 6-4. フォントサイズ（基準）

| 要素 | サイズ |
|---|---|
| h1 タイトル | 26px |
| h2 セクション見出し | 18px |
| 付箋本体 | 14px |
| 種別ラベル (kind) | 10px |
| レーン名 | 13px |
| 凡例の小付箋 | 12px |
| 非同期ラベル | 11px |
| ストーリー / カード本文 | 14-15px |
| ホットスポット / 質問カード | 15px |
| DML コードブロック | 14px |
| 用語集テーブル | 15px |

---

## 7. 自動オープン

### 7-1. フェーズ2完了時のみ初回オープン

MD を Write した直後、PostToolUse hook が HTML を生成するので、AI は続けて `Bash open dist/eventstorming/<session>.html` を実行して外部ブラウザを起動する。

### 7-2. 自動リロード（2 系統）

| 機構 | 対象 | 動作 |
|---|---|---|
| **`<meta http-equiv="refresh" content="3">`** | 外部ブラウザ | 3 秒ごとに自身を再読み込み |
| **`reload_browser_tab()` (osascript)** | macOS Chrome / Safari | ビルダーが HTML 生成後に該当タブを即座に reload。MD 編集とほぼ同時にブラウザ反映 |

両方が併用されることで、外部ブラウザは常に最新版を表示する。

### 7-3. Claude Code Launch preview panel

Claude Code（CLI/PC/スマホアプリ）の preview panel は **JavaScript / `<meta http-equiv="refresh">` を実行しない** スナップショット表示。AI が `Read dist/eventstorming/<session>.html` を呼んだ瞬間に最新版が表示される。

→ **フェーズ完了テンプレの末尾で必ず `Read` を呼ぶこと**（`chat-output-format.md` §3 参照）。

### 7-4. スマホ環境

スマホアプリでは Files / Safari で `dist/eventstorming/*.html` を開く。`Bash open` も `osascript` も効かないので、AI は「HTMLファイルを開いてください」と案内する。meta-refresh は機能する。

---

## 8. ビルダーの内部構造

`.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` は単一ファイル、Python 3 標準ライブラリのみで実装。主要関数：

```
parse_md(md_text) → MDSections     # MD を §1〜§10 に分割
parse_flow_dsl(dsl) → Flow         # event-flow-svg フェンス → Flow AST
render_flow(flow) → HTML 文字列    # Flow → Big Picture グリッド HTML
render_progress(status) → HTML     # Status 行から進捗バー
render_context_map(bc_cards) → SVG # UPSTREAM/DOWNSTREAM から関係図 SVG
highlight_dml(dml) → HTML          # DML（YAML）役割ベース意味色ハイライト
highlight_zod(zod) → HTML          # Zod スキーマシンタックスハイライト
render_html(sections) → HTML 全文  # テンプレに埋め込んで完成版を返す
build(md_path, out_dir) → Path     # 1 ファイルビルド → reload_browser_tab() 呼び出し込み
reload_browser_tab(html_path)      # macOS Chrome/Safari の該当タブを osascript で reload
build_all(in_dir, out_dir)         # 全件ビルド
watch(in_dir, out_dir)             # 監視モード
```

依存: `re`, `pathlib`, `argparse`, `dataclasses`, `time`, `sys`, `subprocess`（hook 内のみ）。外部パッケージなし。

---

## 9. フォールバック

書き込み権限がない、Python 3 が無い等の環境では、ビルダーが動かない。その場合：

1. ビルダーの実行ログ（stderr）を確認
2. 手動で `python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <md>` を実行
3. 解決不可ならチャット本文に **構造化テーブル** で代替表示（`chat-output-format.md` §9 参照）

---

## 10. DSL → HTML 変換ルール（要約）

```
event-flow-svg DSL              →   HTML
─────────────────────────────────────────────────────────
title: <タイトル>                →   <div class="flow-title">{タイトル}</div>
|BC名|: <説明>                   →   <div class="lane-name bc-default-N">{BC名}</div>
@アクター                        →   <div class="note actor"><span class="kind">Actor</span>{ラベル}</div>
!コマンド                        →   <div class="note command"><span class="kind">Command</span>{ラベル}</div>
[イベント]                       →   <div class="note event"><span class="kind">Event</span>{ラベル}</div>  ※[]削除
$ポリシー                        →   <div class="note policy"><span class="kind">Policy</span>{ラベル}</div>
?リードモデル                    →   <div class="note readmodel"><span class="kind">Read Model</span>{ラベル}</div>
>                                →   <div class="arrow-h"></div>
>> (同BC内)                      →   <div class="arrow-h"></div> + 列インクリメント
>> (BC跨ぎ)                      →   <div class="arrow-v down/up" style="grid-row: A / B;">⚡ async</div>
```

時系列ステップ（grid-column）は付箋・矢印のたびに +1。同じ BC が複数回登場する場合も同じ grid-row に配置する。
