# dmlctl 書き込み効率の改善（2026-05-31）

医療予約ドメインのモデリングセッション（`eventstorming-20260531-0748`）で観測した
書き込み側のトークン浪費を分析し、運用ルール（A）と dmlctl 改修（B）に落とした記録。

## 背景：観測された浪費

「DML を直接 I/O させない（dmlctl 経由のみ）」制約は機能している：

- PreToolUse フック `block_direct_dml.py`（`BLOCKED_TOOLS = {Read, Edit, Write}`）が
  DML への直接 Read/Edit/Write を exit 2 でブロック。実際に Read を試して弾かれた。
- ただし守備範囲は Claude Code の 3 ツールのみ。Bash `cat`/`head` は素通りする
  （設計上の許容。完全隔離ではなく「うっかり全文 Read を防ぐガードレール」）。

**読み取り側**の節約は実証された：セッション中、DML 全文（857 行 / 約 35.7k 字 /
概算 9〜12k tokens）を一度も読まず、観点別 view（数百〜4千字）だけで進めた。

**書き込み側**で取りこぼした浪費源：

| 記号 | 浪費 | 原因 |
|---|---|---|
| W1 | `lang` 全体を 3〜4 回 再投入 | `update --merge-yaml` が nested dict を**浅置換**。`lang.states` を足すだけでも `lang` 全文が必要だった |
| W2 | `/tmp/*.yaml` を 10 個近く `Write` | スカラー・短い配列までファイル経由にした（インラインで足りた） |
| W3 | スキーマ違反リトライ 4〜5 往復 | `phase` を数値で / `queries.users` をリストで / `transitions.via` 欠落 / policy 名を日本語で書いて弾かれた |

## A. 運用ルール（コード不要・次セッションから適用）

- **A1**: ネスト構造は「完成形を 1 回で」set。`lang` は actors/cmds/evts/pols/vos/
  states/aggs を最初から全部入れて 1 回で確定する。
- **A2**: 値渡しは機械判定 — 1 行スカラー・短い配列は インライン `--value`/`--item`、
  **長文 prose のみ** `--value-file`。temp YAML は「複数 dict 要素を 1 回で入れる」時だけ。
- **A3**: 着手前に `dml.schema.yaml` か `examples/sample.dml.yaml` を 1 度だけ確認して
  必須キー・型を把握（落とし穴チートシートは SKILL.md 参照）。
- **A4**: 関連編集は 1 つの Bash で `&&` 連鎖。各 set は `--no-postprocess`、**最後だけ**
  postprocess（build+validate を 1 回に）。

## B. dmlctl 改修（実装済み）

- **B1**: `update --merge-yaml` を**再帰マージ**化（`_deep_merge`）。nested dict は再帰、
  リーフ（スカラー/リスト）は置換。W1 の構造的原因を除去。
- **B2**: パスにリスト要素のキー選択を追加（`_Selector` / `_SELECTOR_RE`）。
  `set --path='contexts[name=billing].lang.states'` や `remove --path='contexts[name=x]'`。
- **B3**: 書き込み系に `--dry-run`。本体を書かずに一時ファイルで schema 検証して違反を返す。
  W3 の「汚して書き直す」往復を防ぐ。
- **おまけ**: `view | grep -q` / `| head` で出ていた BrokenPipeError を main 入口で握り潰し、
  smoke test の非決定的 FAIL（session-meta 等）を解消（19 PASS で安定）。

## C. ドキュメント

- **C1**: SKILL.md の「値の渡し方」節に、ネスト部分更新（B1/B2）・`--dry-run`（B3）・
  スキーマ落とし穴チートシートを追記。
- **C2**: 本メモ。

## 効果の要約

- 制約は機能（直接 I/O はブロック、完全隔離ではない）。
- 読み取り節約は実証済み。書き込みは B1〜B3 で W1・W3 を構造的に解消、A1〜A4 で W2 を運用回避。
