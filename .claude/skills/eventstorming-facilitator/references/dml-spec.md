# DML 記法仕様 — （→ `ddd-playbook.md` に統合）

本書が扱っていた**設計判断・記法哲学・慣習**は、DDD 概念軸で再編した [`ddd-playbook.md`](./ddd-playbook.md) に統合された。ルールの正典は playbook 側にあるので、そちらを参照すること。

- 構文 validity の機械検証は [`dml.schema.yaml`](./dml.schema.yaml)（JSON Schema Draft 2020-12）
- 検証: `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py docs/eventstorming/<session>.dml.yaml`
- フル例: [`../examples/sample.dml.yaml`](../examples/sample.dml.yaml)

## 旧 § → playbook 対応表

| 旧 dml-spec.md の節 | 統合先（`ddd-playbook.md`） |
|---|---|
| §0 記法の原則 | §1 記法の原則（横断ルール） |
| §1 インフラ系ドメインの扱い（BC 昇格 vs POLICY 留置）・`lang` 構造 | §9 境界づけられたコンテキスト |
| §2 SCENARIO の哲学（EVT 起点・actor・rules/why・errs/when・業務vs実装エラー・pivotal・qry・brs・内部 CMD） | §2 シナリオ／§3 不変条件・エラー／§4 コマンド／§5 ドメインイベント／§7 リードモデル |
| §3 POLICY の運用（SAME/EVENTUAL 判定・cmd 省略・bulk/qry・trgs・within/after・ガード条件・agg） | §6 ポリシー |
| §4 AGG の設計意図（トップレベル理由・フィールド役割・所有 BC 1 つ・transitions 初期化・意味整合） | §8 集約 |
| §5 HTML 描画との関係 | §12 フロー連鎖／各概念「検証観点」・HTML 描画は `scripts/RENDER_SPEC.md` |
| §6 `[?]` の慣習と decisions 昇格 | §11 意思決定「`[?]` の慣習と昇格」 |
| §7 検証の境界（構文 vs 意味） | §13 検証の境界 |
| §8 最小実例 | §2・§6 の記法例／フル例は `examples/sample.dml.yaml` |
| §9 フロー連鎖と decisions の哲学（参照規則・kind・decisions フィールド・「決められないとき」） | §12 フロー連鎖／§11 意思決定 |
