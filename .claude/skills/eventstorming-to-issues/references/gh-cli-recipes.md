# gh CLI レシピ

## 1. Label 冪等作成

```bash
# 既存 Label 一覧取得
existing=$(gh label list --json name --jq '.[].name')

# 必要 Label を一つずつ確認
need_label() {
  local name="$1"
  local color="$2"
  local desc="$3"
  if ! echo "$existing" | grep -qFx "$name"; then
    gh label create "$name" --color "$color" --description "$desc"
  fi
}

need_label "type:aggregate" "1D76DB" "EventStorming: 集約 Epic (AI dispatch 単位)"
need_label "type:scenario" "C2E0C6" "EventStorming: AGG 跨ぎ統合シナリオ"
need_label "type:saga" "D93F0B" "EventStorming: Cross-BC Saga"
need_label "cross-bc" "B60205" "EventStorming: BC 横断 POLICY / Saga"
need_label "agg:Event" "EDEDED" "EventStorming: 集約 Event"
# bc:* は BC ごとに HSL ハッシュで色を決定
need_label "bc:event-planning" "$(hsl_hash event-planning)" "EventStorming: BC event-planning"
```

## 2. es-key で既存 Issue 検出

```bash
# es-key から既存 Issue 番号を取得（なければ空）
find_issue_by_eskey() {
  local eskey="$1"
  gh issue list --search "es-key:${eskey} in:body" \
    --state all --json number --jq '.[0].number // empty'
}
```

## 3. Issue 作成 or 更新（冪等）

```bash
upsert_issue() {
  local body_file="$1"
  local eskey
  eskey=$(grep -m1 '<!-- es-key:' "$body_file" | sed 's/.*es-key: *\([^ ]*\) *-->.*/\1/')

  local title
  title=$(grep -m1 '^# ' "$body_file" | sed 's/^# *//')

  local labels="$2"  # comma separated

  local existing
  existing=$(find_issue_by_eskey "$eskey")

  if [ -n "$existing" ]; then
    gh issue edit "$existing" --body-file "$body_file"
    echo "$existing"
  else
    gh issue create --title "$title" --body-file "$body_file" --label "$labels" \
      | tail -1 | sed 's|.*/||'
  fi
}
```

## 4. 起票対象は AGG Epic / 統合 SCENARIO / Saga のみ

新設計では **1 AGG = 1 self-contained Epic = 1 PR** で、CMD / QRY / 受信 POLICY は AGG Epic 本文に inline されるため、Sub-issue 紐付け (`addSubIssue` mutation) は使わない。

統合 SCENARIO Issue は AGG Epic を Depends on 欄から `#N` で参照する（GitHub の自動バックリンクで関連付け）。

## 5. レート制限回避

```bash
# 冪等起票ループ
sleep_between() {
  sleep 1.5  # secondary rate limit 対策
}
```

## 6. Milestone は本スキルでは作らない

設計判断: BC は Label `bc:xxx` で表現する。Milestone は「1 issue 1 milestone」制約があり、Phase / リリース管理用に温存する。

もし将来必要になったら:
```bash
gh api "repos/:owner/:repo/milestones" -f title="BC: event-planning" -f description="..."
```

## 7. リポジトリ指定

カレントディレクトリの git remote `origin` を使う（`gh` のデフォルト挙動）。別 repo を対象にしたい場合は `gh -R owner/repo issue create ...` のように `-R` フラグで指定。
