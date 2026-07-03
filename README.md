# pocket-modeling

EventStorming／DDD のドメインモデリングを **対話で進めるためのファシリテータースキル一式** を抱えるナレッジリポジトリ。アプリケーションコードは持たず、AI（Claude Code）と人間がモデルを育てるための仕組みと、その生成物だけを管理する。

## 何ができるか

「このドメインを整理したい」と話しかけると、Claude Code が EventStorming の流儀でドメインイベント・コマンド・集約・ポリシー・リードモデル・境界づけられたコンテキストを会話から発見し、**DML（Domain Modeling Language、YAML）** に情報圧縮していく。DML から閲覧用の HTML が自動生成され、ストーリー・フロー図・意思決定ログなどが一望できる。

呼び出しの合図（例）:

- 「ドメインモデリングしたい」「イベントストーミングやろう」
- 「DDD で整理したい」「DML を育てたい」
- 既存 DML のリファイン、新機能のドメインモデル起こし

## 生成物は 2 種類だけ

| 種類 | パス | 役割 |
| --- | --- | --- |
| DML（真実源） | `docs/eventstorming/<session>.dml.yaml` | 手で書く／AI が育てる唯一のソース |
| HTML（派生物） | `dist/eventstorming/<session>.html` | DML から機械生成。`dist/` は gitignore 済み、**手編集しない** |

セッションは `eventstorming-YYYYMMDD-HHMM` 形式で保存する。

## パイプライン

DML → HTML の **片方向** パイプライン。AI も人間も DML 側だけを触る。

```
docs/eventstorming/*.dml.yaml ──┬──→ eventstorming_build.py ──→ dist/eventstorming/*.html
                                ├──→ validate_dml.py   (JSON Schema 構文検証)
                                └──→ dmlctl.py         (views / checks / set / add / remove)
```

`docs/eventstorming/*.dml.yaml` を Write/Edit すると PostToolUse hook（`.claude/settings.json`）が自動で HTML 再生成と Schema 検証を実行する。

## ディレクトリ構成

```
.
├── CLAUDE.md                     # Claude Code 向けの運用ガイド（開発者も必読）
├── docs/
│   ├── eventstorming/            # DML セッションファイル（真実源）
│   └── skill-improvements/       # スキル改善メモ
├── dist/eventstorming/           # 生成 HTML（gitignore）
└── .claude/skills/eventstorming-facilitator/
    ├── SKILL.md                  # ファシリテーション ワークフロー（9 フェーズ）
    ├── references/
    │   ├── dml.schema.yaml       # DML の JSON Schema（Draft 2020-12）
    │   ├── dml-spec.md           # DML の設計判断・哲学
    │   ├── checks/*.md           # 意味チェック 6 観点（LLM ベース）
    │   └── ...                   # quality-check / causal-check / session-guide ほか
    ├── scripts/
    │   ├── eventstorming_build.py  # DML → HTML レンダラ（全 9 セクション）
    │   ├── validate_dml.py         # Schema 構文検証
    │   ├── dmlctl.py               # 観点別スライス I/O・構造チェック
    │   └── dml_filters/            # views（15）/ checks（18）の実装
    ├── templates/event-flow.html
    └── examples/sample.dml.yaml
```

## セットアップ

リポジトリルートから実行。Python 3 と以下が必要:

```sh
pip install pyyaml jsonschema ruamel.yaml
```

- `pyyaml` / `jsonschema` — 検証・ビルド用
- `ruamel.yaml` — `dmlctl` の構造化編集（set/add/remove、コメント・引用形式を維持）用

## よく使うコマンド

```sh
SKILL=.claude/skills/eventstorming-facilitator/scripts

# 観点別スライス取得（コンテキスト節約。大きい DML は全文 Read しない）
python3 $SKILL/dmlctl.py views                                   # view 名一覧
python3 $SKILL/dmlctl.py view <file> --view=<name> [--ctx=... --name=...]

# 構造化編集
python3 $SKILL/dmlctl.py set    <file> --path=<a.b.c>   --value=<yaml-literal>
python3 $SKILL/dmlctl.py add    <file> --to=<list-path> --item=<yaml-literal>
python3 $SKILL/dmlctl.py remove <file> --path=<a.b.c>

# 識別子の横断検索 / 一括リネーム（用語統一・state 改名。--ctx で BC 内に限定可）
python3 $SKILL/dmlctl.py refs   <file> --name=<identifier>
python3 $SKILL/dmlctl.py rename <file> --from=<old> --to=<new> [--ctx=<bc>] [--dry-run]

# 構造チェック（LLM 不要）
python3 $SKILL/dmlctl.py checks                                  # check 名一覧
python3 $SKILL/dmlctl.py check <file> --all                      # 全観点を一括実行（clean/results サマリ）
python3 $SKILL/dmlctl.py check <file> --check=<name>             # 個別観点

# 検証 / ビルド（通常は hook が自動実行。手動は補助用途）
python3 $SKILL/validate_dml.py <file>.dml.yaml
python3 $SKILL/eventstorming_build.py <file>.dml.yaml
python3 $SKILL/eventstorming_build.py --all                      # 全件
python3 $SKILL/eventstorming_build.py --watch                    # 監視モード
```

## 2 段の検証

- **構文 validity** — `validate_dml.py` が JSON Schema で機械検証。Schema 通過は必要条件であって十分条件ではない
- **意味 validity** — 参照の実在・因果整合・モデル品質は `references/checks/*.md` の 6 観点を LLM（Agent tool）で 1 つずつチェックする。詳細は `references/quality-check.md`

## もっと知る

- 運用原則・命名規約・アーキテクチャ詳細 → [CLAUDE.md](./CLAUDE.md)
- ファシリテーションの進め方 → `.claude/skills/eventstorming-facilitator/SKILL.md`
- DML の構造と設計思想 → `references/dml-spec.md` ＋ `references/dml.schema.yaml`
