# 品質チェックサブエージェント起動プロンプト

MD ファイルを書き出したら以下のプロンプトで Agent を起動する：

```
Agent(
  description: "EventStorming品質チェック",
  prompt: """
EventStorming セッションファイル `<ファイルパス>` のDDD/EventStorming品質を
チェックしてください。

チェック方針は 2 段階:
- D・F・S 系（表記の正しさ）: 違反があれば Edit tool で自動修正
- M 系（モデリングの意味の正しさ）: 自動修正せず、ホットスポット候補として
  レポートに列挙する

手順:
1. `<ファイルパス>`（`.md`）と**兄弟 `.dml.yaml`（同名・拡張子 `.dml.yaml`、DML 本体・純 YAML）**を Read で読み込む（DML 記法チェックは `.dml.yaml` を対象）。あわせて `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py <session>.dml.yaml` を実行し、JSON Schema による構文違反（D1/D6/D8・enum・必須・排他など）を機械検出した結果を判断材料にする
2. `.claude/skills/eventstorming-facilitator/references/quality-check.md` を Read で読み込む
3. 全項目を順に検査する:
   - 表記チェック D1〜D10
   - フロー記法チェック F1〜F6
   - セクション完全性チェック S1〜S7
   - **目的サブセクション必須チェック S8（AGG カードの `#### 目的` 30 字以上）**
   - **WHY/WHEN 推奨チェック W1〜W2（`rules[].why` / `errs[].when`）**
   - モデリング意味チェック M1〜M5
4. D・F・S1〜S7 違反は Edit tool で直接修正する
5. **S8 / W1 / W2 違反は自動修正しない**（形式上 S/W 系だが意味依存のため）。`[?-WHY] S8_<AggName>: ...` / `[?-WHY] W_N: ...` の形でレポートに列挙
6. M 違反候補は修正せず、`[?] M_N: <該当箇所> — <推奨>` の形でレポートに列挙
7. 以下の形式で結果を返す:
   - 違反なし: 「品質チェック完了：問題なし」
   - D/F/S1〜S7 違反あり: 修正した項目リスト（例: F1×3箇所修正, D6×1箇所修正）
   - S8 違反あり: ホットスポット候補リスト（例:
       [?-WHY] S8_Payment: AGG `Payment` の `#### 目的` が未記入。
            推奨: 決済責務の核を 1 文で言語化（30 字以上）
   )
   - W1/W2 違反あり: ホットスポット候補リスト（例:
       [?-WHY] W1: scenario「主催者がコミュニティを作成する」 の rule
            `communityName must be unique system-wide` に `why` 未記入。
            推奨: why: "URL slug や検索 UX で name → id 逆引きを想定するため"
       [?-WHY] W2: 同 scenario の err `DuplicateCommunityNameError`
            (cond: duplicateName) に `when` 未記入。推奨: when: "name が既存と重複"
   )
   - M 違反候補あり: ホットスポット候補リスト（例:
       [?] M1: SCENARIO「顧客が注文を確定する」 — CMD/EVT で「確定」が
            重複し、後続 Saga 起動のため命名が早すぎる可能性。推奨:
            CMD `PlaceOrder` (注文する) / EVT `OrderPlaced` (注文された)
            に変更し、別 SCENARIO で `ConfirmOrder` / `OrderConfirmed`
            を追加
       [?] M2: CMD `MarkOrderPaid` — 「Mark」は CRUD 的命名。推奨: `ConfirmOrder`
   )
"""
)
```

結果を受けて：
- **問題なし** → 次のファシリテーションに進む
- **D/F/S1〜S7 修正あり** → 修正内容をユーザーに1行で報告し、フェーズ完了相当の変更なら更新後の Event Flow SVG をチャットに再掲する
- **S8 / W1 / W2 違反候補あり** → ファシリテーター本体が次ターン応答の末尾に `### WHY 補完が必要` セクションを置き、優先度（目的 > 制約 > WHY > WHEN）で 1 件ずつユーザーに問う（詳細は `chat-output-format.md` §10A）
- **M 違反候補あり** → ホットスポット候補をユーザーに提示し、「修正するか / そのままにするか」を確認。修正する場合は次ターンで MD を Edit して反映する
