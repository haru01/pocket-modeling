# ラベル命名規則

## 3 系統を厳密に分離

| 系統 | プレフィックス | 用途 | 例 |
|---|---|---|---|
| **BC** | `bc:` | 境界づけられたコンテキスト（大項目） | `bc:event-planning` `bc:registration` |
| **AGG** | `agg:` | 集約（中項目） | `agg:Event` `agg:Application` |
| **Type** | `type:` | Issue の種別 | `type:aggregate` `type:scenario` `type:saga` |
| **特殊** | （無印） | 横断的な属性 | `cross-bc` |

**運用系 (`phase:1`, `priority:high`, `area:backend` 等) は本スキルでは付けない**。モデリング由来ラベルと運用ラベルを混ぜないため。

## 命名規約

- `bc:<kebab-case>` — DML の `contexts[].name` 識別子そのまま
- `agg:<PascalCase>` — DML の `scenarios[].agg` 識別子そのまま
- `type:<lower>` — 種別は以下のみ
  - `type:aggregate`（AGG Epic Issue。CMD/QRY/受信 POLICY を inline 保持。AI dispatch 単位）
  - `type:scenario`（AGG 跨ぎ統合 Issue）
  - `type:saga`（Cross-BC Saga）
- `cross-bc` — BC 境界を越える Issue / Saga に付与（`bc:` と併用）

> CMD / QRY / 受信 POLICY は AGG Epic 本文に inline されており **独立 Issue を起票しない** ので、`type:command` / `type:query` / `type:policy` / `mutates-state` のラベルは廃止。

## 付与パターン

| Issue 種別 | 必須ラベル |
|---|---|
| AGG Epic | `bc:<owner>` `agg:<Name>` `type:aggregate` |
| AGG 跨ぎ統合 SCENARIO | `bc:` を複数 / `agg:` を複数 / `type:scenario` / `cross-bc` |
| Cross-BC Saga | `bc:<start>` `bc:<end>` `type:saga` `cross-bc` |

## 重要なルール

- `bc:` `agg:` は **多重付与可**。BC 跨ぎ Issue を両方の BC ビューから発見可能に
- 主体 BC = 1 つを AGG Epic 本文の「実装担当範囲」セクションで必ず明示
- AGG Epic は単一 AGG に閉じる。複数 AGG を跨ぐ処理は統合 Issue / Saga 側で扱う

## クエリ例（集約スコープでの即時識別）

```
# 集約 Event の Epic
is:issue label:agg:Event label:type:aggregate

# BC event-planning に属するすべての Issue（Epic + 統合）
is:issue label:bc:event-planning

# BC を跨ぐ Issue
is:issue label:cross-bc
```

## 色設計（gh label create 用デフォルト）

```
type:aggregate    #1D76DB  青       構造の柱（AI dispatch 単位）
type:scenario     #C2E0C6  薄緑     跨ぎ統合
type:saga         #D93F0B  橙       プロセス（Cross-BC）

agg:*             #EDEDED  薄灰     統一補助色
bc:*              BC ごとに HSL ハッシュで自動割当
cross-bc          #B60205  赤       警告
```

## スキルの責務

1. 入力 MD から必要なラベル集合を抽出
2. `gh label list --json name` で既存確認 → 不足分のみ `gh label create` で作成
3. **既存ラベルの色は上書きしない**（ユーザー編集を尊重）
4. ラベル一覧を `_labels.md` に記録
