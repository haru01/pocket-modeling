"""DML 構造チェック観点別関数群。

各関数は `model: dict` を入力に取り、違反一覧（list[Finding]）を返す。違反 0 件＝合格。

これらは **LLM を呼ばない純構造チェック**。意味チェック（観点別 LLM プロンプト）は
`references/checks/*.md` を Agent から起動する形で行う。両者の連携は
`references/quality-check.md` を参照。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# ============================================================
# 共通: Finding 構造
# ============================================================


@dataclass
class Finding:
    kind: str                              # チェック名（orphan_agg / dangling_cmd / ...）
    path: str                              # 違反箇所の YAML パス（例: aggs[2]）
    message: str                           # 違反内容の日本語サマリ
    slice: dict[str, Any] = field(default_factory=dict)  # LLM への補助スライス（任意）


def finding_to_dict(f: Finding) -> dict[str, Any]:
    return {"kind": f.kind, "path": f.path, "message": f.message, "slice": f.slice}


# ============================================================
# 個別チェック
# ============================================================


def orphan_agg(model: dict) -> list[Finding]:
    """どの scs[].agg からも参照されない AGG を列挙する。"""
    aggs = model.get("aggs") or []
    scs = model.get("scs") or []
    pols = model.get("pols") or []
    referenced: set[str] = set()
    for s in scs:
        if isinstance(s, dict) and s.get("agg"):
            referenced.add(s["agg"])
    # pols は AGG ではなく EVT/CMD を持つので scs だけ走査するが、
    # AGG を `pols[].agg` で明示するスキーマ拡張時のため一応見る（v5 では未定義 OK）。
    for p in pols:
        if isinstance(p, dict) and p.get("agg"):
            referenced.add(p["agg"])

    findings: list[Finding] = []
    for i, agg in enumerate(aggs):
        if not isinstance(agg, dict):
            continue
        name = agg.get("name") or ""
        if name and name not in referenced:
            findings.append(
                Finding(
                    kind="orphan_agg",
                    path=f"aggs[{i}]",
                    message=f"AGG '{name}' はどの scenario からも参照されていません",
                    slice={"agg": name, "ctx": agg.get("ctx")},
                )
            )
    return findings


def dangling_cmd(model: dict) -> list[Finding]:
    """aggs[].transitions[].via が scs[].cmd のいずれにも一致しない場合に警告する。"""
    scs = model.get("scs") or []
    aggs = model.get("aggs") or []
    declared_cmds: set[str] = {
        s["cmd"] for s in scs if isinstance(s, dict) and s.get("cmd")
    }
    findings: list[Finding] = []
    for i, agg in enumerate(aggs):
        if not isinstance(agg, dict):
            continue
        agg_name = agg.get("name") or ""
        transitions = agg.get("transitions") or []
        for j, tr in enumerate(transitions):
            if not isinstance(tr, dict):
                continue
            via = tr.get("via")
            if via and via not in declared_cmds:
                findings.append(
                    Finding(
                        kind="dangling_cmd",
                        path=f"aggs[{i}].transitions[{j}].via",
                        message=f"AGG '{agg_name}' の遷移 via '{via}' が scs[].cmd に未宣言",
                        slice={"agg": agg_name, "via": via, "transition": tr},
                    )
                )
    return findings


def unknown_evt_in_policy(model: dict) -> list[Finding]:
    """pols[].trg / pols[].trgs.evts が aggs[].events[].name に未宣言ならフラグ。"""
    aggs = model.get("aggs") or []
    declared_evts: set[str] = set()
    for agg in aggs:
        if not isinstance(agg, dict):
            continue
        for ev in agg.get("events") or []:
            if isinstance(ev, dict) and ev.get("name"):
                declared_evts.add(ev["name"])

    # scs[].evt と scs[].brs[].evt も宣言済み扱い（実運用で aggs に書き忘れる例あり）
    for s in model.get("scs") or []:
        if not isinstance(s, dict):
            continue
        if s.get("evt"):
            declared_evts.add(s["evt"])
        for br in s.get("brs") or []:
            if isinstance(br, dict) and br.get("evt"):
                declared_evts.add(br["evt"])

    findings: list[Finding] = []
    for i, pol in enumerate(model.get("pols") or []):
        if not isinstance(pol, dict):
            continue
        name = pol.get("name") or ""
        trg = pol.get("trg")
        if trg and trg not in declared_evts:
            findings.append(
                Finding(
                    kind="unknown_evt_in_policy",
                    path=f"pols[{i}].trg",
                    message=f"POL '{name}' のトリガー '{trg}' が EVT として宣言されていません",
                    slice={"policy": name, "trg": trg},
                )
            )
        trgs = pol.get("trgs") or {}
        if isinstance(trgs, dict):
            for k, ev in enumerate(trgs.get("evts") or []):
                if ev and ev not in declared_evts:
                    findings.append(
                        Finding(
                            kind="unknown_evt_in_policy",
                            path=f"pols[{i}].trgs.evts[{k}]",
                            message=f"POL '{name}' の join トリガー '{ev}' が EVT として宣言されていません",
                            slice={"policy": name, "evt": ev},
                        )
                    )
    return findings


def language_coverage(model: dict) -> list[Finding]:
    """`ctxs[].lang` に登録されていない名前付き要素を列挙する。

    語彙辞書の網羅性チェック。HTML フロー図のラベル日本語化に使うため、
    scs[].cmd / scs[].evt / pols[].name / aggs[].name / aggs[].events[].name が
    どこかの ctxs[].lang.{cmds/evts/pols/aggs} に登録されているか確認する。
    """
    ctxs = model.get("ctxs") or []
    registered: set[str] = set()
    for ctx in ctxs:
        if not isinstance(ctx, dict):
            continue
        lang = ctx.get("lang") or {}
        if not isinstance(lang, dict):
            continue
        for cat in ("aggs", "actors", "cmds", "evts", "pols", "qrys", "vos"):
            cat_dict = lang.get(cat) or {}
            if isinstance(cat_dict, dict):
                registered.update(cat_dict.keys())

    findings: list[Finding] = []

    def _check(items: list, getter, kind_label: str, path_prefix: str) -> None:
        for i, it in enumerate(items or []):
            if not isinstance(it, dict):
                continue
            name = getter(it)
            if not name:
                continue
            if name not in registered:
                findings.append(
                    Finding(
                        kind="language_coverage",
                        path=f"{path_prefix}[{i}]",
                        message=f"{kind_label} '{name}' が ctxs[].lang に未登録",
                        slice={"identifier": name, "kind": kind_label},
                    )
                )

    _check(model.get("aggs") or [], lambda x: x.get("name"), "AGG", "aggs")
    _check(model.get("scs") or [], lambda x: x.get("cmd"), "CMD", "scs")
    _check(model.get("scs") or [], lambda x: x.get("evt"), "EVT", "scs")
    _check(model.get("pols") or [], lambda x: x.get("name"), "POL", "pols")
    return findings


def state_reachability(model: dict) -> list[Finding]:
    """aggs[].transitions による状態到達可能性を検査する。

    `aggs[].states` のうち、遷移グラフから到達できない（=どの to にも現れない）状態を
    「孤立状態」として報告する。ただし AGG の初期状態（先頭 state）は除外する。
    """
    findings: list[Finding] = []
    for i, agg in enumerate(model.get("aggs") or []):
        if not isinstance(agg, dict):
            continue
        states = agg.get("states") or []
        if not states:
            continue
        initial = states[0] if states else None
        targets: set[str] = set()
        for tr in agg.get("transitions") or []:
            if not isinstance(tr, dict):
                continue
            to = tr.get("to")
            if isinstance(to, list):
                targets.update(to)
            elif to:
                targets.add(to)

        for state in states:
            if state == initial:
                continue
            if state not in targets:
                findings.append(
                    Finding(
                        kind="state_reachability",
                        path=f"aggs[{i}].states",
                        message=f"AGG '{agg.get('name')}' の状態 '{state}' へ遷移する transitions[] が見つかりません",
                        slice={"agg": agg.get("name"), "unreachable": state},
                    )
                )
    return findings


def orphan_event(model: dict) -> list[Finding]:
    """aggs[].events で宣言されたが、どの scs/pols/flows からも参照されていない EVT。"""
    referenced: set[str] = set()
    for s in model.get("scs") or []:
        if not isinstance(s, dict):
            continue
        if s.get("evt"):
            referenced.add(s["evt"])
        for br in s.get("brs") or []:
            if isinstance(br, dict) and br.get("evt"):
                referenced.add(br["evt"])
    for p in model.get("pols") or []:
        if not isinstance(p, dict):
            continue
        if p.get("trg"):
            referenced.add(p["trg"])
        trgs = p.get("trgs") or {}
        if isinstance(trgs, dict):
            for ev in trgs.get("evts") or []:
                referenced.add(ev)
        if p.get("evt"):
            referenced.add(p["evt"])

    findings: list[Finding] = []
    for i, agg in enumerate(model.get("aggs") or []):
        if not isinstance(agg, dict):
            continue
        for j, ev in enumerate(agg.get("events") or []):
            if not isinstance(ev, dict):
                continue
            name = ev.get("name") or ""
            if name and name not in referenced:
                findings.append(
                    Finding(
                        kind="orphan_event",
                        path=f"aggs[{i}].events[{j}]",
                        message=f"EVT '{name}' は AGG '{agg.get('name')}' で emit 宣言されているが参照されていません",
                        slice={"agg": agg.get("name"), "evt": name},
                    )
                )
    return findings


def flow_step_resolution(model: dict) -> list[Finding]:
    """flows[].steps[] が scs[].name または pols[].name に解決できない場合フラグ。"""
    scs_names = {s.get("name") for s in (model.get("scs") or []) if isinstance(s, dict)}
    pol_names = {p.get("name") for p in (model.get("pols") or []) if isinstance(p, dict)}
    known = scs_names | pol_names

    findings: list[Finding] = []
    for i, f in enumerate(model.get("flows") or []):
        if not isinstance(f, dict):
            continue
        flow_id = f.get("id") or ""
        for j, step in enumerate(f.get("steps") or []):
            if step and step not in known:
                findings.append(
                    Finding(
                        kind="flow_step_resolution",
                        path=f"flows[{i}].steps[{j}]",
                        message=f"flow '{flow_id}' のステップ '{step}' が scs/pols のいずれにも解決できません",
                        slice={"flow": flow_id, "step": step},
                    )
                )
    return findings


def question_decision_link(model: dict) -> list[Finding]:
    """questions[].status==closed の decision_id が decisions[].id と整合するか確認。"""
    decision_ids = {
        d.get("id") for d in (model.get("decisions") or []) if isinstance(d, dict)
    }
    findings: list[Finding] = []
    for i, q in enumerate(model.get("questions") or []):
        if not isinstance(q, dict):
            continue
        if q.get("status") != "closed":
            continue
        did = q.get("decision_id")
        qid = q.get("id") or ""
        if not did:
            findings.append(
                Finding(
                    kind="question_decision_link",
                    path=f"questions[{i}].decision_id",
                    message=f"question '{qid}' が closed なのに decision_id が無い",
                    slice={"question": qid},
                )
            )
            continue
        if did not in decision_ids:
            findings.append(
                Finding(
                    kind="question_decision_link",
                    path=f"questions[{i}].decision_id",
                    message=f"question '{qid}' の decision_id '{did}' が decisions[].id に存在しない",
                    slice={"question": qid, "decision_id": did},
                )
            )
    return findings


# ============================================================
# レジストリ
# ============================================================


CHECKS: dict[str, Callable[[dict], list[Finding]]] = {
    "orphan_agg": orphan_agg,
    "dangling_cmd": dangling_cmd,
    "unknown_evt_in_policy": unknown_evt_in_policy,
    "language_coverage": language_coverage,
    "state_reachability": state_reachability,
    "orphan_event": orphan_event,
    "flow_step_resolution": flow_step_resolution,
    "question_decision_link": question_decision_link,
}
