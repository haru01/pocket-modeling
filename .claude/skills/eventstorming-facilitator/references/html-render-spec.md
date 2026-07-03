# Event Flow HTML レンダリング仕様

EventStorming セッションの全情報を **CSS 付箋風 HTML** として書き出してブラウザでリッチに表示するための仕様。

**重要：AI は HTML を直接編集しない。** Python ビルダー（`.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py`）が **`.dml.yaml` 1 ファイル** を解析して HTML を自動生成する（v5 で `.md` パース廃止、v8 で `story:` を `narratives[]` に統合）。AI が編集するソース・オブ・トゥルースは `.dml.yaml`（モデル本体＋散文系フィールド `narratives`/`actions`/`questions`/`queries`/`contexts[].description` の唯一の真実源）。

Claude Code の CLI/PC/スマホアプリではチャット本文の生 `<svg>` も Mermaid フェンスも描画されないため、別ファイル（HTML）として書き出してブラウザに任せる方針。

---

## 1. ファイル構成

| ファイル | 役割 |
|---|---|
| `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.dml.yaml` | **DML（モデル本体）の唯一の真実源**。純 YAML 直書き（フェンス不要）。散文系（`narratives` / `actions` / `questions` / `queries` / `contexts[].description`）も全てここに統合（v5 で `.md` 廃止）。AI と人間がここを編集 |
| `dist/eventstorming/eventstorming-YYYYMMDD-HHMM.html` | Python ビルダーが `.dml.yaml` 単独から自動生成する派生ファイル。AI も人間も直接編集しない |
| `.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` | DML → HTML 変換スクリプト（Python 3 標準ライブラリ + PyYAML） |
| `.claude/skills/eventstorming-facilitator/templates/event-flow.html` | テンプレート HTML（CSS とプレースホルダー入り） |

---

## 2. 自動再生成のフロー

