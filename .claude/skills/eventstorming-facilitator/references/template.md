# EventStorming 風味のドメインモデリング - {{ドメイン名}}

- Session: {{eventstorming-YYYYMMDD-HHMM}}
- Domain: {{domain}}
- Status: **{{ステータス}}**
- Goal: {{ゴール}}
- HTML ビュー: [../../dist/eventstorming/{{eventstorming-YYYYMMDD-HHMM}}.html](../../dist/eventstorming/{{eventstorming-YYYYMMDD-HHMM}}.html) （Python ビルダーが自動生成する派生ファイル）
- DML: [./{{eventstorming-YYYYMMDD-HHMM}}.dml.yaml](./{{eventstorming-YYYYMMDD-HHMM}}.dml.yaml) （モデル本体・純 YAML。**モデル唯一の真実源**）

> このテンプレートは `.md` 側のセクション構成を示す。**§3（フロー）／§6（意思決定ログ）／§8（集約）の本文はビルダーが `.dml.yaml` から HTML を自動生成するため、`.md` 側には書かない**（注記のみ）。**§7 コンテキスト候補の LANGUAGE / 依存方向も DML `ctxs[].lang` / `up` / `dn` から生成**。
>
> セクション順は **「物語（§1〜§3）→ 次のアクション（§4・読者の次の動き）→ 横断課題（§5〜§6: 質問・決定）→ モデル層（§7〜§9: BC/AGG/QRY）→ メタ（§10: DML）」**。glossary（語彙の英→日変換）は HTML 上に独立セクションを持たず、DML `ctxs[].lang` を全 BC 走査してフロー図ラベルなどに機械的に適用される。

---

## 1) Happy Path Story

{{主人公（ユーザー名・ペルソナ）}}は、{{課題・状況}}を抱えていた。

{{ハッピーパスを辿る400〜600字の短編小説。ユーザーが感じる体験・感情・気づきを中心に。
システム内部の実装詳細（コマンド名・集約・ポリシー）は描かない。
目的達成の喜びや安心感が伝わる場面で締めくくる。}}

---

## 2) 代替シナリオ

### {{シナリオ名（例：主催者がイベントを中止する）}}

{{例外フローの短いストーリー（100〜200字程度）。ユーザー視点で何が起きたかを描く。図解は §3 がビルダーにより自動生成される。}}

---

## 3) Event Walkthrough

> **DML 自動生成セクション**。本文は書かない。HTML §3 は `.dml.yaml` の `flows[]`（`id`/`title`/`kind`/`steps[]`）と `scs[]`/`pols[]` を解決して Big Picture グリッド形式（時系列=横、BC=縦、付箋色分け）にレンダリングされる。フロー記述ガイドは `references/dml-spec.md` §9 参照。

---

## 4) 次のアクション

- {{action 1}}
- {{action 2}}

> 読者（特にステークホルダー）がドキュメントを読んだあと **何をすればよいか** を最上部近くに示す。技術詳細（§5 以降）はオプショナルに読める構造。

---

## 5) オープンクエスチョン

- Q1. {{質問}} — 決まると何が変わるか: {{影響}}
- Q2. {{質問}} — 決まると何が変わるか: {{影響}}

クローズ済み:
- [CLOSED] Q0. {{質問}} → {{解決内容}}

> 因果チェック（causal-check）の自動検出結果は、本セクション末尾に `### 因果チェーン（自動検出）` 見出しで追記される。**自動生成セクションのため手編集禁止**。DML を更新したうえで causal-check-agent を再実行し、その出力でブロックを置換する。

---

## 6) 意思決定ログ

> **DML 自動生成セクション**。本文は `.md` には書かない。`.dml.yaml` の `decisions[]`（`id`/`topic`/`chosen`/`options[]`/`affects[]`、各 option の `why`/`why_not`）から HTML §6 が **採用（緑）／不採用（灰・取り消し線）の比較カード** を自動描画する。`decisions[]` が空なら HTML §6 は見出しごと非表示。書き方ガイドは `references/dml-spec.md` §9 参照。

