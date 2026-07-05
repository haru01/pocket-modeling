#!/usr/bin/env bash
# Smoke test for dmlctl 拡張 API + block_direct_dml hook.
# Usage: bash .claude/skills/eventstorming-facilitator/scripts/tests/smoke_test_dmlctl.sh
#
# Requires: python3, pyyaml, ruamel.yaml, jsonschema
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
DMLCTL="python3 $REPO_ROOT/.claude/skills/eventstorming-facilitator/scripts/dmlctl.py"
HOOK="python3 $REPO_ROOT/.claude/skills/eventstorming-facilitator/scripts/hooks/block_direct_dml.py"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

PASS=0
FAIL=0

ok() { echo "  ✅ $1"; PASS=$((PASS+1)); }
ng() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "== dmlctl init =="
$DMLCTL init "$TMPDIR/t.dml.yaml" --session-id=test-1 --domain=d --goal="G" --no-postprocess >/dev/null
[ -f "$TMPDIR/t.dml.yaml" ] && ok "file created" || ng "file not created"
grep -q "managed by dmlctl" "$TMPDIR/t.dml.yaml" && ok "header present" || ng "header missing"

# init twice → fail
if $DMLCTL init "$TMPDIR/t.dml.yaml" --session-id=dup --domain=d --no-postprocess 2>/dev/null; then
  ng "init overwrite should fail"
else
  ok "init refuses to overwrite"
fi

echo "== dmlctl view =="
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=session-meta | grep -q "test-1" && ok "session-meta works" || ng "session-meta broken"
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=top-level-keys | grep -q "session" && ok "top-level-keys works" || ng "top-level-keys broken"
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=full >/dev/null && ok "full view works" || ng "full view broken"

echo "== dmlctl set =="
$DMLCTL set "$TMPDIR/t.dml.yaml" --path=session.status --value="updated" --no-postprocess
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=session-meta | grep -q "updated" && ok "set basic works" || ng "set basic broken"

# set --value-file
echo "long content from file" > "$TMPDIR/prose.txt"
$DMLCTL set "$TMPDIR/t.dml.yaml" --path=session.goal --value-file="$TMPDIR/prose.txt" --no-postprocess
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=session-meta | grep -q "long content" && ok "set --value-file works" || ng "set --value-file broken"

echo "== dmlctl add =="
$DMLCTL set "$TMPDIR/t.dml.yaml" --path=questions --value='[]' --no-postprocess
$DMLCTL add "$TMPDIR/t.dml.yaml" --to=questions --item='{id: Q1, topic: t1, status: open}' --no-postprocess
$DMLCTL add "$TMPDIR/t.dml.yaml" --to=questions --item='{id: Q2, topic: t2, status: open}' --no-postprocess
[ "$($DMLCTL view "$TMPDIR/t.dml.yaml" --view=all-questions | grep -c "^- id:")" -eq 2 ] && ok "add x2 works" || ng "add x2 broken"

# add --item-file
cat > "$TMPDIR/item.yaml" <<EOF
id: Q3
topic: from file
status: open
EOF
$DMLCTL add "$TMPDIR/t.dml.yaml" --to=questions --item-file="$TMPDIR/item.yaml" --no-postprocess
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=all-questions | grep -q "from file" && ok "add --item-file works" || ng "add --item-file broken"

# P1②: 未存在トップレベルキーへの add は空リストを自動生成して成功（下ごしらえ set 不要）
$DMLCTL init "$TMPDIR/fresh.dml.yaml" --session-id=fresh --domain=d --no-postprocess >/dev/null
$DMLCTL add "$TMPDIR/fresh.dml.yaml" --to=actions --item='{id: A1, text: t}' --no-postprocess 2>/dev/null \
  && $DMLCTL view "$TMPDIR/fresh.dml.yaml" --view=actions | grep -q "A1" \
  && ok "add auto-creates missing key" || ng "add on missing key broken"

# P1②: 未存在キー add が生トレースバックを出さない
if $DMLCTL add "$TMPDIR/fresh.dml.yaml" --to='contexts[name=nope].lang.states' --item='{}' --no-postprocess 2>"$TMPDIR/err.txt"; then
  ng "add should fail on missing intermediate"
else
  grep -q "Traceback" "$TMPDIR/err.txt" && ng "add leaked Traceback" || ok "add missing intermediate is friendly"
fi

# P1②: トップレベルの typo キーは exit 2 で弾く
if $DMLCTL add "$TMPDIR/fresh.dml.yaml" --to=actionss --item='{id: A1, text: t}' --no-postprocess 2>/dev/null; then
  ng "add should reject top-level typo key"
else
  ok "add rejects top-level typo key"
fi

echo "== dmlctl update =="
$DMLCTL update "$TMPDIR/t.dml.yaml" --path=questions --where='id=Q1' --set-key=status --value=closed --no-postprocess 2>/dev/null
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=open-questions | grep -q "Q1" && ng "update should close Q1" || ok "update set-key works"

$DMLCTL update "$TMPDIR/t.dml.yaml" --path=questions --where='id=Q2' --merge-yaml='{status: closed, decision_id: D1}' --no-postprocess 2>/dev/null
$DMLCTL view "$TMPDIR/t.dml.yaml" --view=all-questions | grep -q "D1" && ok "update --merge-yaml works" || ng "update --merge-yaml broken"

# update no match → exit 2
if $DMLCTL update "$TMPDIR/t.dml.yaml" --path=questions --where='id=Q99' --set-key=status --value=closed --no-postprocess 2>/dev/null; then
  ng "update should fail on no match"
else
  ok "update fails on no match"
fi