```
.dml.yaml を Write/Edit (AI または人間)
  ↓
PostToolUse hook 起動 (.claude/settings.json)
  ↓
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <path>
  + python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py <path>
  ↓
dist/eventstorming/<session>.html 再生成 (+ JSON Schema 検証)
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

hook 内で `tool_input.file_path` を判定し、`docs/eventstorming/*.dml.yaml` の場合のみビルド＋検証を実行する。

---

## 3. ビルダーの CLI

```bash
# 個別ビルド
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py docs/eventstorming/eventstorming-20260529-1254.dml.yaml

# 全件ビルド (docs/eventstorming/*.dml.yaml すべて → dist/eventstorming/*.html)
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --all

# 監視モード（ファイル変更を検知して自動再ビルド）
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --watch

# 出力ディレクトリ変更
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <yaml> --out custom/dir/

# Artifact 化（claude.ai に貼る用、macOS のみクリップボード）
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <yaml> --artifact --copy
```

---

## 4. HTML が含むセクション

§0 進捗バー（ヘッダ）＋ §1〜§9 の **9 セクション** で構成される。v8 で旧 §1 ハッピーパスストーリーと §2 代替シナリオが §1 ストーリーに統合された。

| # | セクション | 駆動データ | HTML 表現 |
|---|---|---|---|
| 0 | 進捗バー（ヘッダ） | DML `session.phase` / `session.status` | `フェーズN完了` を自動パースして `done`/`current` クラスを設定 |
| 1 | ストーリー | DML `narratives[]`（v8 で `story:` 廃止して統合） | `kind:happy` を先頭に `.story` 黄背景、`kind:alt` を後続に `.scenario-card` カードで描画 |
| 2 | Event Walkthrough | **DML** `narratives[].entry` + `scenarios[]`（next/brs.terminal） + `policies[]` | `.flow > .grid` Big Picture 形式（§5 参照） |
| 3 | 次のアクション | DML `actions[]` | `.next-actions` 緑カード。**読者の次の動きを最上部近くに置く** |
| 4 | オープンクエスチョン / ホットスポット | DML `questions[]` | `.question`（青）`.hotspot`（赤）、`[CLOSED]` は緑背景 |
| 5 | 意思決定ログ | **DML** `decisions[]` | `.decision-card`：採用（緑 `.opt.adopted`）／不採用（灰・取り消し線 `.opt.rejected`）の比較カード。`decisions[]` が空なら **見出しごと非表示** |
| 6 | コンテキスト候補 | **DML** `contexts[]`（description / LANGUAGE / 依存方向） | `.bc-card` ＋ **コンテキストマップ SVG**。LANGUAGE と UPSTREAM/DOWNSTREAM は DML `contexts[].lang` / `up` / `dn` から merge して描画 |
| 7 | 集約候補 | **DML** `aggregates[]` + 該当 `scenarios[].rules/errs` | `.bc-card` ＋ **属性表 `.attr-table` / イベントペイロード表 `.payload-table` / 不変条件 `.inv-section`（緑）/ エラーケース `.err-section`（赤）/ 状態遷移** |
| 8 | リードモデル候補 | DML `queries[]` | `.bc-card`（緑左ボーダー） |
| 9 | DML（YAML） | `.dml.yaml` 生 | `pre.code` ダークテーマ + 役割ベース意味色ハイライト |

未完成セクションは DML 側で対応するトップレベルフィールドを未記述にすると、HTML 側で `.todo-placeholder`（または見出しごと非表示、`decisions[]` 等）として縮退表示される。

---

## 5. Event Flow グリッド（Big Picture 形式）

### 5-0. DML から HTML を組み立てるアルゴリズム（v6）

ビルダー `build_flows_from_dml(model, glossary_index)` が `.dml.yaml` の `narratives[].entry` を起点に `scenarios[].next` を辿り、`policies[]` を `scenarios[].evt → policies[].trg` のマッチで自動挿入して Lane / Note 構造を組み立てる。

1. `narratives[]` の各エントリで `entry` が指定されたものを 1 グリッド図として描画
2. フロー連鎖の解釈：
   - 開始: `narratives[].entry` の scenario.name から
   - 継続: scenarios[].next（string → 全フロー共通／dict → `narratives[].id` キーで分岐）
   - 終端: `next` 無し、または `brs[].terminal` が当該 `narratives[].id` と一致した時
3. 各 scenario ステップの描画：
   - actor / qry / cmd / evt から `Note` 群を生成（`ctx` は `scenarios[].ctx`）
   - `brs[]` がある場合は **「このフローでアクティブな brs」を 1 つだけ選ぶ**：`terminal == flow_id` 一致 > `terminal` 無し > 先頭
4. policy 自動挿入（scenarios[].evt → policies[].trg マッチ）：
   - マッチした policy を新規 Lane として挿入。`policy.evt` が後続 policy.trg にマッチすれば再帰的に追加
   - **policy ステップは常に EVENTUAL-TX 境界**として、前 Lane 末尾 Note を `is_async=True` にマーク
5. レーン併合：
   - 同一 `ctx` の連続 sync ステップ → 既存 Lane に Note を連結
   - `ctx` が変化、または policy ステップ → **新規 Lane を作成**し、前 Lane 末尾の Note を `is_async=True` でマーク（非同期遷移矢印 `⚡` を描画）
6. 特殊描画：
   - POLICY が `trgs`（複数トリガー join）を持つ → 前 Lane の `joins_into_next=True` を立て、レーン遷移時に **BPMN シンクバー（`.sync-bar` + Σ N）** を描画
   - POLICY の `bulk: true` → 該当 Note を `.note.fanout` クラスで描画し、右上 `× N` バッジ + 3 枚スタック
   - `scenarios[].pivotal: true` の EVT（evt / brs[].evt。policy.evt が同名の場合も含む） → 該当 Note を **`.note.pivotal`** クラスで描画し、左上 `⭐ 節目` バッジ + 強調枠（節目イベント）
7. 同じ BC が複数回出現しても **同じ grid-row に統合**
8. 横幅が画面を超える場合は **`overflow-x: auto`** で横スクロール

### 5-1. レイアウト原則

- **時系列 = 横軸（列）**、**BC = 縦軸（行）**
- 矢印は **CSS 描画**（`<div>` の塗り + 三角形）で付箋同士を視覚的に繋ぐ
- ラベル日本語化方針: ビルダーは DML の英語識別子を glossary_index で日本語ラベルに変換して表示する。glossary_index は **DML `contexts[].lang` を全 BC 走査して機械的に生成**（HTML §4 用語集セクションは廃止済み・MD 側にも辞書テーブルは持たない）。識別子は英語のまま DML/HTML に保持される

### 5-2. 付箋ラベル

種別は `<span class="kind">` のラベル（Actor / Command / Event / Policy / Read Model）と背景色で識別。テキストは **DML の英語識別子 → `contexts[].lang` 起源の glossary_index で日本語化**。

| DML フィールド | HTML 種別 | 種別ラベル |
|---|---|---|
| `scenarios[].actor` | `.note.actor` | Actor |
| `scenarios[].cmd`, `policies[].cmd` | `.note.command` | Command |
| `scenarios[].evt`, `policies[].evt`, `scenarios[].brs[].evt` | `.note.event` | Event |
| `policies[].name` | `.note.policy` | Policy |
| `scenarios[].qry`, `policies[].qry` | `.note.readmodel` | Read Model |

---

## 6. 色とフォント

### 6-1. 付箋色

| 種別 | クラス | fill | border | text |
|---|---|---|---|---|
| Actor | `.note.actor` | `#FFF59D` | `#F9A825` | `#4E342E` |
| Command | `.note.command` | `#90CAF9` | `#1565C0` | `#0D47A1` |
| Event | `.note.event` | `#FFAB40` | `#E65100` | `#7f2700` |
| Policy | `.note.policy` | `#CE93D8` | `#7B1FA2` | `#4A148C` |
| Read Model | `.note.readmodel` | `#A5D6A7` | `#2E7D32` | `#1B5E20` |

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
| BULK Fanout（`bulk: true`） | `#7B1FA2` | 単線 → 3 本に分岐（`.arrow-h.fork`） |
| Join シンクバー（`trgs` join） | `#263238` | 黒太線 + Σ N ラベル（BPMN sync bar） |

### 6-3.2. Fanout (`.note.fanout`) 視覚仕様

BULK POLICY 由来の Note に付くクラス。

| 要素 | 表現 |
|---|---|
| 本体 | 通常 Note と同じ色（`.note.command` 等）。`box-shadow` で背後 2 枚のカードを `#FFF` 抜き + 種別 border 色で重ねる |
| オフセット | 右下 +4px, +8px（2 段スタック） |
| バッジ | 右上 `× N`（`#F3E5F5` 背景 / `#7B1FA2` 文字、`::after` で生成） |
| マージン | `margin-right: 14px; margin-bottom: 14px;` でスタック分の余白確保 |

### 6-3.3. Sync Bar (`.sync-bar`) 視覚仕様

`trgs` join 後段に挿入される BPMN 風 Join バー。

| 要素 | 表現 |
|---|---|
| バー本体 | 縦 6px 幅 × 高さ可変の `#263238` 黒太線 |
| 矢印 | `down` または `up` で 10px の三角（バーの先端） |
| ラベル | バー中央に `Σ N` 文字（`#ECEFF1` 背景 / `#263238` 文字） |
| 配置 | `align-self: stretch` で行をまたぎ、上下バー両端は `top/bottom: 8px` で内側に少し収める |

### 6-3.1. 集約カードのサブセクション色（対比表示）

集約 §7 のサブセクションは意味別に色分けする。**§6-1 の付箋色と同じ Material シェードを再利用** することで、目的=Event 橙系・背景=Command 青系・制約=Policy 紫系・不変条件=ReadModel 緑系・エラーケース=赤系という対応を視覚化する：

| サブセクション | クラス | 背景 | 左ボーダー | ラベル色 | 絵文字 |
|---|---|---|---|---|---|
| **目的** | `.purpose-section` | `#FFF3E0` | `#E65100` | `#E65100` | — |
| **背景** | `.background-section` | `#E3F2FD` | `#1565C0` | `#1565C0` | — |
| **制約** | `.constraints-section` | `#F3E5F5` | `#7B1FA2` | `#7B1FA2` | — |
| **不変条件** | `.inv-section` | `#E8F5E9` | `#2E7D32` | `#2E7D32` | `✓` |
| **エラーケース** | `.err-section` | `#FFEBEE` | `#C62828` | `#C62828` | `⚠` |
| その他（状態遷移・派生イベント・備考） | inline style | — | — | `#37474F` | なし |

**読み順:** AGG カード内では `目的 → 背景 → 制約 → 属性 → イベントペイロード → 不変条件 → エラーケース → 状態遷移 → 備考` の順に並ぶ。

エラーケース内のバックティック識別子は **`.err-code`** で更にハイライト：
- background `#FFCDD2` / text `#B71C1C` / 等幅フォント

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

---

## 6-5. 集約 属性・イベントペイロード表

`render_agg_cards_from_dml()` は `aggregates[].attrs[]` / `aggregates[].events[].params[]` を以下の構造で描画する。

### 属性表 `table.attr-table`

`aggregates[].attrs[]` を **属性名 / 型 / 必須 / 備考** の 4 列テーブルで描画：

| クラス | 用途 |
|---|---|
| `table.attr-table` | 属性表本体（薄い影付き角丸） |
| `table.attr-table th` | ヘッダ行（淡い背景、左寄せ） |
| `table.attr-table td.code-cell` | 識別子セル（等幅フォント、薄い背景） |

`attrs[].required: true` は **`必須`** 文字、`false` または省略は空セル。

### イベントペイロード表 `table.attr-table.payload-table`

`aggregates[].events[]` を集約 emit する EVT の宣言として描画。EVT ごとに名前見出し（橙系 `.agg-events > strong`）＋`params[]` を `table.attr-table.payload-table` クラスで属性表と同じ構造のテーブルとして描画する。

| クラス | 違い |
|---|---|
| `.payload-table th` | ヘッダ背景が `#FFF3E0`（橙系）/ 文字 `#E65100` |
| `.agg-events` | EVT 群の囲い |
| `.agg-events > strong` | EVT 名見出し（`#E65100`） |

`params[]` が無い EVT は名前のみ表示（パラメータなしの宣言として扱う）。

---

## 6-6. 意思決定ログ `.decision-card`

`render_decisions(model, glossary_index)` が `.dml.yaml` の `decisions[]` を描画。`decisions[]` が空なら見出しごと出力されない。

### カード構造

```
.decision-card
  h3              ← "<id>. <topic>"
  .dep            ← "採用: <chosen>"、任意で "影響: <affects[]>"（`contexts[].lang` 由来の glossary_index で日本語化）
  .decision-options
    .opt.adopted    ← 採用された option（緑系・✓ マーカー）
    .opt.rejected   ← 不採用 option（灰背景・取り消し線）
  .decision-note  ← decisions[].note（あれば、斜体）
```

### CSS 主要部

| クラス | スタイル意味 |
|---|---|
| `.decision-card` | Policy と同じ紫系の縁取りカード（border-left / h3 とも `#7B1FA2`） |
| `.decision-options` | flex column / gap 6px |
| `.opt` | 共通：薄い背景 + 左ボーダー |
| `.opt.adopted` | 背景 `#E8F5E9` / 左ボーダー `#2E7D32` / `.opt-name` 文字緑・太字 |
| `.opt.rejected` | 背景 `#FAFAFA` / 左ボーダー `#B0BEC5` / `.opt-name` 取り消し線（採用者と視覚的に差別化） |
| `.opt-why` | 採用理由（緑系本文） |
| `.opt-why-not` | 不採用理由（灰系本文） |
| `.decision-note` | カード末尾の補足（イタリック・グレー） |

各 option の `adopted` 判定は `decisionOption.adopted` を優先し、未指定なら `name == chosen` を `true` 扱いにする。`why` / `why_not` は採用/不採用に応じて自動切替（採用は `why`、不採用は `why_not` をフォールバックに `why` を）。

---

## 7. 自動オープン

### 7-1. フェーズ2完了時のみ初回オープン

DML（`.dml.yaml`）を Write した直後、PostToolUse hook が HTML を生成するので、AI は続けて `Bash open dist/eventstorming/<session>.html` を実行して外部ブラウザを起動する。

### 7-2. 自動リロード（2 系統）

| 機構 | 対象 | 動作 |
|---|---|---|
| **`<meta http-equiv="refresh" content="3">`** | 外部ブラウザ | 3 秒ごとに自身を再読み込み |
| **`reload_browser_tab()` (osascript)** | macOS Chrome / Safari | ビルダーが HTML 生成後に該当タブを即座に reload |

両方が併用されることで、外部ブラウザは常に最新版を表示する。

### 7-3. Claude Code Launch preview panel

Claude Code（CLI/PC/スマホアプリ）の preview panel は **JavaScript / `<meta http-equiv="refresh">` を実行しない** スナップショット表示。AI が `Read dist/eventstorming/<session>.html` を呼んだ瞬間に最新版が表示される。

→ **フェーズ完了テンプレの末尾で必ず `Read` を呼ぶこと**（`chat-output-format.md` §3 参照）。

### 7-4. スマホ環境

スマホアプリでは Files / Safari で `dist/eventstorming/*.html` を開く。`Bash open` も `osascript` も効かないので、AI は「HTMLファイルを開いてください」と案内する。meta-refresh は機能する。

---

## 8. ビルダーの内部構造

`.claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py` は単一ファイル、Python 3 標準ライブラリ + PyYAML で実装。主要関数：

```
_load_dml_model(dml_text) → dict|None  # .dml.yaml を yaml.safe_load
_validate_dml_warn(dml, path) → list   # JSON Schema 検証で警告一覧（HTML §9 バナーに反映）
build_flows_from_dml(model, gloss)     # narratives[].entry + scenarios[].next/brs.terminal + policies の自動連鎖 → Flow / Lane / Note
render_flows(flows) → HTML             # Flow 群 → Big Picture グリッド HTML
render_flow(flow) → HTML               # 単一 Flow の描画
aggregates_from_dml(model) → list      # 集約 1 件あたり attrs/events/inv/err 等を集計
render_agg_cards_from_dml(model, gl)   # AGG カード（属性表 / payload 表 / inv / err）
render_decisions(model, gloss) → HTML  # decisions[] → .decision-card 群
render_progress(status) → HTML         # session.phase / status から進捗バー
render_context_map(bc_cards) → SVG     # UPSTREAM/DOWNSTREAM から関係図 SVG
highlight_dml(dml) → HTML              # DML（YAML）役割ベース意味色ハイライト
render_html(sections) → HTML 全文      # テンプレに埋め込んで完成版を返す
build(yaml_path, out_dir) → Path       # 1 ファイルビルド → reload_browser_tab() 込み
reload_browser_tab(html_path)          # macOS Chrome/Safari の該当タブを osascript で reload
build_all(in_dir, out_dir)             # 全件ビルド
watch(in_dir, out_dir)                 # 監視モード
```

依存: `re`, `pathlib`, `argparse`, `dataclasses`, `time`, `sys`, `subprocess`（hook 内のみ）、`yaml`（PyYAML）。

---

## 9. フォールバック

書き込み権限がない、Python 3 や PyYAML が無い等の環境では、ビルダーが動かない（または DML 解析が失敗する）。

- PyYAML 不在 / DML 解析失敗時は、§2・§5・§7 は `.todo-placeholder` で縮退表示し、**例外で停止せず HTML 生成は最後まで継続**
- 手動再実行: `python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <yaml>`
- 解決不可ならチャット本文に **構造化テーブル** で代替表示（`chat-output-format.md` §9 参照）

---

## 10. DML → HTML 主要マッピング（要約）

| DML 要素 | HTML 出力 |
|---|---|
| `narratives[].title` | `<div class="flow-title">{title}</div>`（`entry` 指定時のみフロー図描画） |
| scenarios[]（next 連鎖で訪問されたもの） | `scenarios[].actor` / `qry` / `cmd` / `evt`（または brs[active].evt）を順に Note 描画。Lane は `scenarios[].ctx` |
| policies[]（scenarios[].evt → policies[].trg マッチで自動挿入） | `policies[].trg` → `cmd` → `evt` を Note 描画。Lane は `policies[].ctx`。前 Lane 末尾 Note に `is_async=True` |
| `scenarios[].brs[].terminal` | 当該 `narratives[].id` と一致するフローはこの brs 発火後に終端 |
| `policies[].trgs.evts` | 前 Lane の `joins_into_next=True`。`.sync-bar` + Σ N 描画 |
| `policies[].bulk: true` | 該当 Note に `.note.fanout` + 右上 `× N` バッジ |
| `scenarios[].pivotal: true` | 発火 EVT の Note に `.note.pivotal` + 左上 `⭐ 節目` バッジ（同名 EVT を policy が emit する場合も強調） |
| `contexts[].name` | `<div class="lane-name bc-default-N">{name}</div>` |
| `aggregates[].purpose` / `background` / `constraints` | `.purpose-section` / `.background-section` / `.constraints-section` |
| `aggregates[].attrs[]` | `table.attr-table` |
| `aggregates[].events[].params[]` | `table.attr-table.payload-table` (EVT 名見出し付き) |
| `scenarios[].rules[]`（同一 agg） | `.inv-section`（緑・✓） |
| `scenarios[].errs[]`（同一 agg） | `.err-section`（赤・⚠）、識別子はバックティックで `.err-code` |
| `aggregates[].transitions[]` | 状態遷移リスト |
| `decisions[]` | `.decision-card` 群（`.opt.adopted` 緑 / `.opt.rejected` 灰） |

時系列ステップ（grid-column）は付箋・矢印のたびに +1。同じ BC が複数回登場する場合も同じ grid-row に配置する。
