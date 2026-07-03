# DDD／EventStorming 観点カバレッジ分析と改善提案（2026-07-03）

現行スキル（SKILL.md / dml-spec / session-guide / checks 18+6 観点 / term-glossary / dml.schema.yaml）を
DDD／EventStorming の標準的な観点セットと突き合わせたギャップ分析。

## 現状よくカバーできている観点（再掲不要）

- 戦術 DDD の中核: EVT/CMD/Actor/Policy（SAME-TX vs EVENTUAL-TX）/ Read Model / AGG（purpose・states・transitions・attrs・events）/ 不変条件（rules）と業務エラー（errs）の区別
- BC とユビキタス言語（contexts[].lang）、依存方向（up/dn/rel）、インフラ系の BC 昇格判定
- ホットスポット `[?]` → decisions[] 昇格、why/why_not の業務文脈化
- フロー連鎖（narratives.entry / next / terminal）、時刻駆動・コールバック・補償の書き方
- 構造 18 チェック + 意味 6 チェックの 2 段階検証

## ギャップと提案（優先順位順）

### 【P1-①】コアドメイン蒸留（Core/Supporting/Generic）のファシリテーション導線 ✅ 反映済み（2026-07-03）

- **ギャップ**: schema には `domains[].subs[].type`（CORE/SUPPORTING/GENERIC_SUBDOMAIN）と
  `contexts[].sub` が**既に存在する**のに、9 フェーズのどこにも書き出しタイミングが無く、
  session-guide にも質問パターンが無い。死にフィールド化している。
  戦略 DDD の「どこに投資するか」を決める最重要観点が抜けている。
- **提案**:
  - フェーズ 4.5（BC 境界）完了時に「このうち、間違えると事業が成り立たないのはどれ？／
    買ってくる・真似すれば済むのはどれ？」の 2 問を追加し `domains[]` + `contexts[].sub` に書き出す
  - SKILL.md フェーズ表・DML 出力タイミング表に `domains[]` の行を追加
  - 構造 check 追加: `subdomain_classification`（contexts[].sub が未設定 / CORE が 0 件 or 全件）
  - term-glossary に「コアドメイン／汎用サブドメイン」を追加
- **コスト**: 小（schema 変更不要。ガイド追記 + check 1 本）

### 【P1-②】コンテキストマップ語彙のフル活用（Partnership / OHS / PL / Separate-Ways）

- **ギャップ**: schema の `relationshipPattern` は CML 由来の Partnership / Open-Host-Service /
  Published-Language まで対応済みだが、session-guide の「関係タイプは何か」は
  Customer-Supplier / Conformist / Shared-Kernel / ACL の 4 つしか提示しない。
  `Separate-Ways`（統合しない選択）は enum にも無い。
- **提案**:
  - session-guide の関係タイプ表を 8 語彙に拡張（各 1 行の判定基準つき）
  - term-glossary に OHS / PL / Partnership / Separate-Ways を追加
  - schema enum に `Separate-Ways` を追加（意図的な非統合を記録できるように）
- **コスト**: 極小（ほぼドキュメントのみ）

### 【P1-③】Pivotal Event（節目イベント）の一級市民化 ✅ 反映済み（2026-07-03）

- **ギャップ**: Big Picture EventStorming の古典テクニック。タイムラインを区切る節目イベント
  （例: 「注文が確定した」「商品が発送された」）は BC 境界候補の最有力な手がかりだが、
  DML に表現手段が無く、フェーズ 3→4.5 の BC 導出が「言語が変わる境界」だけに依存している。
- **提案**:
  - schema: `scenarios[].pivotal: true`（または brs[].evt 単位）を追加
  - フェーズ 3 完了時の問い: 「このタイムラインを大きく区切る節目イベントを 2〜4 個選ぶとしたらどれ？」
  - HTML §2 フロー図で縦の区切り線 or 強調描画
  - フェーズ 4.5 の BC 導出質問に「節目イベントの前後で言葉・責務が変わっていないか」を追加
- **コスト**: 中（schema 1 フィールド + ビルダー描画 + ガイド追記）

### 【P2-④】外部システムの一級表現

- **ギャップ**: session-guide はアクター種別に「外部システム」を挙げ、ACL の判断対象も
  実際には外部 SaaS が多いのに、DML では外部システムを内部 BC と区別して宣言できない
  （`bcType` enum は FEATURE/APPLICATION/SYSTEM/MICROSERVICE のみ。EventStorming の
  ピンク付箋に相当する表現が無い）。
