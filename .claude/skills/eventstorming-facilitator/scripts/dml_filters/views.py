"""DML 観点別 view 関数群。

各 view は `model: dict` を入力に取り、観点に関連する **最小限の dict**（YAML / JSON / Markdown
にダンプ可能）を返す。AI は `dmlctl view --view=<name>` でこれを呼び出し、
全文 Read の代わりに観点別スライスだけを context に取り込む。
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable

from .flow_walk import (
    index_policies_by_trg as _index_policies_by_trg,
    pick_active_branch as _pick_active_branch,
)


# ============================================================
# view 関数本体
# ============================================================


def session_meta(model: dict, **_) -> Any:
    """セッションメタ（旧 .md ヘッダー相当）。"""
    return {"session": model.get("session") or {}}


def narratives(model: dict, **_) -> Any:
    """散文（ハッピーパス + 代替シナリオ）のみ抽出。kind:happy が先頭、kind:alt が後続。"""
    ns = model.get("narratives") or []
    ordered = sorted(
        ns,
        key=lambda n: 0 if isinstance(n, dict) and n.get("kind") == "happy"
        else (1 if isinstance(n, dict) and n.get("kind") == "alt" else 2),
    )
    return {"narratives": ordered}


def open_questions(model: dict, **_) -> Any:
    """status: open の question のみ。"""
    qs = model.get("questions") or []
    open_qs = [q for q in qs if isinstance(q, dict) and q.get("status") != "closed"]
    return {"questions": open_qs}


def all_questions(model: dict, **_) -> Any:
    """すべての question（クローズ済みも含む）。"""
    return {"questions": model.get("questions") or []}


def actions(model: dict, **_) -> Any:
    """次のアクション一覧。"""
    return {"actions": model.get("actions") or []}


def bc_summary(model: dict, **_) -> Any:
    """contexts[] の概要（lang を除外し name / description / up / dn / aggs に絞る）。

    LLM へ BC 構造を渡すときの軽量版。lang は容量が大きいので別 view（bc-language）で扱う。
    """
    contexts = model.get("contexts") or []
    summary = []
    for ctx in contexts:
        if not isinstance(ctx, dict):
            continue
        summary.append(
            {
                k: v
                for k, v in ctx.items()
                if k in ("name", "type", "vision", "description", "up", "dn", "aggs", "sub")
            }
        )
    return {"contexts": summary}


def bc_language(model: dict, *, name: str | None = None, **_) -> Any:
    """`contexts[name].lang` のみ抽出。name が指定されなければ全 BC の lang を辞書化。"""
    contexts = model.get("contexts") or []
    out: dict[str, dict] = {}
    for ctx in contexts:
        if not isinstance(ctx, dict):
            continue
        ctx_name = ctx.get("name")
        if name and ctx_name != name:
            continue
        out[ctx_name] = ctx.get("lang") or {}
    return {"langs": out}


def agg_detail(model: dict, *, name: str | None = None, **_) -> Any:
    """aggregates[] 単体または全体の詳細。"""
    aggregates = model.get("aggregates") or []
    if name:
        for agg in aggregates:
            if isinstance(agg, dict) and agg.get("name") == name:
                return {"agg": agg}
        return {"agg": None}
    return {"aggregates": aggregates}


def _emit_policy_chain(
    evt: str | None, steps: list, visited_pol: set, policies_by_trg: dict[str, list[dict]]
) -> None:
    """evt をトリガーとする policy ステップを再帰挿入（policy.evt 連鎖も辿る）。"""
    if not evt:
        return
    for pol in policies_by_trg.get(evt, []):
        pname = pol.get("name")
        if not pname or pname in visited_pol:
            continue
        visited_pol.add(pname)
        step = {
            "step": pname,
            "kind": "policy",
            "ctx": pol.get("ctx"),
            "trg": pol.get("trg"),
            "cmd": pol.get("cmd"),
            "evt": pol.get("evt"),
        }
        if pol.get("within") is not None:
            step["within"] = pol["within"]  # EVENTUAL-TX の遅延許容 SLA
        steps.append(step)
        if pol.get("evt"):
            _emit_policy_chain(pol["evt"], steps, visited_pol, policies_by_trg)


def _branch_view(br: dict, taken: bool) -> dict:
    """brs 要素を verbatim（cond/evt/pol/next/terminal/after/note）で出し、選択分岐に taken: true を注入。"""
    out = {k: br[k] for k in ("cond", "evt", "pol", "next", "terminal", "after", "note") if k in br}
    if taken:
        out["taken"] = True
    return out


def _spawnable(br: dict, policies_by_trg: dict[str, list[dict]]) -> bool:
    """非選択分岐を sidetrack として展開すべきか: next がある or 分岐 evt が policy を起動する。"""
    return bool(br.get("next")) or br.get("evt") in policies_by_trg


def _walk(
    start: str | None,
    flow_id: str,
    *,
    sc_idx: dict[str, dict],
    policies_by_trg: dict[str, list[dict]],
    visited_sc: set[str],
    queue: deque,
    lead_evt: str | None = None,
) -> list[dict]:
    """start から next 連鎖を辿って step 列を返す（メインパス・sidetrack 共用）。

    - visited_sc は flow 単位でメインパスと全 sidetrack が共有。既出 scenario に到達したら
      {step, kind: scenario-ref} の 1 行参照で停止する（合流・ループの重複展開防止）
    - 非選択分岐は (発生元 scenario 名, br) を queue に積むだけで、ここでは辿らない
    - lead_evt は sidetrack の起点分岐 evt。冒頭でその policy 連鎖を emit する
    - visited_pol は walk 呼び出しごとに新規（同じ補償 policy がメインと sidetrack の
      両方に現れることは許容 — 「見えない」ことによる誤検知の防止を優先）
    """
    steps: list = []
    visited_pol: set[str] = set()
    if lead_evt:
        _emit_policy_chain(lead_evt, steps, visited_pol, policies_by_trg)
    current = start
    while current:
        if current in visited_sc:
            steps.append({"step": current, "kind": "scenario-ref"})
            break
        visited_sc.add(current)
        sc = sc_idx.get(current)
        if sc is None:
            steps.append({"step": current, "kind": "unresolved"})
            break
        active_br = _pick_active_branch(sc, flow_id)
        cur_evt = active_br.get("evt") if active_br else sc.get("evt")
        step: dict = {
            "step": current,
            "kind": "scenario",
            "ctx": sc.get("ctx"),
            "cmd": sc.get("cmd"),
            "evt": cur_evt,
        }
        brs = [br for br in (sc.get("brs") or []) if isinstance(br, dict)]
        if brs:
            step["branches"] = [_branch_view(br, taken=(br is active_br)) for br in brs]
            if sc.get("brMode"):
                step["brMode"] = sc["brMode"]
        terminal_here = bool(active_br and active_br.get("terminal") == flow_id)
        if terminal_here:
            step["terminal"] = flow_id
        steps.append(step)
        for br in brs:
            if br is not active_br and _spawnable(br, policies_by_trg):
                queue.append((current, br))
        if cur_evt:
            _emit_policy_chain(cur_evt, steps, visited_pol, policies_by_trg)
        if terminal_here:
            break
        # 次の scenario を決定: active_br.next を優先、無ければ sc.next（v6 構文）
        br_next = active_br.get("next") if active_br else None
        if br_next:
            current = br_next
            continue
        nv = sc.get("next")
        if isinstance(nv, str):
            current = nv
        elif isinstance(nv, dict):
            nxt = nv.get(flow_id)
            if nxt is None:
                # このフローの継続先が無い next-dict は verbatim 提示して停止
                # （継続は他フローに属することを明示）
                step["next"] = nv
            current = nxt
        else:
            current = None
    return steps


def flow_causality(model: dict, *, id: str | None = None, **_) -> Any:
    """narratives[].entry を起点にフロー連鎖を全分岐込みで抽出（v6 構文 / brs 対応版）。

    フロー因果整合性・Saga 完結性のチェック観点に渡すスリム化スライス。

    出力構造:
    - flows[].steps[]: entry からメインパス（_pick_active_branch が選ぶ分岐）を線形に辿った step 列
      - kind: scenario … {step, ctx, cmd, evt, branches?, brMode?, terminal?, next?}
        - branches: brs 全件を verbatim（cond/evt/pol/next/terminal/note）で列挙し、
          メインパスが辿った分岐に taken: true
        - terminal: 選択分岐の terminal がこのフロー id のときのみ、その flow-id を出す
          （next 省略による暗黙終端にはフィールドを出さない。false の合成はしない）
        - next: sc.next が dict でこのフロー id のキーを持たない場合のみ verbatim 提示
      - kind: policy … scenario/分岐の evt → policy.trg のマッチで自動挿入（policy.evt 連鎖も再帰）
      - kind: scenario-ref … 既出 scenario への合流・ループ。{step} のみ
      - kind: unresolved … next / entry が解決できない参照
    - flows[].sidetracks[]: 非選択分岐（next を持つ or evt が policy を起動するもの）の展開チェーン。
      {from: 分岐元 scenario 名, cond, evt, steps: [...]}。steps の形式はメインパスと同一。
      sidetrack 内でさらに分岐が湧いた場合もネストせずフラットに追加される（from で辿れる）

    `id` で narratives[].id を絞り込み可能。
    """
    narratives = model.get("narratives") or []
    if id:
        narratives = [n for n in narratives if isinstance(n, dict) and n.get("id") == id]

    sc_idx = {s.get("name"): s for s in (model.get("scenarios") or []) if isinstance(s, dict)}
    policies_by_trg = _index_policies_by_trg(model)

    result_flows = []
    for n in narratives:
        if not isinstance(n, dict):
            continue
        entry = n.get("entry")
        if not entry:
            continue
        flow_id = n.get("id") or ""
        visited_sc: set[str] = set()
        queue: deque = deque()
        steps = _walk(
            entry,
            flow_id,
            sc_idx=sc_idx,
            policies_by_trg=policies_by_trg,
            visited_sc=visited_sc,
            queue=queue,
        )
        sidetracks: list = []
        while queue:
            from_name, br = queue.popleft()
            st_steps = _walk(
                br.get("next"),
                flow_id,
                sc_idx=sc_idx,
                policies_by_trg=policies_by_trg,
                visited_sc=visited_sc,
                queue=queue,
                lead_evt=br.get("evt"),
            )
            if not st_steps:
                continue
            st: dict = {"from": from_name}
            if br.get("cond") is not None:
                st["cond"] = br["cond"]
            st["evt"] = br.get("evt")
            st["steps"] = st_steps
            sidetracks.append(st)
        flow: dict = {
            "id": flow_id,
            "title": n.get("title") or flow_id,
            "kind": n.get("kind"),
            "steps": steps,
        }
        if sidetracks:
            flow["sidetracks"] = sidetracks
        result_flows.append(flow)
    return {"flows": result_flows}


def decisions(model: dict, **_) -> Any:
    """意思決定ログ一覧。"""
    return {"decisions": model.get("decisions") or []}


def queries(model: dict, **_) -> Any:
    """リードモデル候補一覧。"""
    return {"queries": model.get("queries") or []}


def scenarios(model: dict, *, ctx: str | None = None, **_) -> Any:
    """scenarios[] を BC（ctx 名）で絞り込んで返す。"""
    scs = model.get("scenarios") or []
    if ctx:
        scs = [s for s in scs if isinstance(s, dict) and s.get("ctx") == ctx]
    return {"scenarios": scs}


def policies(model: dict, *, ctx: str | None = None, **_) -> Any:
    """policies[] を BC で絞り込んで返す。"""
    pols = model.get("policies") or []
    if ctx:
        pols = [p for p in pols if isinstance(p, dict) and p.get("ctx") == ctx]
    return {"policies": pols}


def top_level_keys(model: dict, **_) -> Any:
    """トップレベルキーと各要素数だけを返す（最小スライス・「何が入ってるか」確認用）。"""
    summary: dict[str, Any] = {}
    for key, value in model.items():
        if isinstance(value, list):
            summary[key] = f"list[{len(value)}]"
        elif isinstance(value, dict):
            summary[key] = f"dict[{len(value)} keys]"
        else:
            summary[key] = type(value).__name__
    return {"top_level_keys": summary}


def coverage(model: dict, **_) -> Any:
    """モデル充足度マトリクス。書き漏れのある要素だけを missing フィールド付きで返す。

    フェーズ 5〜6 の「書くべきものが揃っているか」を俯瞰する view。schema 必須キーの
    検証（validate）や参照整合（check）とは別レイヤーで、**任意だが揃っているべき**
    フィールドの欠落を数える。期待フィールド:

    - contexts:   description / lang / aggs
    - aggregates: purpose / background / constraints / states / transitions / attrs /
                  events（+ 各 event の params）
    - scenarios:  rules / errs / evt-or-brs
    - policies:   trg-or-trgs / cmd-or-note（副作用専用 POLICY は cmd 無し note 説明が正当）
    - queries:    purpose / users / sources / formula
    - decisions:  affects / 各 option の why（adopted）・why_not（非 adopted）
    - narratives: kind:happy の存在 / entry
    """

    def _section(items: list, label_key: str, expected) -> dict[str, Any]:
        total = 0
        incomplete = []
        for i, it in enumerate(items or []):
            if not isinstance(it, dict):
                continue
            total += 1
            missing = expected(it)
            if missing:
                incomplete.append(
                    {"name": it.get(label_key) or f"#{i}", "missing": missing}
                )
        return {
            "total": total,
            "complete": total - len(incomplete),
            **({"incomplete": incomplete} if incomplete else {}),
        }

    def _ctx_expected(c: dict) -> list[str]:
        return [f for f in ("description", "lang", "aggs") if not c.get(f)]

    def _agg_expected(a: dict) -> list[str]:
        missing = [
            f
            for f in ("purpose", "background", "constraints", "states", "transitions", "attrs", "events")
            if not a.get(f)
        ]
        noparams = [
            ev.get("name") or "?"
            for ev in (a.get("events") or [])
            if isinstance(ev, dict) and not ev.get("params")
        ]
        if noparams:
            missing.append(f"events[].params ({', '.join(noparams)})")
        return missing

    def _scenario_expected(s: dict) -> list[str]:
        missing = [f for f in ("rules", "errs") if not s.get(f)]
        if not s.get("evt") and not s.get("brs"):
            missing.append("evt|brs")
        return missing

    def _policy_expected(p: dict) -> list[str]:
        missing = []
        if not p.get("trg") and not p.get("trgs"):
            missing.append("trg|trgs")
        if not p.get("cmd") and not p.get("note"):
            missing.append("cmd|note")  # 副作用専用なら note で説明する
        return missing

    def _query_expected(q: dict) -> list[str]:
        return [f for f in ("purpose", "users", "sources", "formula") if not q.get(f)]

    def _decision_expected(d: dict) -> list[str]:
        missing = []
        if not d.get("affects"):
            missing.append("affects")
        for o in d.get("options") or []:
            if not isinstance(o, dict):
                continue
            oname = o.get("name") or "?"
            if o.get("adopted") is True and not o.get("why"):
                missing.append(f"options[{oname}].why")
            if o.get("adopted") is not True and not o.get("why_not"):
                missing.append(f"options[{oname}].why_not")
        return missing

    def _narrative_expected(n: dict) -> list[str]:
        return ["entry"] if not n.get("entry") else []

    result: dict[str, Any] = {
        "contexts": _section(model.get("contexts") or [], "name", _ctx_expected),
        "aggregates": _section(model.get("aggregates") or [], "name", _agg_expected),
        "scenarios": _section(model.get("scenarios") or [], "name", _scenario_expected),
        "policies": _section(model.get("policies") or [], "name", _policy_expected),
        "queries": _section(model.get("queries") or [], "name", _query_expected),
        "decisions": _section(model.get("decisions") or [], "id", _decision_expected),
        "narratives": _section(model.get("narratives") or [], "id", _narrative_expected),
    }
    has_happy = any(
        isinstance(n, dict) and n.get("kind") == "happy"
        for n in (model.get("narratives") or [])
    )
    if not has_happy:
        result["narratives"]["missing_happy"] = True
    return {"coverage": result}


def full(model: dict, **_) -> Any:
    """全文をそのまま返す（安全弁・サイズ警告は呼び出し側で）。"""
    return model


# ============================================================
# レジストリ（dmlctl view --view=<name> で参照される）
# ============================================================


VIEWS: dict[str, Callable[..., Any]] = {
    "session-meta": session_meta,
    "narratives": narratives,
    "open-questions": open_questions,
    "all-questions": all_questions,
    "actions": actions,
    "bc-summary": bc_summary,
    "bc-language": bc_language,
    "agg-detail": agg_detail,
    "flow-causality": flow_causality,
    "decisions": decisions,
    "queries": queries,
    "scenarios": scenarios,
    "policies": policies,
    "top-level-keys": top_level_keys,
    "coverage": coverage,
    "full": full,
}
