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


def story(model: dict, **_) -> Any:
    """ハッピーパスと代替シナリオ散文のみ抽出。"""
    return {
        "story": model.get("story") or "",
        "narratives": model.get("narratives") or [],
    }


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
    """ctxs[] の概要（lang を除外し name / description / up / dn / aggs に絞る）。

    LLM へ BC 構造を渡すときの軽量版。lang は容量が大きいので別 view（bc-language）で扱う。
    """
    ctxs = model.get("ctxs") or []
    summary = []
    for ctx in ctxs:
        if not isinstance(ctx, dict):
            continue
        summary.append(
            {
                k: v
                for k, v in ctx.items()
                if k in ("name", "type", "vision", "description", "up", "dn", "aggs", "sub")
            }
        )
    return {"ctxs": summary}


def bc_language(model: dict, *, name: str | None = None, **_) -> Any:
    """`ctxs[name].lang` のみ抽出。name が指定されなければ全 BC の lang を辞書化。"""
    ctxs = model.get("ctxs") or []
    out: dict[str, dict] = {}
    for ctx in ctxs:
        if not isinstance(ctx, dict):
            continue
        ctx_name = ctx.get("name")
        if name and ctx_name != name:
            continue
        out[ctx_name] = ctx.get("lang") or {}
    return {"langs": out}


def agg_detail(model: dict, *, name: str | None = None, **_) -> Any:
    """aggs[] 単体または全体の詳細。"""
    aggs = model.get("aggs") or []
    if name:
        for agg in aggs:
            if isinstance(agg, dict) and agg.get("name") == name:
                return {"agg": agg}
        return {"agg": None}
    return {"aggs": aggs}


def flow_causality(model: dict, *, id: str | None = None, **_) -> Any:
    """flows[] と関連する scs[] / pols[] の id/name/cmd/evt だけを抽出。

    フロー因果整合性のチェック観点に渡すスリム化スライス。
    """
    flows = model.get("flows") or []
    if id:
        flows = [f for f in flows if isinstance(f, dict) and f.get("id") == id]

    scs_idx = {s.get("name"): s for s in (model.get("scs") or []) if isinstance(s, dict)}
    pols_idx = {p.get("name"): p for p in (model.get("pols") or []) if isinstance(p, dict)}

    result_flows = []
    for f in flows:
        if not isinstance(f, dict):
            continue
        steps = []
        for step in f.get("steps") or []:
            ref = scs_idx.get(step) or pols_idx.get(step)
            if ref is None:
                steps.append({"step": step, "kind": "unresolved"})
                continue
            kind = "scenario" if step in scs_idx else "policy"
            steps.append(
                {
                    "step": step,
                    "kind": kind,
                    "ctx": ref.get("ctx"),
                    "cmd": ref.get("cmd"),
                    "evt": ref.get("evt"),
                    "trg": ref.get("trg"),
                }
            )
        result_flows.append({"id": f.get("id"), "title": f.get("title"), "steps": steps})
    return {"flows": result_flows}


def decisions(model: dict, **_) -> Any:
    """意思決定ログ一覧。"""
    return {"decisions": model.get("decisions") or []}


def qrys(model: dict, **_) -> Any:
    """リードモデル候補一覧。"""
    return {"qrys": model.get("qrys") or []}


def scenarios(model: dict, *, ctx: str | None = None, **_) -> Any:
    """scs[] を BC（ctx 名）で絞り込んで返す。"""
    scs = model.get("scs") or []
    if ctx:
        scs = [s for s in scs if isinstance(s, dict) and s.get("ctx") == ctx]
    return {"scs": scs}


def policies(model: dict, *, ctx: str | None = None, **_) -> Any:
    """pols[] を BC で絞り込んで返す。"""
    pols = model.get("pols") or []
    if ctx:
        pols = [p for p in pols if isinstance(p, dict) and p.get("ctx") == ctx]
    return {"pols": pols}


# ============================================================
# レジストリ（dmlctl view --view=<name> で参照される）
# ============================================================


VIEWS: dict[str, Callable[..., Any]] = {
    "session-meta": session_meta,
    "story": story,
    "open-questions": open_questions,
    "all-questions": all_questions,
    "actions": actions,
    "bc-summary": bc_summary,
    "bc-language": bc_language,
    "agg-detail": agg_detail,
    "flow-causality": flow_causality,
    "decisions": decisions,
    "qrys": qrys,
    "scenarios": scenarios,
    "policies": policies,
}
