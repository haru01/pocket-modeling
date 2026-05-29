"""DML 観点別 view 関数群。

各 view は `model: dict` を入力に取り、観点に関連する **最小限の dict**（YAML / JSON / Markdown
にダンプ可能）を返す。AI は `dmlctl view --view=<name>` でこれを呼び出し、
全文 Read の代わりに観点別スライスだけを context に取り込む。
"""

from __future__ import annotations

from typing import Any, Callable


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


def flow_causality(model: dict, *, id: str | None = None, **_) -> Any:
    """narratives[].entry を起点に scenarios[].next を辿って各フローのステップ列を抽出（v6）。

    フロー因果整合性のチェック観点に渡すスリム化スライス。policy ステップは
    scenario.evt → policy.trg のマッチで自動挿入する（再帰的に policy.evt 連鎖も辿る）。

    `id` で narratives[].id を絞り込み可能。
    """
    narratives = model.get("narratives") or []
    if id:
        narratives = [n for n in narratives if isinstance(n, dict) and n.get("id") == id]

    sc_idx = {s.get("name"): s for s in (model.get("scenarios") or []) if isinstance(s, dict)}
    policies = [p for p in (model.get("policies") or []) if isinstance(p, dict)]
    policies_by_trg: dict[str, list[dict]] = {}
    for p in policies:
        trg = p.get("trg")
        if trg:
            policies_by_trg.setdefault(trg, []).append(p)
        trgs = p.get("trgs") or {}
        if isinstance(trgs, dict):
            for ev in trgs.get("evts") or []:
                policies_by_trg.setdefault(ev, []).append(p)

    def pick_active_branch(sc: dict, flow_id: str) -> dict | None:
        brs = sc.get("brs") or []
        if not brs:
            return None
        for br in brs:
            if isinstance(br, dict) and br.get("terminal") == flow_id:
                return br
        for br in brs:
            if isinstance(br, dict) and not br.get("terminal"):
                return br
        return brs[0] if isinstance(brs[0], dict) else None

    def emit_policy_chain(evt: str, steps: list, visited: set) -> None:
        if not evt:
            return
        for pol in policies_by_trg.get(evt, []):
            pname = pol.get("name")
            if not pname or pname in visited:
                continue
            visited.add(pname)
            steps.append(
                {
                    "step": pname,
                    "kind": "policy",
                    "ctx": pol.get("ctx"),
                    "trg": pol.get("trg"),
                    "cmd": pol.get("cmd"),
                    "evt": pol.get("evt"),
                }
            )
            if pol.get("evt"):
                emit_policy_chain(pol["evt"], steps, visited)

    result_flows = []
    for n in narratives:
        if not isinstance(n, dict):
            continue
        entry = n.get("entry")
        if not entry:
            continue
        flow_id = n.get("id") or ""
        steps: list = []
        visited_sc: set[str] = set()
        visited_pol: set[str] = set()
        current = entry
        while current and current not in visited_sc:
            visited_sc.add(current)
            sc = sc_idx.get(current)
            if sc is None:
                steps.append({"step": current, "kind": "unresolved"})
                break
            active_br = pick_active_branch(sc, flow_id)
            cur_evt = active_br.get("evt") if active_br else sc.get("evt")
            steps.append(
                {
                    "step": current,
                    "kind": "scenario",
                    "ctx": sc.get("ctx"),
                    "cmd": sc.get("cmd"),
                    "evt": cur_evt,
                    "terminal": bool(active_br and active_br.get("terminal") == flow_id),
                }
            )
            if cur_evt:
                emit_policy_chain(cur_evt, steps, visited_pol)
            if active_br and active_br.get("terminal") == flow_id:
                break
            # 次の scenario を決定: active_br.next を優先、無ければ sc.next（v6 構文）
            br_next = active_br.get("next") if active_br else None
            if br_next:
                current = br_next
            else:
                nv = sc.get("next")
                if isinstance(nv, str):
                    current = nv
                elif isinstance(nv, dict):
                    current = nv.get(flow_id)
                else:
                    current = None
        result_flows.append(
            {"id": flow_id, "title": n.get("title") or flow_id, "kind": n.get("kind"), "steps": steps}
        )
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
}
