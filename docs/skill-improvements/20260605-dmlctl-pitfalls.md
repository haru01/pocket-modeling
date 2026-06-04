# dmlctl 運用で踏んだ落とし穴（2026-06-05）

マップカメラ オンライン下取り購入のモデリングセッション
（`eventstorming-20260605-0757`）で発生した失敗の記録。**記録のみ**（修正は未実施）。

## F1. `scenarios[].pol` と `brs[].pol` の型が非対称（schema 違反リトライ 1 往復）

- **症状**: scenario 直下に `pol: GuideTradeInKit`（文字列）と書いたら
  `scenarios/1/pol: 'GuideTradeInKit' is not of type 'array'` で弾かれた。
- **原因**: schema 上、**scenario 直下の `pol` は配列**（`pol: [GuideTradeInKit]`）、
  一方 **`brs[].pol` は文字列**（`pol: RequestPayment`）。同じキー名で型が違う。
  `examples/sample.dml.yaml` には `brs[].pol`（文字列）の例しか無く、
  scenario 直下 `pol` の例が無いため、文字列で書いてしまった。
- **改善案**:
  - **(a) ドキュメント**: SKILL.md の「スキーマ落とし穴チートシート」に
    「`scenarios[].pol` は配列 / `brs[].pol` は文字列」の 1 行を追加する。
  - **(b) サンプル**: `examples/sample.dml.yaml` に scenario 直下 `pol: [X, Y]`
    （複数ポリシー同時発火）の例を 1 つ足す。
  - **(c) 検討**: そもそも型を揃える（両方 array、または scenario 直下も string 許容の
    oneOf）と紛らわしさが消える。ただし後方互換に注意。
  - **(d) 予防運用**: 着手前に `--dry-run` を付ければ書き込み前に検出できた（A3/B3 の徹底）。

## F2. Bash 変数にコマンド文字列を入れると zsh で exit 127（自分の誤用・2 往復ロス）

- **症状**: `D="python3 .claude/.../dmlctl.py"; $D set ...` が
  `no such file or directory: python3 .claude/.../dmlctl.py` で失敗（exit 127）。
- **原因**: zsh では `$D` 展開後の文字列全体が **1 個のコマンド名**として解釈され、
  「`python3 .claude/.../dmlctl.py`」というスペース込みの実行ファイルを探しに行く
  （単語分割されない）。これはスキルの問題ではなく Bash 使用側の誤り。
- **回避**: シェル関数 `d() { python3 .claude/skills/.../dmlctl.py "$@"; }` を定義して
  `d set ...` `d update ...` のように呼ぶと、`&&` 連鎖（A4）も短く書けて確実。
- **改善案（ドキュメント）**: skill-improvements か SKILL.md の運用 Tips に
  「複数 dmlctl 呼び出しを 1 Bash で連鎖するときは、変数代入ではなく**シェル関数**で
  ラップする」と一言添えると、同じ取りこぼしを防げる。

## F3. 「単数キーは文字列・複数キーは配列」の型非対称が複数箇所にある（schema 違反リトライ各 1 往復）

- **症状**: 同じ要素内で型が割れていて、片方を取り違えて弾かれた。
  - `scenarios[].pol` は**配列**、`brs[].pol` は**文字列**（F1）。
  - `queries[].sources` は**配列**、`queries[].users` は**文字列**
    （`sources: 'A, Appraisal' is not of type 'array'` で弾かれた）。
- **共通の根**: キー名から型が推測できない。`users` が文字列なら `sources` も文字列だろう、
  と推測してハマる。`examples/sample.dml.yaml` には `queries[]` の例が無いのも一因。
- **改善案**:
  - **(a) チートシート**: 「複数を表すキーは配列（`pol`/`sources`/`attrs`/`appraisalIds`…）」
    「`users` は文字列（複数ユーザーは『受付・医師』のように 1 文字列に列挙）」を
    SKILL.md の落とし穴表に明記（`queries.users` は既出だが `sources` の対比が無い）。
  - **(b) サンプル**: `examples/sample.dml.yaml` に `queries[]` の実例を 1 つ追加。
  - **(c) 予防運用**: 新カテゴリを初めて書くときは `--dry-run` を必ず通す。
    今回 F1・F3 とも dry-run していれば往復ゼロだった。**A3 を「未経験カテゴリは
    dry-run 必須」に格上げ**するのが効く。

## 実装状況（2026-06-05 反映済み）

計画 `~/.claude/plans/dapper-sleeping-knuth.md` に基づき、F1〜F4 を以下で解消した。

- **SKILL.md**: スキーマ落とし穴チートシートに `scenarios[].pol`（配列のみ）/ `queries[].sources`
  （配列）/ 値内 ` : ` のクォート の 3 行を追加。「単数キー=文字列／複数キー=配列、`brs[].pol`・
  `transition.to` は oneOf の例外」の見分け方ノートを追記。`--dry-run` を **未経験カテゴリ必須** に格上げ。
  シェル関数ラップの運用 Tips（F2）を「値の渡し方」節に追加。
- **examples/sample.dml.yaml**: トップレベル `queries[]` ブロックを新規追加（`users` 文字列 ＋
  `sources` 配列の対比を実演）。scenarios 冒頭に `pol` の配列/文字列の書き分けコメントを追加。
- **references/dml.schema.yaml**: `scenarios[].pol` / `qry.users` / `qry.sources` にインライン注意
  コメント、冒頭「命名方針」に「型の方針」節を追記。
- **scripts/validate_dml.py**: `_format_error()` を拡張し type 違反時に「（期待: array / 実際: str）」
  ヒントを付与（F1・F3 を自己説明化）。exit code・検証ロジックは不変。
- **検証**: sample が validate OK / 構造チェック 6 観点すべて count=0 / HTML ビルド成功 /
  dry-run で型違反時にヒント表示・ファイル未変更、を確認済み。

## 補足：今回うまくいった点（B1/B2/B3 の効果実証）

- `update --merge-yaml`（再帰マージ・B1）で `lang.evts` / `lang.pols` に新規識別子だけを
  追記でき、`lang` 全文の再投入（旧 W1）は発生しなかった。
- `update --path=contexts --where=name=X --merge-yaml=...` で BC 単位の
  `up`/`dn`/`description` 部分更新が 1 行で済んだ。
- フェーズ完了時に `--no-postprocess` を連ね、最後だけ build+validate（A4）を実践できた。
