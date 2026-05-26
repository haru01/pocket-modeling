# es-key 安定キー仕様

セッションを跨いだ Issue 同一性追跡のためのキー。Issue 本文先頭に **HTML コメント** として埋め込み、`gh issue list --search` で検索可能にする。

## 形式

```
<!-- es-key: <kind-path> -->
```

`<kind-path>` は階層スラッシュ形式:

| 種別 | パターン | 例 |
|---|---|---|
| AGG Epic | `bc/<bc-slug>/agg/<AggName>` | `bc/event-planning/agg/Event` |
| 統合 SCENARIO | `bc/<bc-slugs-joined>/scenario/<ScenarioName>` | `bc/registration+payment/scenario/ConfirmApplication` |
| Cross-BC Saga | `saga/<SagaName>` | `saga/ApplicationPaymentSaga` |

- `<bc-slug>` は kebab-case
- `<AggName>` は PascalCase（DML 識別子そのまま）
- 統合 SCENARIO は複数 BC を `+` で結合（アルファベット順）

> CMD / QRY / 受信 POLICY は AGG Epic 本文に inline で記述され、独立 Issue を持たないため es-key も持たない。

## 重複検出

```bash
gh issue list --search "es-key:bc/event-planning/agg/Event in:body" \
  --json number,title --state all
```

ヒットすれば既存。`gh issue edit <N> --body-file ...` で本文を更新する（タイトル・ラベルは変更しない）。
ヒットしなければ `gh issue create` で新規作成。

## なぜ HTML コメントか

- GitHub の Markdown レンダリングでは表示されない
- 本文検索の対象には含まれる
- ユーザーが Issue を編集する際に明示的に残しておけば破壊されにくい

## 補助: _state.json

ローカル `docs/issues/<session-id>/_state.json` に es-key → issue 番号マップを保存:

```json
{
  "bc/event-planning/agg/Event": 101,
  "bc/registration+ticketing/scenario/RefundExecution": 205,
  ...
}
```

これは高速ルックアップ用のキャッシュ。**真実源は GitHub 上の Issue 本文に埋め込まれた es-key**。`_state.json` が消えても再構築可能。