echo "== dmlctl remove =="
$DMLCTL remove "$TMPDIR/t.dml.yaml" --path=questions --where='id=Q3' --no-postprocess 2>/dev/null
[ "$($DMLCTL view "$TMPDIR/t.dml.yaml" --view=all-questions | grep -c "^- id:")" -eq 2 ] && ok "remove --where works" || ng "remove --where broken"

echo "== dmlctl validate =="
$DMLCTL validate "$TMPDIR/t.dml.yaml" 2>&1 | grep -q "schema OK" && ok "validate works" || ng "validate broken"

echo "== dmlctl check --format=summary (P2/P3) =="
# ⑮ summary 出力。check --all は違反ありで exit 1 を返すため、出力を変数に捕捉して判定
summary_out="$($DMLCTL check "$TMPDIR/t.dml.yaml" --all --format=summary 2>/dev/null || true)"
echo "$summary_out" | grep -q "観点" && ok "check --format=summary works" || ng "check summary broken"

# ⑥ decisions: adopted を明示しなくても chosen だけで違反にならない
cat > "$TMPDIR/dec.dml.yaml" <<EOF
decisions:
  - id: D1
    topic: t
    chosen: opt-a
    affects: [X]
    options:
      - { name: opt-a, why: yes }
      - { name: opt-b, why_not: no }
EOF
$DMLCTL check "$TMPDIR/dec.dml.yaml" --check=decision_chosen_adopted 2>/dev/null | grep -q '"count": 0' \
  && ok "decision_chosen_adopted allows chosen-only" || ng "decision_chosen_adopted still requires adopted"

# ⑯ narrative_entry_consistency: 共有 entry でも下流で分岐すれば違反にしない
cat > "$TMPDIR/narr.dml.yaml" <<EOF
narratives:
  - { id: happy, kind: happy, entry: E1, prose: x }
  - { id: alt, kind: alt, entry: E1, prose: y }
scenarios:
  - name: E1
    ctx: bc-a
    actor: System
    cmd: C1
    next: E2
  - name: E2
    ctx: bc-a
    actor: System
    cmd: C2
    next: { happy: E3, alt: E4 }
  - { name: E3, ctx: bc-a, actor: System, cmd: C3 }
  - { name: E4, ctx: bc-a, actor: System, cmd: C4 }
EOF
$DMLCTL check "$TMPDIR/narr.dml.yaml" --check=narrative_entry_consistency 2>/dev/null | grep -q '"count": 0' \
  && ok "narrative_entry_consistency allows downstream divergence" || ng "narrative_entry_consistency too strict"

# ④⑤ schema: within / brs.after / trgs.mode:or を含む DML が valid
cat > "$TMPDIR/time.dml.yaml" <<EOF
policies:
  - name: RefundPol
    ctx: accounting
    trgs: { evts: [ReturnConfirmed, RedeliveryCancelled], mode: or }
    cmd: ExecuteRefund
    within: 火金の週2回
scenarios:
  - name: 前払い
    ctx: ordering
    actor: Customer
    cmd: PlaceOrder
    brMode: exclusive
    brs:
      - { cond: 入金あり, evt: PaymentReceived, next: 受注 }
      - { cond: 入金なし, evt: PaymentDeadlineExpired, after: 1週間, terminal: alt }
EOF
$DMLCTL validate "$TMPDIR/time.dml.yaml" 2>&1 | grep -q "schema OK" \
  && ok "within/after/trgs.mode:or validate" || ng "time/OR schema broken"

echo "== block_direct_dml hook =="
# Block: Edit on DML path
if echo '{"tool_name":"Edit","tool_input":{"file_path":"docs/eventstorming/x.dml.yaml"}}' | $HOOK 2>/dev/null; then
  ng "hook should block Edit on DML"
else
  ok "hook blocks Edit"
fi
# Block: Read on DML abs path
if echo '{"tool_name":"Read","tool_input":{"file_path":"/abs/docs/eventstorming/y.dml.yaml"}}' | $HOOK 2>/dev/null; then
  ng "hook should block Read"
else
  ok "hook blocks Read"
fi
# Pass: Write on other path
if echo '{"tool_name":"Write","tool_input":{"file_path":"src/foo.py"}}' | $HOOK 2>/dev/null; then
  ok "hook passes non-DML Write"
else
  ng "hook should pass non-DML Write"
fi
# Pass: Bash (not blocked tool)
if echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | $HOOK 2>/dev/null; then
  ok "hook passes Bash"
else
  ng "hook should pass Bash"
fi

echo "== dmlctl hint =="
# P1③: 条件付き必須（bulk→qry）と排他（trg/trgs）が hint に出る
$DMLCTL hint --path=policies | grep -q "conditional" && ok "hint shows conditional" || ng "hint conditional missing"
$DMLCTL hint --path=policies | grep -q "trg と trgs" && ok "hint shows exclusive" || ng "hint exclusive missing"
$DMLCTL hint --path=policies | grep -q "name" && ok "hint required regression" || ng "hint required broken"

echo "== flow-causality view unit tests =="
if python3 "$REPO_ROOT/.claude/skills/eventstorming-facilitator/scripts/tests/test_flow_causality.py" >/dev/null 2>&1; then
  ok "test_flow_causality passes"
else
  ng "test_flow_causality failed"
fi

echo "== hints unit tests =="
if python3 "$REPO_ROOT/.claude/skills/eventstorming-facilitator/scripts/tests/test_hints.py" >/dev/null 2>&1; then
  ok "test_hints passes"
else
  ng "test_hints failed"
fi

echo ""
echo "==================="
echo " PASS: $PASS  FAIL: $FAIL"
echo "==================="
[ "$FAIL" -eq 0 ]