- **提案**:
  - `bcType` に `EXTERNAL` を追加（or `contexts[].external: true`）
  - HTML §2/§6 で外部システムをピンク系の別スタイルで描画
  - 構造 check: 外部 context に `dn` として依存する内部 BC が rel（ACL/Conformist）未指定なら警告
- **コスト**: 中

### 【P2-⑤】Reverse Narrative チェック（逆順走査）— 意味チェック 7 観点目

- **ギャップ**: Brandolini の古典検証法「タイムラインを逆から辿り、各イベントの直前提条件が
  揃っているか確認する」が無い。causal-chain-completeness は前向き走査のみで、
  「このイベントが起きるために必要な事前イベント・データが存在するか」の後ろ向き検証が抜ける。
- **提案**: `references/checks/reverse-narrative.md` を追加（view は flow-causality を流用）。
  各フローの終端から entry へ逆順に「E_n が成立するには何が真である必要があるか →
  それは先行ステップで保証されているか」を評価。
- **コスト**: 小（checks md 1 枚。dmlctl 変更不要）

### 【P2-⑥】集約サイジングのヒューリスティックと競合質問

- **ギャップ**: 「一緒に変わるものをひとつの集約に」だけで、Vaughn Vernon の設計原則
  （集約は小さく／他集約は ID 参照／集約間は結果整合）と、ホット集約（ロック競合）の
  検出質問が無い。実セッションの decisions[]（capacity 所有など）で毎回同じ議論をしている。
- **提案**:
  - dml-spec §4 に「サイジング 3 原則」節を追加
  - session-guide 65〜80 分の集約導出に質問追加: 「この集約、同時に何人が書き換える？
    ピーク時に競合しない？」「他の集約を丸ごと抱えていないか（ID 参照で足りないか）」
  - 構造 check（機械化可能部分）: `agg_size_smell` — attrs 15 個超 or 参照 scenario 数が突出した AGG を報告
- **コスト**: 小〜中

### 【P2-⑦】EVENTUAL-TX の遅延許容（結果整合 SLA）の言語化

- **ギャップ**: SAME-TX vs EVENTUAL-TX の判定はあるが、EVENTUAL を選んだ後の
  「業務的にどれだけ遅れてよいか」（数秒？翌日バッチで十分？）を引き出す質問が無い。
  これは実装エージェントがキュー設計・リトライ設計を決める一級の判断材料。
- **提案**:
  - schema: `policies[].within: string`（任意・自然文。例: "5 分以内", "翌朝バッチで可"）
  - session-guide の POLICY マッピングに質問追加: 「この後続処理、業務的にはどれくらい
    遅れたら困りますか？」
  - HTML §2 の policy 付箋に within を小さく併記
- **コスト**: 小

### 【P3-⑧】Value Object の定義置き場

- **ギャップ**: `lang.vos` に英日ラベルはあるが、VO 自体の制約（例: HoldAmount は 0 以上・
  通貨単位固定）を書く場所が無く、attrs[].type から VO 名を参照しても定義に辿れない。
- **提案**: まずは `aggregates[].attrs[].note` 運用の明文化で凌ぎ、必要になったら
  トップレベル `vos[]`（name / ctx / constraints[]）を検討。
- **コスト**: 運用明文化なら極小／schema 化は中

### 【P3-⑨】ドメインサービスの表現

- **ギャップ**: どの AGG にも属さない複数集約横断の業務ロジック（例: 与信スコア計算）の
  置き場が無い。現状は qry か policy で代替しており、多くのセッションでは困っていない。
- **提案**: 実セッションで必要になった時点で検討（YAGNI）。それまでは dml-spec に
  「複数 AGG 横断の計算は qry（formula）で表現する」と明文化するだけに留める。

### 【P3-⑩】Opportunity（機会）付箋

- **ギャップ**: hotspot `[?]` は問題・迷い側のみで、Big Picture で拾える「改善機会・アイデア」
  の受け皿が無い。
- **提案**: `questions[]` に `kind: opportunity` を足す程度の軽量対応。優先度低。

## 優先順位の根拠

効果（モデル品質・後続の実装判断への影響）× コスト（schema/ビルダー変更の要否）で並べた。
P1 の 3 件はいずれも「戦略 DDD の空洞」を埋めるもの。特に ①② は schema が既に対応済みで
ファシリテーション導線を書くだけなので、次のセッション前に反映する価値が高い。
