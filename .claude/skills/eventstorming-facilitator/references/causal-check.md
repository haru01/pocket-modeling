# DML フロー整合性チェックリスト

DML（YAML）の `scenarios` / `policies` のつながりを辿り、切れ・孤立・循環を検出する。
DML は兄弟 `<session>.dml.yaml` ファイル（純 YAML・フェンスなし）。`yaml.safe_load` でパースしてから各フィールドを収集する。

---

## 検査対象の収集

チェック前に以下を列挙する：

| リスト | 収集方法 |
|--------|---------|
| **EVT一覧** | 全 `scenarios[].evt` + `scenarios[].branches[].evt` + 全 `policies[].evt` |
| **CMD一覧** | 全 `scenarios[].cmd` |
| **POLICY名一覧** | 全 `policies[].name` |
| **TRIGGER一覧** | 全 `policies[].trigger` |
| **POLICY発行CMD一覧** | 全 `policies[].cmd` |
| **SCENARIO参照POL一覧** | 全 `scenarios[].pol` + `scenarios[].branches[].pol` |

---

## チェック項目

| # | チェック | 検出したい問題 |
|---|---------|---------------|
| **C1** | POLICY TRIGGERが実在するEVTを参照しているか | 存在しないEVTをTRIGGERとするPOLICY |
| **C2** | POLICYのCMDが実在するSCENARIOのCMDを参照しているか | SCENARIO未定義のCMDをPOLICYが発行している |
| **C3** | SCENARIOのPOL参照が実在するPOLICYを指しているか | 未定義のPOLICYをSCENARIOが参照している |
| **C4** | 孤立EVTの検出（終端以外） | どのPOLICY TRIGGERにも拾われないEVT（フロー終端でない場合は欠落） |
| **C5** | System ACTORのSCENARIO CMDがPOLICYから発行されているか | 人間が呼ぶはずのないCMDが自動起動されていない |
| **C6** | `branches` の全パスに `evt`（必要なら `pol`）が揃っているか | 成功パスのみ pol 定義、失敗パスが未接続 |
| **C7** | 循環参照の検出 | A→B→C→A のような無限ループになるPOLICYチェーン |
| **C8** | `contexts[].upstream` / `downstream` の `context` 参照が実在する `contexts[].name` を指しているか | 未定義 BC を依存先に指定したタイプミス・古い名前の残存 |

---

## 各チェックの詳細

### C1: POLICY TRIGGERの参照チェック

```
POLICY X の TRIGGER: SomeEvent
→ EVT一覧に SomeEvent が存在するか？
→ NOなら: 「POLICY X のTRIGGER SomeEvent は未定義のEVT」
```

### C2: POLICY CMDの参照チェック

```
POLICY X の CMD: SomeCommand
→ CMD一覧に SomeCommand が存在するか？
→ NOなら: 「POLICY X が発行する CMD SomeCommand に対応するSCENARIOがない」
```

### C3: SCENARIO POL参照チェック

```
scenario Y の pol: SomePolicy（または branches[].pol: SomePolicy）
→ POLICY名一覧に SomePolicy が存在するか？
→ NOなら: 「SCENARIO Y が参照する POLICY SomePolicy は未定義」
```

### C4: 孤立EVTの検出

```
EVT一覧の各EVTについて：
→ TRIGGER一覧に含まれるか？
→ NOなら終端候補としてリストアップ
→ フローの最後の結果（例: ShipmentNotificationSent）は「終端EVT（正常）」と明記
→ 中間段階のEVTが孤立している場合は「孤立EVT（要確認）」として報告
```

### C5: System CMDの起動元チェック

```
ACTOR が System のSCENARIOのCMDについて：
→ POLICY発行CMD一覧に含まれるか？
→ NOなら: 「CMD X はSystem SCENARIOだがどのPOLICYからも発行されていない」
```

### C6: branches の完全性チェック

```
branches を持つ scenario の各 branch について：
→ evt が付いているか？（全分岐で発火イベントが揃っているか）
→ 後続ポリシーへ接続する分岐は pol が付いているか？
→ 不足があれば: 「SCENARIO Y の branch N に evt / pol が未定義」
```

### C7: 循環参照チェック

```
POLICYグラフを構築:
  POLICY A → CMD X → SCENARIO Y → EVT Z → POLICY B → ...

深さ優先探索で訪問済みノードを記録し、再訪したら循環として報告。
```

---

## 出力フォーマット

```
## 因果チェーン結果

### ✅ 問題なし
- C1, C2, C3, C6, C7: 異常なし

### ⚠️ 要確認
- C4: 孤立EVT候補
  - `OutOfStockNotificationSent` — 終端EVT（正常）
  - `ShipmentNotificationSent` — 終端EVT（正常）

### ❌ 問題あり
- C2: POLICY CancelOnOutOfStock が発行する CMD CancelOrder に対応するSCENARIOがない
- C5: CMD ConfirmOrder は System SCENARIOだがPOLICYのCMD参照を確認してください
```

---

## 手順（サブエージェント向け）

1. MDファイルを Read で読み込む
2. 上記「検査対象の収集」を実施してリストを作る
3. C1〜C7 を順に検査する
4. **問題あり・要確認** の項目をセクション6（オープンクエスチョン）に追記する（Edit tool）

### セクション6への追記ルール

- `### 因果チェーン（自動検出）` という小見出しで追記する
- 既存のQ番号の続き番号を使う（重複させない）
- フォーマット: `- Q?. <業務上の問題の説明（非エンジニアが読める日本語）> — <確認が必要な問い>`
- 問題なし（✅）の項目は記載しない
- `### 因果チェーン（自動検出）` 見出しが既にある場合は内容を上書き更新する
- 問題がゼロの場合はセクション6に何も追記しない

### 文章の書き方（重要）

**技術用語（CMD, POLICY, TRIGGER, SCENARIO 等）は使わない。**
ビジネス・業務の言葉で、非エンジニアの担当者が読んで「何を決めなければいけないか」がわかるように書く。

| NG（技術的すぎる） | OK（業務言語） |
|-------------------|---------------|
| `CancelOrder` に対応するSCENARIOがない | 「注文キャンセル」の業務手順がまだ定義されていない |
| `OrderConfirmed` がTRIGGERに繋がっていない | 「注文承認」の後に何が自動で動くかが決まっていない |
| System ACTORのCMDがPOLICYから発行されていない | 「〇〇処理」がどのタイミングで自動実行されるか未定義 |

### 追記例

```markdown
### 因果チェーン（自動検出）
- Q2. 「注文キャンセル」の業務手順がまだ定義されていません — 在庫切れでキャンセルになったとき、顧客への連絡・返金はどの部門が担当し、どの順番で行いますか？
- Q3. 「注文承認」の後に何が起きるかが決まっていません — 承認されたら倉庫への指示は自動で飛ぶのか、担当者が手動で操作するのかを確認してください
```
