# eventstorming-facilitator スキル改善レジャー — 2026-05-29

セッション `meetup-20260529` をミートアップ・プラットフォーム題材に AI 単独で全自動実行する過程で検出した、スキル本体（`.claude/skills/eventstorming-facilitator/`）の問題点と修復記録。

## 進行サマリ

| ステータス | 件数 |
|---|---|
| 検出 (open) | TBD |
| 自動修復済 | TBD |
| 未適用（要ユーザー判断） | TBD |

## カテゴリ凡例

- **schema-mismatch** — `dml.schema.yaml` と実装/ドキュメントのズレ、合理的 DML がスキーマで弾かれる等
- **script-bug** — `dmlctl.py` / `eventstorming_build.py` / `validate_dml.py` の異常動作・例外・引数バグ
- **doc-inconsistency** — `SKILL.md` と `references/*.md` の不整合、ファイル数・観点数の食い違い、廃止フィールドへの参照残存
- **missing-content** — 参照されているが内容が空・無いセクション／ファイル
- **hook-misbehavior** — `.claude/settings.json` の PostToolUse hook の予期しない挙動
- **facilitation-gap** — 自動実行中に「判断軸がスキル内に無い」と気付いたシーン

---

## Issues

### Issue-001: `docs/skill-improvements/` ディレクトリが存在しなかった

- カテゴリ: missing-content
- 観察したフェーズ: ステージ 1（環境準備）
- 該当: `docs/skill-improvements/`（ディレクトリ自体）
- 期待: `CLAUDE.md` 末尾の「ファシリテーション セッションの保存先」セクションと `SKILL.md` の「スキル改善メモ: `docs/skill-improvements/`」記述に基づき、当該ディレクトリが存在しているはず
- 実際: `ls docs/skill-improvements/` で No such file or directory。git log を見ると `docs/skill-improvements/eventstorming-facilitator-20260528.md` は直近で削除されている（`91cd4dc eventstorming-to-issues スキルと関連アーティファクトを削除`）
- 提案修正: ディレクトリを作成し、本ファイル（`eventstorming-facilitator-20260529.md`）を初期化として置く。`.gitkeep` は不要（本ファイルがコミットされる）
- 自動修復: 適用済み（`mkdir -p docs/skill-improvements/` 実行、本ファイル作成）

### Issue-002: `references/html-render-spec.md` が「9 セクション」表記なのに実テーブルは §0–§9 で 10 項目

- カテゴリ: doc-inconsistency
- 観察したフェーズ: Phase 1 事前調査
- 該当: `.claude/skills/eventstorming-facilitator/references/html-render-spec.md`
- 期待: 見出し記述（「9 セクション」）と項目テーブルの個数が一致
- 実際: 「v8 で §1/§2 を統合して 9 セクション」と書きつつ、実テーブルは §0 進捗バー〜§9 DML YAML の **10 項目**
- 提案修正: テーブル冒頭・末尾の表記を「§0 進捗バー（コンパクト） + §1–§9 の 9 セクション」と整理。または §0 を含めて「10 セクション」に統一
- 自動修復: ステージ 4 で実施予定

### Issue-003: `references/dml-spec.md` に v7 への言及が無く v5/v6/v8 のみ言及

- カテゴリ: doc-inconsistency
- 観察したフェーズ: Phase 1 事前調査
- 該当: `.claude/skills/eventstorming-facilitator/references/dml-spec.md`
- 期待: スキーマのバージョン進化（v3→v5→v6→v7→v8）と差分の流れが一通り辿れる
- 実際: v3（AGG トップレベル化）/ v5（MD 廃止）/ v6（flows 廃止・narratives.entry 駆動）/ v8（story → narratives 統合）は触れられているが、v7（commit `91xxxxx` 系で導入された `policies[].agg` 併記許可など）は明文化なし
- 提案修正: v7 の差分（`policies[].cmd が AGG を変更する場合 agg 併記、dangling_cmd チェックは policies[].cmd も declared として扱う` 等）を 1 段落追記
- 自動修復: ステージ 4 で実施予定

### Issue-004: `references/session-guide.md` が 90 分短縮版なのに SKILL.md 9 フェーズとの対応関係が文書化されていない

