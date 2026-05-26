# Event Flow SVG レンダリング仕様

assistant が `event-flow-svg` DSL を読み解いて、Markdown チャット本文に直接埋め込む `<svg>...</svg>` を手で生成するための仕様。

iOS 縦画面 (iPhone 375pt / iPad mini 768pt) で横スクロール無しで読めることを優先する。

---

## 1. 出力先と全体フォーマット

- **チャット本文に直接埋め込む** (` ```svg ` コードブロックではなく、Markdown 中に裸の `<svg ...>...</svg>`)
- SVG の **直後に「参照番号リスト」** を Markdown で併記する (アイテム ID と日本語ラベルの対応)
- フォールバック (描画されない場合): §10 を参照

---

## 2. ビューポートと寸法

| 項目 | 値 |
|---|---|
| viewBox | `0 0 380 H` (W=380 固定、H 動的) |
| width / height | viewBox と一致 (`width="380" height="H"`) |
| xmlns | `http://www.w3.org/2000/svg` |
| lane 並び | **縦積み** (BC が上から下へ) |

横並びは採用しない。BC が3以上でも縦積み (スクロール許容)。

### 主要定数

| 名前 | 値 | 用途 |
|---|---|---|
| `VIEW_W` | 380 | viewBox 幅 |
| `NOTE_W` | 110 | ノート (付箋) 幅 |
| `NOTE_H` | 56 | ノート高さ |
| `H_LANE_HDR_W` | 70 | レーン名カラム幅 (左端) |
| `H_ITEM_GAP` | 12 | ノート間水平ギャップ |
| `LANE_PAD` | 12 | レーン内パディング (上下) |
| `LANE_H` | NOTE_H + LANE_PAD×2 = 80 | レーン1行の高さ |
| `LANE_H_2ROW` | NOTE_H×2 + LANE_PAD×2 + 12 = 148 | 折り返し時の2段レーン高さ |
| `SEG_LBL_H` | 28 | セグメントラベル帯の高さ |
| `TITLE_H` | 32 | タイトル帯の高さ |
| `H_SEG_PAD` | 14 | セグメント開始位置の左マージン (lane header 直後) |

### 1レーンあたりの最大ノート数

- **横方向 4 個まで** ((110 + 12) × 4 - 12 = 476 だが、最初の note は H_LANE_HDR_W + H_SEG_PAD = 84 から始まるので 84 + 476 = 560 → はみ出すため **実質3個**)
- W=380 / lane header 70 / 左パディング 14 を引いた 296 px が描画領域 → (110 + 12) × n - 12 ≤ 296 → n ≤ 2.5 → **2 ノート/レーン/セグメント**
- 3ノート以上は **セグメント分割** を優先 (§4)
- セグメント分割でも収まらない 5+ ノートは **2段折り返し** (§5)

---

## 3. 色とフォント

### 種別別の色

| 種別 | DSL記号 | fill | stroke | text | typeLabel | typeLabel色 |
|---|---|---|---|---|---|---|
| actor | `@` | `#FFF59D` | `#F9A825` | `#4E342E` | `Actor` | `#795548` |
| readmodel | `?` | `#A5D6A7` | `#2E7D32` | `#1B5E20` | `Read Model` | `#2E7D32` |
| command | `!` | `#90CAF9` | `#1565C0` | `#0D47A1` | `Command` | `#1565C0` |
| event | `[...]` | `#FFAB40` | `#E65100` | `#7f2700` | `Event` | `#BF360C` |
| policy | `$` | `#CE93D8` | `#7B1FA2` | `#4A148C` | `Policy` | `#4A148C` |

ノートは `<rect rx="3" stroke-width="2">`。

### レーン色 (lane header の塗り)

```
LANE_COLORS = ['#37474F', '#455A64', '#546E7A', '#607D8B', '#78909C']
```

レーン番号 li に対し `LANE_COLORS[li % 5]`。

### レーン背景 (フル幅、奇偶で色を変える)

```
BG_COLS = ['#F8F9FA', '#FFFFFF']
```

### セグメントラベル帯

- bg `#E3F2FD` / 枠 `#90CAF9` / text `#1565C0` / `font-style="italic"`

### 矢印

| 種別 | stroke | width | dasharray | marker |
|---|---|---|---|---|
| 同期 (セグメント内) | `#546E7A` | 1.8 | なし | `url(#ef-arr)` |
| 同期 (セグメント間、レーン同じ) | `#90A4AE` | 2 | `6 3` | `url(#ef-arr)` |
| 非同期 (`>>` でレーン跨ぎ) | `#7B1FA2` | 2 | `8 4` | `url(#ef-arr-async)` |

非同期矢印には ⚡ async ラベルを曲線中央上部に置く: `<text font-size="8" fill="#7B1FA2">⚡ async</text>`

### `<defs>` (SVG 先頭で必須)

```svg
<defs>
  <marker id="ef-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#546E7A"/></marker>
  <marker id="ef-arr-async" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7B1FA2"/></marker>
</defs>
```

### フォント

- 全体: `font-family="'Noto Sans JP','Hiragino Kaku Gothic ProN',sans-serif"` を `<svg>` ルートに付ける (継承)
- 種別ラベル (note 上部): `font-size="8" font-weight="700"`
- アイテムラベル (note 中央): `font-size="10" font-weight="600"`
- レーンヘッダー: `font-size="10" font-weight="700" fill="#FFF"`
- セグメントラベル: `font-size="11" font-style="italic" fill="#1565C0"`
- SVG 内タイトル: `font-size="12" font-weight="700" fill="#FFF"`
- 非同期 ⚡ async ラベル: `font-size="8" fill="#7B1FA2"`

### ラベル折り返しルール

- アイテムラベルが **8 文字** を超えたら 2 行に分割 (現 `splitLabel(text, 14)` を iOS 用に短縮)
- 1ノートに最大 2 行まで表示。3 行以上になる場合は要約して 2 行に収める
- レーンヘッダーは **6 文字** を超えたら 2 行

---

## 4. レイアウト (縦積み)

```
┌────────────────────────────────────┐  ← TITLE_H (32)
│            タイトル帯 #37474F            │
├────────────────────────────────────┤  ← SEG_LBL_H (28、任意)
│      セグメントラベル帯 #E3F2FD          │
├────┬───────────────────────────────┤  ← LANE_H (80) × N
│BC1 │ [note] → [note]                │
├────┼───────────────────────────────┤
│BC2 │ [note] → [note] (async↑)      │
└────┴───────────────────────────────┘
```

### Y 座標計算

- `TITLE_Y_END = TITLE_H = 32`
- `SEG_Y_END = TITLE_Y_END + SEG_LBL_H (任意) = 60`
- `LANE_TOP[i] = SEG_Y_END + i * LANE_H`
- `NOTE_Y[i] = LANE_TOP[i] + LANE_PAD = LANE_TOP[i] + 12`
- `LANE_CENTER_Y[i] = NOTE_Y[i] + NOTE_H/2 = LANE_TOP[i] + 40`

### X 座標計算 (1セグメントの場合)

- `NOTE_X[j] = H_LANE_HDR_W + H_SEG_PAD + j * (NOTE_W + H_ITEM_GAP)`
- = `70 + 14 + j * 122` = `84 + j * 122`
- j=0: 84, j=1: 206, j=2: 328 (はみ出す — 2ノートまで)

### 全体の高さ H

```
H = TITLE_H + (hasSegLabel ? SEG_LBL_H : 0) + Σ(lane_h) + 20  # 下20pxマージン
```

シングル段レーンなら `lane_h = LANE_H = 80`、2段折り返しなら `lane_h = LANE_H_2ROW = 148`。

---

## 5. 折り返し戦略

ノート数が 1 レーン × 1 セグメントの最大 (2) を超える場合:

### 5-1. まずセグメント分割を試みる (推奨)

ストーリー上の章の切れ目 (時間経過・状態変化・別アクター介入) で `|BC名|: <セグメント説明>` を入れて、セグメントを分ける。各セグメントが独立した X 配置を持つ。

ただし W=380 制約下で複数セグメントを横並びにすると詰まる。1レーン × 2セグメント × 2ノートでも 計4ノート分の幅が必要だが描画領域 296 px には収まらない。
**ので、複数セグメントを使うときも `<svg>` 内では「セグメントごとに改行して縦配置」する**:

```
┌────────────────────────────────────┐
│   セグメント1: 受付段階              │
├────┬───────────────────────────────┤
│BC1 │ [note1] → [note2]               │
├────────────────────────────────────┤
│   セグメント2: 確認段階              │
├────┬───────────────────────────────┤
│BC1 │ [note3] → [note4]               │
└────┴───────────────────────────────┘
```

つまり **「セグメントは縦に積む」** が iOS 縦画面での実装方針。

### 5-2. 2段折り返し (セグメント分割が困難な場合のみ)

1セグメント内で 3ノート以上必要なら、同じ lane を 2 段に折り返す:

- レーン高さを `LANE_H_2ROW = 148` に拡張
- 1段目: j=0, 1 (NOTE_X[0]=84, NOTE_X[1]=206)
- 2段目: j=2, 3 (NOTE_X[0]=84, NOTE_X[1]=206 だが Y は NOTE_Y[i] + NOTE_H + 12)
- 1段目末尾 → 2段目先頭は **"U" 字矢印** (右に出て下にカーブして左から戻る)

矢印パス例:
```svg
<path d="M{x1+NOTE_W},{y1+NOTE_H/2} C{x1+NOTE_W+30},{y1+NOTE_H/2} {x1+NOTE_W+30},{y2+NOTE_H/2} {x1+NOTE_W},{y2+NOTE_H/2} L{x2},{y2+NOTE_H/2}" .../>
```

ただし W=380 では x1+NOTE_W+30 が描画領域外になりやすい。**実質的には U 字より「下向きの直線矢印」で十分**:

```svg
<line x1="{x1+NOTE_W/2}" y1="{y1+NOTE_H}" x2="{x1+NOTE_W/2}" y2="{y2}" stroke="#546E7A" stroke-width="1.8" marker-end="url(#ef-arr)"/>
```

(1段目最後のノート中央下端 → 2段目最初のノート中央上端への垂直矢印)

---

## 6. レーン間の async 遷移 (`>>`)

縦積みのため、前レーン末尾 → 次レーン先頭への遷移は **垂直または斜めのベジエ曲線**:

```svg
<path d="M{x1+NOTE_W/2},{y1+NOTE_H} C{x1+NOTE_W/2},{y1+NOTE_H+20} {x2+NOTE_W/2},{y2-20} {x2+NOTE_W/2},{y2}"
      fill="none" stroke="#7B1FA2" stroke-width="2" stroke-dasharray="8 4"
      marker-end="url(#ef-arr-async)"/>
<text x="{(x1+x2)/2+NOTE_W/2}" y="{(y1+NOTE_H+y2)/2}" text-anchor="middle"
      font-size="8" fill="#7B1FA2">⚡ async</text>
```

座標:
- `x1+NOTE_W/2` = 前レーン最後のノート中央 X
- `y1+NOTE_H` = 前レーン最後のノート下端 Y
- `x2+NOTE_W/2` = 次レーン最初のノート中央 X
- `y2` = 次レーン最初のノート上端 Y

---

## 7. アイテム識別子 (E1, C2 等)

- **SVG 内には書かない** (iOS 解像度で読みづらいため)
- SVG 直後に **参照番号リスト** を Markdown で書く

例:
```markdown
参照番号:
- A1 = @利用者
- A2 = @スタッフ
- C1 = !本を予約
- C2 = !本を貸出
- E1 = [予約された]
- E2 = [貸し出された]
```

### ID 割り当て規則

| 種別 | プレフィックス | 番号 |
|---|---|---|
| actor | A | 出現順 (シナリオ全体で通し) |
| command | C | 出現順 |
| event | E | 出現順 |
| policy | P | 出現順 |
| readmodel | Q | 出現順 |

同じラベルが複数回出現したら同じ ID を使う (例: `@利用者` が3回出ても A1)。

---

## 8. SVG 生成手順 (DSL → SVG 変換)

`event-flow-svg` ブロックから SVG を作る手順。assistant が頭の中で実行する:

### 8-1. パース

DSL を読んで以下を作る:

1. **タイトル** (`title:` の右側)
2. **アイテムリスト**: 各行を `>` で分割し、種別 (`@`/`?`/`!`/`[...]`/`$`) を判定。lane と isAsync を保持
3. **セグメント分割**: 連続する同レーン行を 1 セグメントにまとめる。`|BC名|: 説明` で次のセグメントに移る
4. **レーン順**: 出現順
5. **セグメントラベル**: `|BC名|: 説明` の説明部分を該当セグメントに紐付け

### 8-2. レイアウト計算

1. **セグメントを縦に積む順序を決める**: 出現順
2. **各セグメントの高さ**: ノート数 ≤ 2 なら LANE_H、3+ なら LANE_H_2ROW
3. **全体高さ H** を計算
4. **各ノートの X, Y 座標** を算出

### 8-3. SVG 構築 (出力順序)

1. `<svg width=... height=H viewBox="0 0 380 H" font-family="..." xmlns="...">`
2. `<defs>` (marker × 2)
3. タイトル帯 `<rect>` + `<text>`
4. セグメント (上から順):
   - セグメントラベル帯 (任意) `<rect>` + `<text>`
   - レーン背景 `<rect>` (BG_COLS で奇偶)
   - レーンヘッダー `<rect>` + `<text>` (lane 名、LANE_COLORS で着色)
   - アイテム間の矢印 (`<line>` または `<path>`) — ノートより先に描く
   - ノート (`<g><rect>...<text>...</g>`)
5. セグメント間の async 矢印 (`>>`)
6. `</svg>`

### 8-4. 参照番号リストを SVG 直後に Markdown で出力

---

## 9. 簡略テンプレート (assistant 用)

assistant は以下のテンプレを選んで `{...}` を埋めるだけで SVG を書ける。
**改行・インデントは省略してよい** (チャットの token を節約)。

### テンプレ-1: 1 BC × 2 ノート (最小)

```svg
<svg width="380" height="112" viewBox="0 0 380 112" font-family="'Noto Sans JP',sans-serif" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="ef-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#546E7A"/></marker></defs>
<rect x="0" y="0" width="380" height="32" fill="#37474F"/>
<text x="190" y="21" text-anchor="middle" fill="#FFF" font-size="12" font-weight="700">{TITLE}</text>
<rect x="0" y="32" width="380" height="80" fill="#F8F9FA"/>
<rect x="0" y="32" width="70" height="80" fill="#37474F"/>
<text x="35" y="77" text-anchor="middle" fill="#FFF" font-size="10" font-weight="700">{BC_NAME}</text>
<g><rect x="84" y="44" width="110" height="56" rx="3" fill="#FFF59D" stroke="#F9A825" stroke-width="2"/>
<text x="139" y="57" text-anchor="middle" font-size="8" font-weight="700" fill="#795548">Actor</text>
<text x="139" y="77" text-anchor="middle" font-size="10" font-weight="600" fill="#4E342E">{ACTOR_LABEL}</text></g>
<line x1="194" y1="72" x2="206" y2="72" stroke="#546E7A" stroke-width="1.8" marker-end="url(#ef-arr)"/>
<g><rect x="206" y="44" width="110" height="56" rx="3" fill="#FFAB40" stroke="#E65100" stroke-width="2"/>
<text x="261" y="57" text-anchor="middle" font-size="8" font-weight="700" fill="#BF360C">Event</text>
<text x="261" y="77" text-anchor="middle" font-size="10" font-weight="600" fill="#7f2700">{EVENT_LABEL}</text></g>
</svg>
```

### テンプレ-2: 2 BC × 縦積み + 非同期遷移

ノート Y 座標:
- BC1 行 (i=0): NOTE_Y = 32 + 12 = 44 (タイトル帯のみ、セグメントラベル無し)
- BC2 行 (i=1): NOTE_Y = 32 + 80 + 12 = 124

```svg
<svg width="380" height="212" viewBox="0 0 380 212" font-family="'Noto Sans JP',sans-serif" xmlns="http://www.w3.org/2000/svg">
<defs>
<marker id="ef-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#546E7A"/></marker>
<marker id="ef-arr-async" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7B1FA2"/></marker>
</defs>
<rect x="0" y="0" width="380" height="32" fill="#37474F"/>
<text x="190" y="21" text-anchor="middle" fill="#FFF" font-size="12" font-weight="700">{TITLE}</text>
<!-- BC1 -->
<rect x="0" y="32" width="380" height="80" fill="#F8F9FA"/>
<rect x="0" y="32" width="70" height="80" fill="#37474F"/>
<text x="35" y="77" text-anchor="middle" fill="#FFF" font-size="10" font-weight="700">{BC1_NAME}</text>
<g><rect x="84" y="44" width="110" height="56" rx="3" fill="#FFF59D" stroke="#F9A825" stroke-width="2"/>
<text x="139" y="57" text-anchor="middle" font-size="8" font-weight="700" fill="#795548">Actor</text>
<text x="139" y="77" text-anchor="middle" font-size="10" font-weight="600" fill="#4E342E">{A1_LABEL}</text></g>
<line x1="194" y1="72" x2="206" y2="72" stroke="#546E7A" stroke-width="1.8" marker-end="url(#ef-arr)"/>
<g><rect x="206" y="44" width="110" height="56" rx="3" fill="#FFAB40" stroke="#E65100" stroke-width="2"/>
<text x="261" y="57" text-anchor="middle" font-size="8" font-weight="700" fill="#BF360C">Event</text>
<text x="261" y="77" text-anchor="middle" font-size="10" font-weight="600" fill="#7f2700">{E1_LABEL}</text></g>
<!-- BC2 -->
<rect x="0" y="112" width="380" height="80" fill="#FFFFFF"/>
<rect x="0" y="112" width="70" height="80" fill="#455A64"/>
<text x="35" y="157" text-anchor="middle" fill="#FFF" font-size="10" font-weight="700">{BC2_NAME}</text>
<g><rect x="84" y="124" width="110" height="56" rx="3" fill="#90CAF9" stroke="#1565C0" stroke-width="2"/>
<text x="139" y="137" text-anchor="middle" font-size="8" font-weight="700" fill="#1565C0">Command</text>
<text x="139" y="157" text-anchor="middle" font-size="10" font-weight="600" fill="#0D47A1">{C1_LABEL}</text></g>
<line x1="194" y1="152" x2="206" y2="152" stroke="#546E7A" stroke-width="1.8" marker-end="url(#ef-arr)"/>
<g><rect x="206" y="124" width="110" height="56" rx="3" fill="#FFAB40" stroke="#E65100" stroke-width="2"/>
<text x="261" y="137" text-anchor="middle" font-size="8" font-weight="700" fill="#BF360C">Event</text>
<text x="261" y="157" text-anchor="middle" font-size="10" font-weight="600" fill="#7f2700">{E2_LABEL}</text></g>
<!-- async transition BC1[Event] → BC2[Command] -->
<path d="M261,100 C261,112 139,112 139,124" fill="none" stroke="#7B1FA2" stroke-width="2" stroke-dasharray="8 4" marker-end="url(#ef-arr-async)"/>
<text x="200" y="118" text-anchor="middle" font-size="8" fill="#7B1FA2">⚡ async</text>
</svg>
```

### テンプレ-3: 3+ ノートを 1 BC で扱う場合 (セグメント縦積み)

例: 同じ BC で `@A1 > !C1 > [E1] > !C2 > [E2]` (5ノート)
→ セグメント1 = (A1, C1, E1)、セグメント2 = (C2, E2) として **縦に積む**

```svg
<svg width="380" height="240" ...>
<!-- タイトル -->
<rect x="0" y="0" width="380" height="32" fill="#37474F"/>
<text x="190" y="21" .../>
<!-- セグメント1 ラベル (任意) -->
<rect x="0" y="32" width="380" height="28" fill="#E3F2FD" stroke="#90CAF9"/>
<text x="78" y="51" font-size="11" font-style="italic" fill="#1565C0">受付段階</text>
<!-- BC1 セグメント1 (3ノート: 折り返し or 2ノートに削る) -->
<rect x="0" y="60" width="380" height="80" fill="#F8F9FA"/>
<rect x="0" y="60" width="70" height="80" fill="#37474F"/>
<text x="35" y="105" .../>
<!-- ここに A1, C1 の2ノート (E1 はセグメント2先頭に移す) -->
...
<!-- セグメント2 ラベル -->
<rect x="0" y="140" width="380" height="28" fill="#E3F2FD" stroke="#90CAF9"/>
<text x="78" y="159" font-size="11" font-style="italic" fill="#1565C0">確認段階</text>
<!-- BC1 セグメント2 -->
<rect x="0" y="168" width="380" height="80" fill="#F8F9FA"/>
<rect x="0" y="168" width="70" height="80" fill="#37474F"/>
<!-- ここに E1, C2, E2 ... (3ノート → 2ノートに収まらない場合は 4) -->
...
</svg>
```

---

## 10. フォールバックモード (SVG が描画されない場合)

ユーザーから「SVG が生コードのまま見える」と報告されたら、以降の出力で SVG を出さず **構造化リスト** に切り替える。

### フォーマット

````
### Event Flow (フォールバック表示)

**ハッピーパス**

- **予約BC**: A1 @利用者 → C1 !本を予約 → E1 [予約された]
- **(async 遷移)**
- **貸出BC**: A2 @スタッフ → C2 !本を貸出 → E2 [貸し出された]

参照番号:
- A1 = @利用者 / A2 = @スタッフ
- C1 = !本を予約 / C2 = !本を貸出
- E1 = [予約された] / E2 = [貸し出された]
````

ルール:
- 各 BC を `**BC名**:` で開始
- ノートは `<ID> <種別記号><ラベル>` 形式
- レーン遷移は `**(async 遷移)**` で示す (同期なら省略)
- 矢印は `→` (U+2192) を使う
- 色は付けない (Markdown の制約)

---

## 11. 既存実装 (render.py) との対応

参考までに、現 `scripts/render.py` (削除予定) のレイアウト計算ロジックとの対応:

| 旧実装 (render.py) | 新仕様の場所 |
|---|---|
| L700-L702: 寸法定数 (NOTE_W=130 等) | §2 (W=380 縦画面用に縮小) |
| L711-L723: `splitLabel(text, maxChars=14)` | §3 (8文字に短縮) |
| L725-L895: `renderEventFlowSVG()` 全体 | §8 (assistant が手で実行) |
| L753-L757: セグメント分割 | §8-1 step3 |
| L760: セグメント幅計算 | §4 X座標 (W=380 制約) |
| L772-L774: レーン Y 座標 | §4 (縦積み版に書き換え) |
| L862: クロスセグメントベジエ曲線 | §6 (async 遷移) |
| L831-L840: clipPath セグメントラベル | §5-1 (縦積みなので clipPath 不要) |
| L902-L949: `parseFlowStr()` (DSL パーサ) | §8-1 (assistant が読み解く) |
| L952-L968: `parseSegLabels()` | §8-1 step5 |
