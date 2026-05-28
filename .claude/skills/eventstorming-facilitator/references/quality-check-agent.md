# 品質チェックサブエージェント起動プロンプト

`.md` ファイル＋兄弟 `.dml.yaml` を書き出したら以下のプロンプトで Agent を起動する：

```
Agent(
  description: "EventStorming品質チェック",
  prompt: """
EventStorming セッションファイル `<ファイルパス>` のDDD/EventStorming品質を
チェックしてください。

チェック方針は 2 段階:
- D・F・S1〜S7 系（表記の正しさ）: 違反があれば Edit tool で自動修正
- S5-attr / S5-evt / S8 / S9 / F-flows / F-decisions / W / M 系
  （モデリングの意味の正しさ）: 自動修正せず、ホットスポット候補として
  レポートに列挙する

手順:
1. `<ファイルパス>`（`.md`）と**兄弟 `.dml.yaml`（同名・拡張子 `.dml.yaml`、DML 本体・純 YAML）**を Read で読み込む（DML 記法チェックは `.dml.yaml` を対象）。あわせて `python3 .claude/skills/eventstorming-facilitator/scripts/validate_dml.py <session>.dml.yaml` を実行し、JSON Schema による構文違反（D1/D6/D8・enum・必須・排他など）を機械検出した結果を判断材料にする
2. `.claude/skills/eventstorming-facilitator/references/quality-check.md` を Read で読み込む
3. 全項目を順に検査する:
   - 表記チェック D1〜D10
   - フロー記述チェック F-flows / F-decisions
   - セクション完全性チェック S1〜S7
   - **属性/イベントペイロード必須チェック S5-attr / S5-evt（aggs[].attrs[] / aggs[].events[].params[]）**
   - **目的サブセクション必須チェック S8（aggs[].purpose 30 字以上）**
   - **孤立/未定義 AGG 検出 S9**
   - **WHY/WHEN 推奨チェック W1〜W3（rules[].why / errs[].when / decisions[].options[].why or why_not）**
   - モデリング意味チェック M1〜M5
4. D・F・S1〜S7 違反は Edit tool で直接修正する
5. **S5-attr / S5-evt / S8 / S9 / F-flows / F-decisions / W1〜W3 違反は自動修正しない**（意味依存のため）。`[?-WHY] S8_<AggName>: ...` / `[?] S5-attr_<AggName>: ...` / `[?] F-flows_<flowId>_<step>: ...` の形でレポートに列挙
6. M 違反候補は修正せず、`[?] M_N: <該当箇所> — <推奨>` の形でレポートに列挙
7. 以下の形式で結果を返す:
   - 違反なし: 「品質チェック完了：問題なし」
   - D/F/S1〜S7 違反あり: 修正した項目リスト
   - S5-attr / S5-evt 違反あり: ホットスポット候補リスト（例:
       [?] S5-attr_Event: aggs[] エントリ Event に attrs[] が未記述。
            推奨: { name: title, type: string, required: true } 等の属性宣言を追加
       [?] S5-evt_Event.EventPublished: params[] が未記述。
            推奨: { name: eventId, type: EventId } 等の payload 宣言を追加
   )
   - S8 違反あり: ホットスポット候補リスト（例:
       [?-WHY] S8_Payment: AGG `Payment` の purpose が未記入。
            推奨: 決済責務の核を 1 文で言語化（30 字以上）
   )
   - S9 違反あり: ホットスポット候補リスト（例:
       [?] S9_Notification: aggs[] に宣言されているが scs[].agg で未参照（孤立 AGG）
   )
   - F-flows / F-decisions 違反あり: ホットスポット候補リスト（例:
       [?] F-flows_happy_顧客が注文する: step "顧客が注文する" は scs/pols に未定義
       [?] F-decisions_D1: chosen "A 案" が options[].name のいずれにも一致しない
   )
   - W1/W2/W3 違反あり: ホットスポット候補リスト（例:
       [?-WHY] W1: scenario「主催者がコミュニティを作成する」 の rule
            `communityName must be unique system-wide` に `why` 未記入。
            推奨: why: "URL slug や検索 UX で name → id 逆引きを想定するため"
       [?-WHY] W3: decision D1 の option "Participation 集約に持たせる" に
            why_not 未記入。推奨: なぜ採用しなかったかを業務文脈で言語化
   )
   - M 違反候補あり: ホットスポット候補リスト（例:
       [?] M1: SCENARIO「顧客が注文を確定する」 — CMD/EVT で「確定」が
            重複し、後続 Saga 起動のため命名が早すぎる可能性。推奨:
            CMD `PlaceOrder` (注文する) / EVT `OrderPlaced` (注文された)
            に変更し、別 SCENARIO で `ConfirmOrder` / `OrderConfirmed`
            を追加
   )
"""
)
```

結果を受けて：
- **問題なし** → 次のファシリテーションに進む
- **D/F/S1〜S7 修正あり** → 修正内容をユーザーに1行で報告し、フェーズ完了相当の変更なら更新後の構造化テーブルをチャットに再掲する
- **S5-attr / S5-evt / S8 / S9 / F-flows / F-decisions / W 違反候補あり** → ファシリテーター本体が次ターン応答の末尾に `### WHY 補完が必要` セクションを置き、優先度（目的 > 属性 > イベントペイロード > 制約 > WHY > WHEN）で 1 件ずつユーザーに問う（詳細は `chat-output-format.md` §10A）
- **M 違反候補あり** → ホットスポット候補をユーザーに提示し、「修正するか / そのままにするか」を確認。修正する場合は次ターンで `.dml.yaml` を Edit して反映する