- カテゴリ: doc-inconsistency
- 観察したフェーズ: Phase 1 事前調査
- 該当: `.claude/skills/eventstorming-facilitator/references/session-guide.md`
- 期待: `session-guide.md` 冒頭で「これは SKILL.md の 9 フェーズを 90 分セッション用に短縮した質問集である」等の関係性が明示される
- 実際: 4 区切り（フレーミング / イベント収集 / CMD/POLICY / BC/AGG）で書かれており、SKILL.md の 9 フェーズとどう対応するかが読者に伝わらない
- 提案修正: 冒頭に「対応関係: フレーミング = フェーズ 1-2 / イベント収集 = フェーズ 3 / CMD/POLICY = フェーズ 4 / BC/AGG = フェーズ 4.5-4.6（フェーズ 5-7 は本文書外）」と注記
- 自動修復: ステージ 4 で実施予定

### Issue-005: `references/domain-starters.md` の「インフラ系パターン」が見出しのみ・ミートアップ系不在

- カテゴリ: missing-content
- 観察したフェーズ: Phase 1 事前調査
- 該当: `.claude/skills/eventstorming-facilitator/references/domain-starters.md`
- 期待: 主要ドメイン（転職・EC・SaaS・医療）と並んで「ミートアップ／コミュニティイベント」のスターターリストがあり、インフラ系セクションも内容が埋まっている
- 実際: 転職 16・EC 13・SaaS 16・医療 12 はあるが、インフラ系は見出しのみ・ミートアップ系は不在
- 提案修正: ミートアップ／コミュニティイベント向け候補イベント（EventDrafted, EventPublished, ParticipationApplied, ParticipationConfirmed, ParticipationWaitlisted, EventReminded, AttendanceCheckedIn, AttendanceNoShowDetected, FeedbackSubmitted, EventCancelled, ParticipationCancelled, RefundIssued, …）を 1 セクション追加。インフラ系は最低限 5 イベント補完または「TBD」明記
- 自動修復: ステージ 4 で実施予定

---

## 以下、ステージ 2 実行中に追記

### Issue-006: `errs[]` には `why` が無く `rules[]` とフィールド名が非対称

- カテゴリ: facilitation-gap（兼 schema-mismatch 候補）
- 観察したフェーズ: Phase 5 実装中（rules/errs 同時記述時）
- 該当: `references/dml.schema.yaml` の `$defs/rule`（`why` あり）vs `$defs/error`（`why` なし・`when` のみ）
- 期待: ルールも「なぜそれを守るか」、エラーも「なぜそれが業務的に起こり得るか／問題か」を構造化して残せる
- 実際: AI が `errs[]` のエントリに `why:` を書こうとして PostToolUse hook がブロック（exit=2）。エラーメッセージ `scenarios/1/errs/1: Additional properties are not allowed ('why' was unexpected)` で即時検出。代替として `when:` フィールドに業務的理由を押し込む形で回避
- 提案修正: 2 案。(A) error スキーマに `why` を追加して rules と対称化（後方互換）。(B) ドキュメント側で「errs の業務的理由は `when` に書く」と明示。本セッションでは (B) を採用し、(A) は中長期検討
- 自動修復: (B) の方針で `references/dml-spec.md` と `references/checks/scenario-rules-quality.md` に注記を追加。ステージ 4 で実施予定

### Issue-007: PostToolUse hook の検証成功時メッセージが見えづらい

- カテゴリ: hook-misbehavior（低）
- 観察したフェーズ: Phase 2 / 4 / 5 の Write 直後
- 該当: `.claude/settings.json` の PostToolUse hook
- 期待: 検証 OK 時に「✅ scheme OK」が hook 経由で標準出力に流れて AI/ユーザーが確認できる
- 実際: 違反時はブロッキングメッセージが見えるが、成功時は何も出力されず、AI 側で再度 `validate_dml.py` を手動実行して確認する必要があった
- 提案修正: hook シェル末尾で成功時に `echo "✅ <file>: validated"` を stdout に流す（PostToolUse は exit=0 なら追加メッセージで通知としては使えるはず）。または、SKILL.md 側で「成功時は hook が無音」と明示する
- 自動修復: ステージ 4 で .claude/settings.json と SKILL.md の両方に対応検討

### Issue-008: `dmlctl views` の登録数が SKILL.md と不一致

