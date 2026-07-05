# causal-chain-completeness

ハッピーパスと代替シナリオの **因果連鎖が途切れていないか** を LLM で評価する観点。

## 抽出条件

```bash
python3 scripts/dmlctl.py view <session>.dml.yaml --view=flow-causality [--id <flow-id>]
```

各 step の `kind`（scenario / policy / scenario-ref / unresolved）/ `ctx` / `cmd` / `evt` / `trg` を含む。
unresolved な step は構造チェック側で先に検出済みであることを前提とする。

view 出力の読み方（brs 分岐対応版）:

- `steps[]` はメインパス（各分岐点で 1 本を選んだ線形時系列）
- scenario step の `branches[]` に **brs 全分岐が verbatim**（cond / evt / pol / next / terminal / note）で
  列挙され、メインパスが辿った分岐に `taken: true` が付く
- **非選択分岐の行き先はフローの `sidetracks[]` に展開される**。`{from: 分岐元 scenario 名, cond, evt,
  steps: [...]}` で、steps の形式はメインパスと同一（policy 挿入・さらなる分岐もある）
- `kind: scenario-ref` は既出 scenario への **合流**（重複展開を避けた参照）。連鎖の途切れではない
- `terminal` は分岐がそのフローを終端させるときのみ現れる（値は flow-id）。**next 省略による暗黙終端は
  正当な終端であり、terminal フィールドが無いことは不備ではない**（terminal は schema 上 `brs[]` にのみ
  存在するため、「scenario に terminal を宣言せよ」という修正提案はしないこと）

## LLM へのプロンプト

```
あなたは EventStorming のフロー因果整合性をレビューするドメイン専門家です。以下の flow を
時系列順に読み、業務的に「次に何が起きるか」が自然につながっているかを評価してください。

評価観点:
1. **アクター起点の CMD** から始まり、**POLICY による非同期遷移** で別 BC へ流れ、最終 EVT で終端しているか
2. **連続する step の間に説明されない飛躍** がないか（例: 検品完了 → いきなり配送完了。承認 / 査定確定 / 出荷指示 がスキップされている等）
3. **POLICY の trg** が直前ステップの evt と整合しているか
4. **業務上の「分岐」が落ちていないか**（rejected/timeout/suspicious 等の代替フローが必要なポイントが抜けていないか）。
   ただし missing_branches の判定は、**必ず各 step の branches[] と flow の sidetracks[] を突合してから**
   行うこと（分岐は steps の線形列には現れず branches/sidetracks 側にモデル済みのことが多い。
   モデル済みの分岐を「無い」と報告しない）

入力 (YAML):
{{flow_causality_yaml}}

出力フォーマット:
[
  {
    "flow": "<flow.id>",
    "verdict": "complete" | "gap" | "broken",
    "gaps": [
      {
        "between_steps": ["<step N>", "<step N+1>"],
        "missing": "<business event/action that should bridge>",
        "suggestion": "<改善案>"
      }
    ],
    "missing_branches": [
      "<必要な代替フローの説明>"
    ]
  }
]
```

## 期待される所見

- ✅ complete: ハッピーパスが切れ目なくつながっており、代替フローも網羅されている
- ⚠ gap: 「検品完了 → 査定確定 → 通知」の流れで `承認` step が抜けている
- ❌ missing_branch: 偽物検出後の補償フロー（SUSPENDED 解除）が narratives[] / scenarios[].next 連鎖に無い

## 連携する構造チェック

- `flow_chain_resolution` — unresolved entry/next/terminal を先に修正
- `unknown_evt_in_policy` — POLICY のトリガー整合を先に修正
