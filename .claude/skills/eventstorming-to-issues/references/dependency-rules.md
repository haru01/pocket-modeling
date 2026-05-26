# 依存判定ルール

新設計（1 AGG = 1 self-contained Epic = 1 PR）下では、Issue 構造に影響するのは **AGG 跨ぎ判定** と **POLICY ルーティング** のみ。CMD / QRY / 受信 POLICY は対応する AGG Epic 本文に inline されるので、それぞれを独立 Issue にしない。

## AGG 跨ぎ SCENARIO の判定（統合 Issue 化）

入力 MD の `### Aggregate` カード内 `- 関連シナリオ:` リストを使う。

**同一 SCENARIO 名が複数の AGG カードで言及されている場合 → 跨ぎ SCENARIO** として扱い、`integration/<scenario>.md` に統合 Issue を生成する。

例:
- `Application` カードの関連シナリオに「参加者がイベント詳細を確認して参加を申し込む」
- `Ticket` カードの関連シナリオにも同じ SCENARIO
→ この SCENARIO は `Application + Ticket` を跨ぐ統合 Issue

1 AGG にのみ紐づく SCENARIO は、その AGG Epic の CMD 詳細セクションに inline される（独立 Issue 化しない）。

## POLICY ルーティング規則

DML の `POLICY` ブロックは `parse_eventstorming_md.py` の `parse_dml_blocks()` で抽出され、`generate_issue_drafts.py:route_policies()` が各 POLICY を AGG に振り分ける。

ルーティング規則:

| 条件 | 行き先 | Epic 内セクション |
|---|---|---|
| POLICY に `CMD <name>` あり | CMD が属する AGG (cmd → AGG マップで逆引き) | **受信 POLICY (inbound)** |
| POLICY に `CMD` なし（副作用専用） | TRIGGER EVT を発火する AGG (evt → AGG マップで逆引き) | **副作用専用 POLICY (outbound, side-effects)** |
| 発生元 AGG ↔ 行き先 AGG が異なる BC | （上記に加えて） | `cross-bc` フラグを立て、Epic で ⚠ 表示 |

`outbound_consumers` は EVT 発火元 AGG 側で「自分の EVT を消費する POLICY」一覧として表示するため、上記とは別軸で集計される。

cmd → AGG マップは DML SCENARIO の `CMD <name>` + `AGG <agg>` から、evt → AGG マップは DML SCENARIO の `EVT <name>` + `AGG <agg>` から構築する（`generate_issue_drafts.py:build_cmd_to_agg_map()` / `build_evt_to_agg_map()`）。

## 状態遷移 CMD の判定

AGG カードの `#### 状態遷移` セクションに記載されている遷移を解析:

```
- DRAFT → PUBLISHED: 公開操作（必須項目チェック）
- PUBLISHED → CANCELLATION_REQUESTED: 主催者による中止要求
```

各遷移行から:
- `from` 状態: `→` の左
- `to` 状態: `→` の右、`:` の前
- `trigger`: `:` 以降

を抽出して AGG Epic の「状態遷移を起こす CMD（一覧）」テーブルおよび「状態遷移を起こす CMD（詳細）」セクションに inline する。

## Cross-BC Saga

複数の POLICY が連鎖して BC を跨ぐ場合（例: 申込 → 支払 → チケット発行）、それを 1 つの Saga Issue として独立させる。

判定: 同一 SCENARIO 内で 2 つ以上の BC レーンを `>>`（非同期）で繋ぐ場合、Saga 候補として `cross-bc/` ディレクトリに生成。

> 個々の POLICY 自体は AGG Epic 内に inline されているので、Saga Issue は連鎖全体の整合性・補償トランザクション・Saga インスタンス管理（DB / Temporal 等）を扱う窓口。

## BC 間依存

`### BC Candidates` カードの:
- `UPSTREAM:` リスト → この BC は記載 BC に依存する
- `DOWNSTREAM:` リスト → この BC に依存される BC

これを Mermaid の `graph LR` で `Upstream --> Downstream` 方向に描画 (`build_dependency_graph.py`)。