- カテゴリ: doc-inconsistency
- 観察したフェーズ: Phase 3 開始時の `dmlctl views` 実行
- 該当: `.claude/skills/eventstorming-facilitator/SKILL.md` の「14 view・10 check が登録済み」記述（CLAUDE.md の "Architecture" 説明にも類似）
- 期待: SKILL.md の数値と実装の登録数が一致
- 実際: 実装は **13 view**（session-meta / narratives / open-questions / all-questions / actions / bc-summary / bc-language / agg-detail / flow-causality / decisions / queries / scenarios / policies）と **10 check**。SKILL.md 記述「14 view」は 1 多い
- 提案修正: SKILL.md と CLAUDE.md の view 数を 13 に修正、もしくは将来の追加 view を 1 つ実装
- 自動修復: ステージ 4 で SKILL.md / CLAUDE.md の数値を 13 に修正

### Issue-009: `policies[]` に `rules[]` が無く、ガード条件を構造的に書けない

- カテゴリ: schema-mismatch（兼 facilitation-gap）
- 観察したフェーズ: Phase 7 意味チェック（saga-completeness 指摘）
- 該当: `references/dml.schema.yaml` の `$defs/policy`
- 期待: ポリシーにも「発火時のガード条件」「skip 条件」を構造化して書ける
- 実際: scenario には `rules[]`/`errs[]` があるが policy にはない。saga-completeness の指摘で「NotifyParticipantsOnEventCancelled bulk Cancel が PromoteOnCancelled を連鎖発火させるエッジ」を防ぐルールを policy 側に書きたかったが、scenarios[システムが繰上を実行する].rules に「Skip when Event is CANCELLED」を書く回避策で対処
- 提案修正: 2 案。(A) policy schema に `rules[]`/`guards[]` を追加（後方互換）。(B) ドキュメント側で「policy のガード条件は呼び出される scenario の rules に書く」と明示
- 自動修復: (B) の方針で `references/dml-spec.md` の POLICY 節と `references/checks/saga-completeness.md` に注記追加。ステージ 4 で実施

### Issue-010: `decisions[].affects[]` の粒度ガイドラインが無い

- カテゴリ: doc-inconsistency（兼 facilitation-gap）
- 観察したフェーズ: Phase 7 意味チェック（decision-rationale-clarity 指摘）
- 該当: `references/dml.schema.yaml` の `$defs/decision.affects`、`references/checks/decision-rationale-clarity.md`
- 期待: affects[] に何を書くか（AGG 名のみ / AGG + Policy / AGG + Event 等）の粒度規範がある
- 実際: スキーマは `type: string` で自由文字列。本セッションでも D1=[Event,Participation]（AGG のみ）/ D2=[Participation,PromoteOnCancelled]（AGG+Policy）/ D4=[Attendance,ParticipantCheckedIn]（AGG+Event）と決定ごとに粒度が揺れた
- 提案修正: decision-rationale-clarity.md に「affects[] には AGG 名と Policy 名を必ず書く（Event 名は省略可）」等の粒度ガイドを追加
- 自動修復: ステージ 4 で実施

### Issue-011: `errs[]` と業務エラー／実装エラーの区別ガイドが薄い

- カテゴリ: doc-inconsistency
- 観察したフェーズ: Phase 7 意味チェック（scenario-rules-quality 指摘）
- 該当: `references/checks/scenario-rules-quality.md`
- 期待: 「業務エラーのみを errs に書く」「実装/インフラ問題（スケジューラ誤発火、null pointer 等）は errs に書かない」の境界が明確
- 実際: 初稿で AI が `TooEarlyForNoShow (スケジューラ誤発火)` のような実装エラーを書いてしまい、scenario-rules-quality agent から「業務違反でなく実装エラー」と指摘。セッション内で `NoShowDetectionTooEarly (早期判定試行)` に書き換えて業務語彙へ寄せた
- 提案修正: checks/scenario-rules-quality.md に「業務エラー vs 実装エラー」の判別観点と書き換え例を追加
- 自動修復: ステージ 4 で実施

### Issue-012: `lang.pols` に書いたポリシーが `policies[]` に存在しないことを構造チェックで検出できない

