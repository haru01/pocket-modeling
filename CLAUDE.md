# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリは何か

EventStorming／DDD ドメインモデリングのファシリテータースキル一式を抱えるナレッジリポジトリ。アプリケーションコードは持たず、生成物は次の 2 種類のみ：

- `docs/eventstorming/<session>.dml.yaml` — DML（Domain Modeling Language、YAML）で書かれたドメインモデルのソース・オブ・トゥルース
- `dist/eventstorming/<session>.html` — DML から機械生成される閲覧用 HTML（`dist/` は gitignore 済み）

中身のスキルは `.claude/skills/eventstorming-facilitator/` に集約。詳細仕様は `.claude/skills/eventstorming-facilitator/SKILL.md` と `references/*`、特に `dml-spec.md` と `dml.schema.yaml` を参照。

## 最重要の運用原則

- **DML が唯一の真実源**。HTML は派生物なので絶対に手で編集しない。`.md` 入力サポートは v5 で廃止済み（YAML-only）
- **大きい DML を全文 Read/Edit しない**。`scripts/dmlctl.py` 経由で観点別スライスだけ読み書きしてコンテキスト消費を抑える。直接 `Edit` も可だが小さな変更でも dmlctl を優先
- **PostToolUse hook が自動で再生成・検証**する（`.claude/settings.json` 参照）。`docs/eventstorming/*.dml.yaml` を Write/Edit すると以下が走る：
  1. `eventstorming_build.py <path>` で `dist/eventstorming/*.html` を再生成
  2. `validate_dml.py <path>` で JSON Schema 検証（違反は stderr に出力し exit 2）
- AI は HTML を直接編集しない。チャットに DML 全文を流さない（フェーズ完了テンプレで抜粋のみ）

## YAML キーの命名規約

**トップレベルは略語禁止**：`contexts` / `aggregates` / `scenarios` / `policies` / `queries` / `decisions` / `questions` / `actions` / `narratives` / `domains` / `session`。

**ネストの短いキーは略語維持**：`ctx` / `aggs`（`contexts[].aggs` の AGG 名簿）／`cmds` / `evts` / `pols` / `qrys` / `vos`（`contexts[].lang` 内のカテゴリ別辞書）／`trg` / `trgs` / `brs` / `brMode` / `up` / `dn` / `rel` など。これは履歴経緯ではなく現行の意図的な設計（読みやすさと識別子の短さのトレードオフ）。schema 冒頭コメントの「命名方針」に明記。

新規 DML を書く / 既存 DML を編集するときはこの規約に必ず合わせる。

## 主要なコマンド

すべてリポジトリルートから実行。Python 3 と `pyyaml` / `jsonschema` / `ruamel.yaml`（dmlctl の set/add/remove 用）が必要。

```sh
# DML 観点別スライス取得（コンテキスト節約）
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py views          # view 名一覧
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py view <file> --view=<name> [--name=... --id=... --ctx=...]

# DML 構造化編集（コメント・引用形式を維持）
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py set    <file> --path=<a.b.c>   --value=<yaml-literal>
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py add    <file> --to=<list-path> --item=<yaml-literal>
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py remove <file> --path=<a.b.c>

# 構造チェック（LLM 不要・全観点は `dmlctl checks` で一覧）
python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py check <file> --check=<name>

# 単体検証 / HTML ビルド（hook が自動で呼ぶので手動実行は補助用途）
python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py <file>.dml.yaml
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <file>.dml.yaml
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --all       # 全件
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py --watch     # 監視モード
python3 .claude/skills/eventstorming-facilitator/scripts/eventstorming_build.py <file> --artifact --copy  # claude.ai Artifact 用、macOS
```

意味チェック（観点別 LLM 起動）は Agent tool で `.claude/skills/eventstorming-facilitator/references/checks/*.md` の 6 観点を 1 つずつ呼ぶ。詳細は `references/quality-check.md`。

## アーキテクチャの押さえどころ

DML → HTML の片方向パイプラインで、AI／人間は DML 側のみを触る。

```
docs/eventstorming/*.dml.yaml  ──┐
                                  ├──→ eventstorming_build.py ──→ dist/eventstorming/*.html
.claude/.../templates/event-flow.html  ┘
                                  │
                                  ├──→ validate_dml.py (JSON Schema)
                                  └──→ dmlctl.py (views / checks / set / add / remove)
```

- `eventstorming_build.py` — DML から HTML 全 9 セクション（ストーリー／フロー図／次のアクション／オープンクエスチョン／意思決定ログ／コンテキスト候補／集約候補／リードモデル候補／DML 全文ハイライト）を組み立てる 1,800 行超のレンダラ。Mermaid・自前 SVG・YAML シンタックスハイライトを内蔵。v8 で旧 §1 ハッピーパス＋§2 代替シナリオを §1 ストーリーに統合
- `validate_dml.py` — `references/dml.schema.yaml`（JSON Schema Draft 2020-12）で **構文** validity を機械検証。空 YAML や非 dict は「未記述」として違反扱いしない（進行中セッション許容）
- `dmlctl.py` + `dml_filters/views.py` + `dml_filters/checks.py` — AI コンテキスト圧迫を避けるため、観点別スライスの I/O と純構造チェック（LLM 不要）を提供。13 view・10 check が登録済み
- 意味 validity（参照の実在・因果整合・モデル品質）は LLM ベースの `references/checks/*.md` が担う。**スキーマ通過は必要条件であって十分条件ではない**

## DML の構造（要点）

JSON Schema は `.claude/skills/eventstorming-facilitator/references/dml.schema.yaml`、設計判断・哲学は `dml-spec.md` を真実源として参照すること。要点だけ：

- トップレベルは object、必須キー無し（空 `{}` も valid）
- モデル本体: `contexts[]` / `aggregates[]` / `scenarios[]` / `policies[]` / `decisions[]`（v6 で `flows[]` 廃止）
- 散文系: `session` / `narratives[]` / `actions[]` / `questions[]` / `queries[]` / 任意 `domains[]`（v8 で `story` 廃止して `narratives[]` に統合）
- `narratives[]` は `kind: happy` / `kind: alt` で散文を区別（kind 必須）。`kind: happy` は 0 or 1 件（`narrative_happy_unique` で検出）
- フロー連鎖は `narratives[].entry` を起点に `scenarios[].next` / `brs[].terminal` で表現（旧 `flows[]` の役割を分散保持）
- `aggregates[]` は v3 でトップレベル化、`contexts[].aggs` は名前リストだけの軽量名簿（双方向参照）
- `scenarios[].name` のみ日本語（アクター＋行為）。それ以外の識別子は英語 PascalCase または `lowercase-with-hyphen`
- `policies[]` は EVENTUAL-TX 専用。SAME-TX 分岐は発行元 scenario の `brs` で書く
- `decisions[].options[]` は `name`（英語 slug 推奨）と任意の `label`（日本語）で「日本語 (english-id)」表示

## ファシリテーション セッションの保存先

- 進行中 / 履歴: `docs/eventstorming/eventstorming-YYYYMMDD-HHMM.dml.yaml`
- 生成 HTML: `dist/eventstorming/eventstorming-YYYYMMDD-HHMM.html`（gitignore 済み）
- スキル改善メモ: `docs/skill-improvements/`