---

## 7) コンテキスト候補

> **命名規約**: `### english-slug（日本語名）` 形式を必須とする（例: `### store-front（店舗フロント）`）。HTML レンダー時にこの全体が `<h3>` に表示される。
>
> **LANGUAGE / 依存方向（UPSTREAM/DOWNSTREAM）は DML `ctxs[].lang` / `up` / `dn` が唯一の真実源**。`.md` 側には書かない（重複管理を避けるため）。ビルダーが DML から merge して HTML §7 に描画する。`.md` 側には散文（境界の理由・含むシナリオ・目的・背景・制約）のみ書く。さらに `ctxs[].lang` には本 BC で扱う AGG/Actor/CMD/EVT/QRY 等の英→日辞書を集約することで、glossary_index も自動生成される。

### {{english-slug}}（{{日本語名}}）

- 境界の理由: {{なぜここでBCが分かれるか}}
- 含むシナリオ: {{scenario-1}}, {{scenario-2}}

#### 目的

{{この BC が事業上担う価値（任意・1〜2文）。AGG レベルの「目的」を束ねる戦略的判断を 1 文で。}}

#### 背景

{{なぜこの境界で BC を切るか・現状の痛み（任意・1〜3文）。}}

#### 制約

- {{BC レベルで横断的に守る非機能・法令・運用上の制約。任意・複数可。}}

---

## 8) 集約候補

> **DML 自動生成セクション**。本文（属性・状態遷移・不変条件・エラーケース）は `.md` には書かない。`.dml.yaml` の `aggs[]`（`name`/`ctx`/`purpose`/`background`/`constraints[]`/`states`/`transitions[]`/`attrs[]`/`events[]`）と該当 `scs[].rules[]`/`scs[].errs[]` を解析して HTML §8 が **属性表 / イベントペイロード表 / 不変条件（緑）/ エラーケース（赤）/ 状態遷移** を自動描画する。命名規約と書き方ガイドは `references/dml-spec.md` §4 参照。

`.md` 側に補足の散文コメントを書きたい場合のみ、以下の形で追記する（必須ではない）。

### {{EnglishName}}（{{日本語名}}）

- コンテキスト: `{{context-slug}}`
- 関連シナリオ: `{{scenario-1}}`, `{{scenario-2}}`

{{必要なら散文コメント（DML には収まらない設計メモなど）。属性・不変条件・エラー・状態遷移は DML 側で管理。}}

---

## 9) リードモデル候補

### {{QRYName}}（{{日本語名}}）
- **利用者**: {{アクター名 または ポリシー名}}
- **目的**: {{何を確認して何を決めるか（1行）}}
- **ソース**: {{どの集約・BC からデータを取るか}}
- **算出**: {{計算式・取得条件・ソート順など（単純ルックアップなら省略可）}}

---

## 10) DML

DML 全文は別ファイル [`./{{eventstorming-YYYYMMDD-HHMM}}.dml.yaml`](./{{eventstorming-YYYYMMDD-HHMM}}.dml.yaml)（YAML 直書き・フェンス不要）に保持する。`ctxs` / `aggs` / `scs` / `pols` の 4 リスト（任意で `domains` / `flows` / `decisions`）、識別子は英語。トップレベル `aggs[]` に AGG 詳細（`name`/`ctx`/`purpose`/`background`/`constraints`/`states`/`transitions`/`attrs`/`events`）を集約し、`ctxs[].aggs` は AGG 名（PascalCase 文字列）の軽量名簿として保持する。`ctxs[].lang` には本 BC で扱う AGG/Actor/CMD/EVT/QRY 等の英→日辞書を集約する（glossary_index がここから自動生成される）。構文の機械検証は `references/dml.schema.yaml`、設計判断・哲学は `references/dml-spec.md`、フル参照例は `examples/sample.dml.yaml`。HTML §10 にはこの `.dml.yaml` の内容が描画される。

> このセクションは `.dml.yaml` へのリンク参照のみとし、DML 本文（YAML）は **埋め込まない**。