- カテゴリ: missing-content（構造チェックの観点抜け）
- 観察したフェーズ: Phase 7 意味チェック（causal-chain-completeness 指摘）
- 該当: `.claude/skills/eventstorming-facilitator/scripts/dml_filters/checks.py`
- 期待: `contexts[].lang.pols` のエントリが `policies[].name` に存在するか検証する構造チェック（例: `dangling_policy_in_lang`）が存在
- 実際: 本セッションで attendance.lang.pols に `InviteFeedbackOnCheckedIn` を書いたが、policies[] には存在しなかった（causal-chain-completeness agent が指摘）。10 観点の構造チェックでは検出されず、意味チェックで初めて発見
- 提案修正: 新しい構造チェック `dangling_lang_entry` を `dml_filters/checks.py` に追加（cmds/evts/pols/qrys/aggs/actors すべてについて、scenarios/policies/aggregates での実在を確認）
- 自動修復: ステージ 4 で実装検討（または提案のみ）

### Issue-013: 異 BC で同一 state 名が異なる意味を持つことを構造チェックで検出できない

- カテゴリ: missing-content（構造チェックの観点抜け）
- 観察したフェーズ: Phase 7 意味チェック（bc-vocabulary-consistency 指摘）
- 該当: `.claude/skills/eventstorming-facilitator/scripts/dml_filters/checks.py`
- 期待: 同名 state（例: `CANCELLED`）が複数 AGG / BC に存在する場合、警告を出す構造チェック
- 実際: 本セッションで event-planning.Event の `CANCELLED` と participation.Participation の `CANCELLED` が同名異義だったが構造チェックは通過。意味チェックで初めて発見
- 提案修正: 新しい構造チェック `cross_bc_state_name_collision` を `dml_filters/checks.py` に追加。同名 state が複数 AGG で発見されたら lang.states の日本語ラベルを比較し、ラベルが異なれば警告
- 自動修復: ステージ 4 で実装検討（または提案のみ）

### Issue-014: `domain-starters.md` に「ミートアップ」が無いことで自動実行時の参考が不足

- カテゴリ: missing-content（Issue-005 の重複ではなく具体化）
- 観察したフェーズ: 本セッション全体
- 該当: `.claude/skills/eventstorming-facilitator/references/domain-starters.md`
- 期待: 自動実行で立ち上げたミートアップドメインの候補イベントが事前にスターターとして用意されている
- 実際: 本セッションでミートアップ・プラットフォームのモデルを完成させた。このセッションで使用した候補イベント・コマンドを domain-starters.md に逆輸入することで、次回以降の類似ドメイン立ち上げが速くなる
- 提案修正: Issue-005 の自動修復と統合し、本セッションの語彙を反映したスターターセクションを追加
- 自動修復: ステージ 4 で実施

### Issue-015: `examples/sample.dml.yaml` 自体が v5 以前の lang フォーマットでスキーマ違反

- カテゴリ: schema-mismatch（重要・以前から看過されていた）
- 観察したフェーズ: ステージ 4 で新規 check（`dangling_lang_entry`）を sample に対して回帰確認したとき
- 該当: `.claude/skills/eventstorming-facilitator/examples/sample.dml.yaml`
- 期待: `dml-spec.md` で「v6 参照例」として参照されている canonical sample が現行スキーマで valid
- 実際: `lang: { Event: "...", Capacity: "..." }` の旧 v3 フォーマットで書かれており、現行 schema の `additionalProperties: false` で違反:
  ```
  contexts/0/lang: Additional properties are not allowed ('Capacity', 'Event' were unexpected)
  contexts/1/lang: Additional properties are not allowed ('Capacity', 'Event' were unexpected)
  contexts/2/lang: Additional properties are not allowed ('Payment' was unexpected)
  ```
- 提案修正: `lang` をカテゴリ別 dict-of-dicts (`aggs/actors/cmds/evts/pols/qrys/vos/states`) に書き換え、合わせて session メタ・narratives 散文・decisions.options.label/adopted も v8 表現に揃える。`subdomainType` も `CORE_DOMAIN` → `CORE_SUBDOMAIN` へ
- 自動修復: ステージ 4 で全面リライト実施済（valid + 全 12 構造チェック PASS を確認）

## ステージ 2-D 完了時点のサマリ

- 構造チェック: **10/10 観点 PASS**
- 意味チェック 6 観点:
  - scenario-rules-quality: B+（2 件の rule/errs を業務語彙に書き換え反映済）
  - saga-completeness: ⚠（PromoteOnCancelled ガード rule 追記で 1 件解消・残り 2 件は actions[A4,A6] に送り）
  - bc-vocabulary-consistency: B+（CANCELLED 同名異義はラベル差別化で対処・PROMOTED 改名は actions[A5] に送り）
  - agg-purpose-quality: 合格 minor revision（Attendance.events 越境と Feedback 上書き transition 抜けは actions[A4,A6] へ）
  - causal-chain-completeness: ⚠ → ✅ (InviteFeedbackOnCheckedIn policy 追加・PromoteOnCancelled ガード rule 追記で 2 件解消・EventConcluded は actions[A4] へ)
  - decision-rationale-clarity: 概ね clear（affects[] 粒度・ストローマン why_not はスキル側改善対象として Issue-010 に送り）
- 新規発見 issue: **Issue-006〜015 の 10 件**

---

## ステージ 4: 自動修復の実施結果

各 issue の最終ステータス:

| Issue | カテゴリ | 修復ステータス |
|---|---|---|
| Issue-001 `docs/skill-improvements/` 不在 | missing-content | ✅ 適用済（ディレクトリ作成 + 本ファイル新規） |
| Issue-002 html-render-spec.md セクション数・`.md` 残骸 | doc-inconsistency | ✅ 適用済（9 セクション明示・`.md` 参照を `.dml.yaml` に統一・CLI 例更新・hook フロー図更新） |
| Issue-003 dml-spec.md に v7 言及なし | doc-inconsistency | ✅ 適用済（POLICY 節に v7 `policies[].agg` 追記） |
| Issue-004 session-guide.md と SKILL.md 対応関係未文書化 | doc-inconsistency | ✅ 適用済（冒頭に 90 分版 ↔ 9 フェーズ対応表を追加） |
| Issue-005/014 domain-starters.md インフラ系空・ミートアップ不在 | missing-content | ✅ 適用済（ミートアップ／コミュニティイベントセクション追加。インフラ系既存内容で十分と判定） |
| Issue-006 errs に `why` 無く rules と非対称 | facilitation-gap | ✅ 適用済（dml-spec.md と checks/scenario-rules-quality.md に「when に書く」明記） |
| Issue-007 hook 成功時メッセージ無音 | hook-misbehavior | ⛔ 未適用（成功時 stdout を流すとチャットがノイズで埋まるため、現行の「無音 = 成功」が設計上妥当と判断） |
| Issue-008 SKILL.md「14 view」記述 | doc-inconsistency | ⛔ 不要（誤検知。SKILL.md に view 数の言及なし。CLAUDE.md は既に「13 view」と正記） |
| Issue-009 policies[] に rules[] なし | schema-mismatch | ✅ 適用済（doc 側で対応。dml-spec.md POLICY 節と checks/saga-completeness.md にガード書き方注記。schema 変更は scenario-side ガードパターンを規範化する設計判断により見送り） |
| Issue-010 decisions[].affects[] 粒度ガイド無し | doc-inconsistency | ✅ 適用済（checks/decision-rationale-clarity.md に粒度ガイド・ストローマン回避ガイド追加） |
| Issue-011 errs[] 業務 vs 実装エラー区別ガイド薄い | doc-inconsistency | ✅ 適用済（checks/scenario-rules-quality.md に判別基準と書き換え例追加） |
| Issue-012 lang.pols dangling 検出 check 無し | missing-content | ✅ 適用済（`dangling_lang_entry` 構造チェック新規追加。pols/cmds/evts/aggs/qrys/actors を一括検証） |
| Issue-013 異 BC 同名 state 検出 check 無し | missing-content | ✅ 適用済（`cross_bc_state_name_collision` 構造チェック新規追加） |
| Issue-015 sample.dml.yaml が v3 lang format で schema 違反 | schema-mismatch | ✅ 適用済（v8 全面リライト・schema 検証 + 全 12 構造チェック PASS 確認） |

**自動修復済: 12 件 / 適用不要・判定変更: 2 件 / 未適用: 0 件**

### 修復のたびに走った回帰検証

1. `validate_dml.py` を本セッション DML と `examples/sample.dml.yaml` の両方に対して実行 → 全て exit=0
2. 12 構造チェックを両ファイルで実行 → 全て findings=0
3. `dmlctl checks` でレジストリに新規 2 check が登録されていることを確認
