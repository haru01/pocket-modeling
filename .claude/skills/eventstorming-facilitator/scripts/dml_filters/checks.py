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
    path: str                              # 違反箇所の YAML パス（例: aggregates[2]）
    message: str                           # 違反内容の日本語サマリ
    slice: dict[str, Any] = field(default_factory=dict)  # LLM への補助スライス（任意）


def finding_to_dict(f: Finding) -> dict[str, Any]:
    return {"kind": f.kind, "path": f.path, "message": f.message, "slice": f.slice}


# ============================================================
# 個別チェック
# ============================================================


def orphan_agg(model: dict) -> list[Finding]:
    """どの scenarios[].agg からも参照されない AGG を列挙する。"""
    aggregates = model.get("aggregates") or []
    scenarios = model.get("scenarios") or []
    policies = model.get("policies") or []
    referenced: set[str] = set()
    for s in scenarios:
        if isinstance(s, dict) and s.get("agg"):
            referenced.add(s["agg"])
    # policies は AGG ではなく EVT/CMD を持つので scenarios だけ走査するが、
    # AGG を `policies[].agg` で明示するスキーマ拡張時のため一応見る（v5 では未定義 OK）。
    for p in policies:
        if isinstance(p, dict) and p.get("agg"):
            referenced.add(p["agg"])

    findings: list[Finding] = []
    for i, agg in enumerate(aggregates):
        if not isinstance(agg, dict):
            continue
        name = agg.get("name") or ""
        if name and name not in referenced:
            findings.append(
                Finding(
                    kind="orphan_agg",
                    path=f"aggregates[{i}]",
                    message=f"AGG '{name}' はどの scenario からも参照されていません",
                    slice={"agg": name, "ctx": agg.get("ctx")},
                )
            )
    return findings


def dangling_cmd(model: dict) -> list[Finding]:
    """aggregates[].transitions[].via が scenarios[].cmd / policies[].cmd に一致しない場合に警告する。

    v7: 内部 CMD（時刻駆動・外部コールバック・副作用）は scenario でなく policy.cmd として
    宣言されるケースも実体として正当なので、両方をチェック対象に含める。
    """
    scenarios = model.get("scenarios") or []
    policies = model.get("policies") or []
    aggregates = model.get("aggregates") or []
    declared_cmds: set[str] = {
        s["cmd"] for s in scenarios if isinstance(s, dict) and s.get("cmd")
    }
    declared_cmds |= {
        p["cmd"] for p in policies if isinstance(p, dict) and p.get("cmd")
    }
    findings: list[Finding] = []
    for i, agg in enumerate(aggregates):
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
                        path=f"aggregates[{i}].transitions[{j}].via",
                        message=f"AGG '{agg_name}' の遷移 via '{via}' が scenarios[].cmd に未宣言",
                        slice={"agg": agg_name, "via": via, "transition": tr},
                    )
                )
    return findings


def unknown_evt_in_policy(model: dict) -> list[Finding]:
    """policies[].trg / policies[].trgs.evts が aggregates[].events[].name に未宣言ならフラグ。"""
    aggregates = model.get("aggregates") or []
    declared_evts: set[str] = set()
    for agg in aggregates:
        if not isinstance(agg, dict):
            continue
        for ev in agg.get("events") or []:
            if isinstance(ev, dict) and ev.get("name"):
                declared_evts.add(ev["name"])

    # scenarios[].evt と scenarios[].brs[].evt も宣言済み扱い（実運用で aggregates に書き忘れる例あり）
    for s in model.get("scenarios") or []:
        if not isinstance(s, dict):
            continue
        if s.get("evt"):
            declared_evts.add(s["evt"])
        for br in s.get("brs") or []:
            if isinstance(br, dict) and br.get("evt"):
                declared_evts.add(br["evt"])

    findings: list[Finding] = []
    for i, pol in enumerate(model.get("policies") or []):
        if not isinstance(pol, dict):
            continue
        name = pol.get("name") or ""
        trg = pol.get("trg")
        if trg and trg not in declared_evts:
            findings.append(
                Finding(
                    kind="unknown_evt_in_policy",
                    path=f"policies[{i}].trg",
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
                            path=f"policies[{i}].trgs.evts[{k}]",
                            message=f"POL '{name}' の join トリガー '{ev}' が EVT として宣言されていません",
                            slice={"policy": name, "evt": ev},
                        )
                    )
    return findings


def language_coverage(model: dict) -> list[Finding]:
    """`contexts[].lang` に登録されていない名前付き要素を列挙する。

    語彙辞書の網羅性チェック。HTML フロー図のラベル日本語化に使うため、
    scenarios[].cmd / scenarios[].evt / policies[].name / aggregates[].name / aggregates[].events[].name が
    どこかの contexts[].lang.{cmds/evts/pols/aggs} に登録されているか確認する。
    """
    contexts = model.get("contexts") or []
    registered: set[str] = set()
    for ctx in contexts:
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
                        message=f"{kind_label} '{name}' が contexts[].lang に未登録",
                        slice={"identifier": name, "kind": kind_label},
                    )
                )

    _check(model.get("aggregates") or [], lambda x: x.get("name"), "AGG", "aggregates")
    _check(model.get("scenarios") or [], lambda x: x.get("cmd"), "CMD", "scenarios")
    _check(model.get("scenarios") or [], lambda x: x.get("evt"), "EVT", "scenarios")
    _check(model.get("policies") or [], lambda x: x.get("name"), "POL", "policies")
    return findings


def state_reachability(model: dict) -> list[Finding]:
    """aggregates[].transitions による状態到達可能性を検査する。

    `aggregates[].states` のうち、遷移グラフから到達できない（=どの to にも現れない）状態を
    「孤立状態」として報告する。ただし AGG の初期状態（先頭 state）は除外する。
    """
    findings: list[Finding] = []
    for i, agg in enumerate(model.get("aggregates") or []):
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
                        path=f"aggregates[{i}].states",
                        message=f"AGG '{agg.get('name')}' の状態 '{state}' へ遷移する transitions[] が見つかりません",
                        slice={"agg": agg.get("name"), "unreachable": state},
                    )
                )
    return findings


def orphan_event(model: dict) -> list[Finding]:
    """aggregates[].events で宣言されたが、どの scenarios/policies からも参照されていない EVT。

    v7: `events[].terminal: true` のイベントは「業務的にここで止まる」終端イベント
    （失敗系・タイムアウト系など）として orphan 判定から除外する。
    """
    referenced: set[str] = set()
    for s in model.get("scenarios") or []:
        if not isinstance(s, dict):
            continue
        if s.get("evt"):
            referenced.add(s["evt"])
        for br in s.get("brs") or []:
            if isinstance(br, dict) and br.get("evt"):
                referenced.add(br["evt"])
    for p in model.get("policies") or []:
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
    for i, agg in enumerate(model.get("aggregates") or []):
        if not isinstance(agg, dict):
            continue
        for j, ev in enumerate(agg.get("events") or []):
            if not isinstance(ev, dict):
                continue
            name = ev.get("name") or ""
            if not name or name in referenced:
                continue
            if ev.get("terminal") is True:
                continue  # v7: 明示終端は orphan 扱いしない
            findings.append(
                Finding(
                    kind="orphan_event",
                    path=f"aggregates[{i}].events[{j}]",
                    message=f"EVT '{name}' は AGG '{agg.get('name')}' で emit 宣言されているが参照されていません",
                    slice={"agg": agg.get("name"), "evt": name},
                )
            )
    return findings


def flow_chain_resolution(model: dict) -> list[Finding]:
    """フロー連鎖（v6）の参照整合性チェック。

    検出対象:
      - narratives[].entry が scenarios[].name に解決できない
      - scenarios[].next（string / dict 値）が scenarios[].name に解決できない
      - scenarios[].next が dict 形式の時、キーが narratives[].id に存在しない
      - scenarios[].brs[].next が scenarios[].name に解決できない
      - scenarios[].brs[].terminal が narratives[].id に存在しない
    """
    scs_names = {s.get("name") for s in (model.get("scenarios") or []) if isinstance(s, dict)}
    narrative_ids = {
        n.get("id") for n in (model.get("narratives") or []) if isinstance(n, dict)
    }

    findings: list[Finding] = []

    for i, n in enumerate(model.get("narratives") or []):
        if not isinstance(n, dict):
            continue
        entry = n.get("entry")
        nid = n.get("id") or ""
        if entry and entry not in scs_names:
            findings.append(
                Finding(
                    kind="flow_chain_resolution",
                    path=f"narratives[{i}].entry",
                    message=f"narrative '{nid}' の entry '{entry}' が scenarios[].name に解決できません",
                    slice={"narrative": nid, "entry": entry},
                )
            )

    for i, s in enumerate(model.get("scenarios") or []):
        if not isinstance(s, dict):
            continue
        sname = s.get("name") or ""

        # next: string or dict
        next_value = s.get("next")
        if isinstance(next_value, str):
            if next_value not in scs_names:
                findings.append(
                    Finding(
                        kind="flow_chain_resolution",
                        path=f"scenarios[{i}].next",
                        message=f"scenario '{sname}' の next '{next_value}' が scenarios[].name に解決できません",
                        slice={"scenario": sname, "next": next_value},
                    )
                )
        elif isinstance(next_value, dict):
            for fid, target in next_value.items():
                if narrative_ids and fid not in narrative_ids:
                    findings.append(
                        Finding(
                            kind="flow_chain_resolution",
                            path=f"scenarios[{i}].next.{fid}",
                            message=f"scenario '{sname}' の next キー '{fid}' が narratives[].id に存在しません",
                            slice={"scenario": sname, "flow_id": fid},
                        )
                    )
                if isinstance(target, str) and target and target not in scs_names:
                    findings.append(
                        Finding(
                            kind="flow_chain_resolution",
                            path=f"scenarios[{i}].next.{fid}",
                            message=f"scenario '{sname}' の next.{fid} '{target}' が scenarios[].name に解決できません",
                            slice={"scenario": sname, "flow_id": fid, "next": target},
                        )
                    )

        # brs[].next / brs[].terminal
        for j, br in enumerate(s.get("brs") or []):
            if not isinstance(br, dict):
                continue
            br_next = br.get("next")
            if br_next and br_next not in scs_names:
                findings.append(
                    Finding(
                        kind="flow_chain_resolution",
                        path=f"scenarios[{i}].brs[{j}].next",
                        message=f"scenario '{sname}' brs[{j}] の next '{br_next}' が scenarios[].name に解決できません",
                        slice={"scenario": sname, "next": br_next},
                    )
                )
            term = br.get("terminal")
            if term and narrative_ids and term not in narrative_ids:
                findings.append(
                    Finding(
                        kind="flow_chain_resolution",
                        path=f"scenarios[{i}].brs[{j}].terminal",
                        message=f"scenario '{sname}' brs[{j}] の terminal '{term}' が narratives[].id に存在しません",
                        slice={"scenario": sname, "terminal": term},
                    )
                )

    return findings


def narrative_entry_consistency(model: dict) -> list[Finding]:
    """複数の narrative が同一 scenario を `entry` に指す場合、
    対応する scenarios[].next が narrative.id をキーとする dict 形式に
    なっているかを検証する（v6 規約）。

    そうでないと、すべての narrative が同じフローを描画してしまい、
    意味チェック agent が「フロー broken」と誤検出する原因になる。

    OK パターン：
      - scenarios[].next が dict 形式で全 narrative.id をカバー
      - 漏れている narrative.id が brs[].terminal で別途終端宣言されている
    """
    narratives = model.get("narratives") or []
    scenarios = model.get("scenarios") or []
    by_name: dict[str, dict] = {
        s.get("name"): s for s in scenarios
        if isinstance(s, dict) and s.get("name")
    }

    by_entry: dict[str, list[str]] = {}
    for n in narratives:
        if not isinstance(n, dict):
            continue
        entry = n.get("entry")
        nid = n.get("id")
        if entry and nid:
            by_entry.setdefault(entry, []).append(nid)

    findings: list[Finding] = []
    for entry_name, nids in by_entry.items():
        if len(nids) < 2:
            continue
        sc = by_name.get(entry_name)
        if not sc:
            # flow_chain_resolution で別途検出されるためここはスキップ
            continue

        # brs[].terminal で narrative ごとに終端宣言されているものを集計
        terminal_narratives: set[str] = set()
        for br in sc.get("brs") or []:
            if isinstance(br, dict) and br.get("terminal"):
                terminal_narratives.add(br["terminal"])

        nxt = sc.get("next")
        if isinstance(nxt, dict):
            # dict 形式 — narrative ID 全てがキー or terminal でカバーされているか
            missing = [
                nid for nid in nids
                if nid not in nxt and nid not in terminal_narratives
            ]
            if missing:
                findings.append(
                    Finding(
                        kind="narrative_entry_consistency",
                        path=f"scenarios[].next",
                        message=(
                            f"narratives {nids} が entry '{entry_name}' を共有していますが、"
                            f"scenario.next dict に {missing} のキーが無く、brs[].terminal でも"
                            f"終端宣言されていません"
                        ),
                        slice={
                            "entry": entry_name,
                            "shared_by": nids,
                            "missing_keys": missing,
                        },
                    )
                )
        else:
            # 単一値 or 未設定 — brs[].terminal で各 narrative が個別に終端
            # 宣言されていれば OK、そうでなければ全 narrative が同じフローを辿る
            unhandled = [nid for nid in nids if nid not in terminal_narratives]
            if len(unhandled) >= 2:
                findings.append(
                    Finding(
                        kind="narrative_entry_consistency",
                        path=f"scenarios[].next",
                        message=(
                            f"narratives {unhandled} が entry '{entry_name}' を共有しているのに、"
                            f"scenario.next が単一値（または未設定）です。narrative.id をキーとする"
                            f"dict 形式に書き換えるか、brs[].terminal でフロー別に終端宣言してください"
                            f"（dml-spec.md v6 規約）"
                        ),
                        slice={
                            "entry": entry_name,
                            "shared_by": unhandled,
                            "current_next": nxt,
                        },
                    )
                )
    return findings


def narrative_happy_unique(model: dict) -> list[Finding]:
    """`kind: happy` の narrative は 0 or 1 件であることを確認する（v8）。

    ハッピーパスは「正規フロー」を 1 本だけ示す概念なので、複数 happy が宣言された場合は
    モデリングミスとみなす（旧トップレベル `story:` を統合した v8 で導入）。
    """
    findings: list[Finding] = []
    happy_indices = [
        i for i, n in enumerate(model.get("narratives") or [])
        if isinstance(n, dict) and n.get("kind") == "happy"
    ]
    if len(happy_indices) >= 2:
        ids = [
            (model["narratives"][i].get("id") or f"#{i}") for i in happy_indices
        ]
        findings.append(
            Finding(
                kind="narrative_happy_unique",
                path="narratives",
                message=(
                    f"kind:happy が {len(happy_indices)} 件あります "
                    f"（ハッピーパスは 1 本だけ）: {ids}"
                ),
                slice={"happy_ids": ids},
            )
        )
    return findings


def dangling_lang_entry(model: dict) -> list[Finding]:
    """contexts[].lang.{pols,cmds,evts,aggs,qrys} に登録された名前が
    モデル本体（policies/scenarios/aggregates/queries）に存在しない場合に警告する。

    `language_coverage` は逆方向（モデル要素が lang に未登録）を見るが、本チェックは
    「lang に書いたけれど実体が無い」ケースを検出する。typo / リネーム漏れ / lang だけ
    先行追加した実装忘れを早期発見するのが目的。
    """
    declared = {
        "pols": {p.get("name") for p in (model.get("policies") or []) if isinstance(p, dict)},
        "cmds": set(),
        "evts": set(),
        "aggs": {a.get("name") for a in (model.get("aggregates") or []) if isinstance(a, dict)},
        "qrys": {q.get("name") for q in (model.get("queries") or []) if isinstance(q, dict)},
        "actors": set(),
        "vos": set(),  # vos は scenarios/policies/aggregates では参照されないので空のまま（cross-ref しない）
    }
    for s in model.get("scenarios") or []:
        if isinstance(s, dict):
            if s.get("cmd"):
                declared["cmds"].add(s["cmd"])
            if s.get("evt"):
                declared["evts"].add(s["evt"])
            if s.get("actor"):
                declared["actors"].add(s["actor"])
            for q in s.get("qry") or []:
                if q:
                    declared["qrys"].add(q)
            for br in s.get("brs") or []:
                if isinstance(br, dict) and br.get("evt"):
                    declared["evts"].add(br["evt"])
    for p in model.get("policies") or []:
        if isinstance(p, dict):
            if p.get("cmd"):
                declared["cmds"].add(p["cmd"])
            if p.get("evt"):
                declared["evts"].add(p["evt"])
            if p.get("trg"):
                declared["evts"].add(p["trg"])
            if p.get("qry"):
                declared["qrys"].add(p["qry"])
            trgs = p.get("trgs") or {}
            if isinstance(trgs, dict):
                for ev in trgs.get("evts") or []:
                    declared["evts"].add(ev)
    for a in model.get("aggregates") or []:
        if isinstance(a, dict):
            for ev in a.get("events") or []:
                if isinstance(ev, dict) and ev.get("name"):
                    declared["evts"].add(ev["name"])

    findings: list[Finding] = []
    for i, ctx in enumerate(model.get("contexts") or []):
        if not isinstance(ctx, dict):
            continue
        lang = ctx.get("lang") or {}
        if not isinstance(lang, dict):
            continue
        ctx_name = ctx.get("name") or f"#{i}"
        for cat, real_set in declared.items():
            if cat == "vos":
                # VOs は scenarios/policies/aggregates 本体には現れない（attrs.type で参照される程度）。
                # 厳密な cross-ref は attrs.type の自由文字列まで追わないと判定できないので、本チェックでは
                # vos の dangling は対象外（誤検知を避ける）。
                continue
            cat_dict = lang.get(cat) or {}
            if not isinstance(cat_dict, dict):
                continue
            for name in cat_dict.keys():
                if name not in real_set:
                    findings.append(
                        Finding(
                            kind="dangling_lang_entry",
                            path=f"contexts[{i}].lang.{cat}.{name}",
                            message=(
                                f"BC '{ctx_name}' の lang.{cat} に '{name}' が登録されていますが、"
                                f"対応する実体が見つかりません（typo / 未実装 / リネーム漏れの可能性）"
                            ),
                            slice={"ctx": ctx_name, "category": cat, "identifier": name},
                        )
                    )
    return findings


def cross_bc_state_name_collision(model: dict) -> list[Finding]:
    """異なる AGG / BC で同じ state 名（UPPER_SNAKE）が使われている場合、
    lang.states の日本語ラベルが一致しなければ「同名異義」として警告する。

    例: event-planning.Event.CANCELLED と participation.Participation.CANCELLED は
    英語 ID 完全一致だが意味が異なる（前者=イベント中止、後者=参加辞退）。HTML フロー図
    のラベル日本語化で混乱を招くため、lang.states のラベルで差別化されているかを確認する。
    """
    # state -> [(ctx_name, agg_name, label_or_None), ...]
    by_state: dict[str, list[tuple[str, str, str | None]]] = {}
    ctx_lang_states: dict[str, dict] = {}
    for ctx in model.get("contexts") or []:
        if not isinstance(ctx, dict):
            continue
        cname = ctx.get("name") or ""
        lang = ctx.get("lang") or {}
        if isinstance(lang, dict):
            states = lang.get("states") or {}
            if isinstance(states, dict):
                ctx_lang_states[cname] = states

    for agg in model.get("aggregates") or []:
        if not isinstance(agg, dict):
            continue
        ctx = agg.get("ctx") or ""
        agg_name = agg.get("name") or ""
        label_map = ctx_lang_states.get(ctx, {})
        for state in agg.get("states") or []:
            by_state.setdefault(state, []).append((ctx, agg_name, label_map.get(state)))

    findings: list[Finding] = []
    for state, occurrences in by_state.items():
        if len(occurrences) < 2:
            continue
        # 異なる AGG / ctx で同じ state が使われている
        labels = {label for _, _, label in occurrences if label}
        if len(labels) <= 1:
            # ラベル無し or 全て同一ラベル → 同義かもしれないが同名なので警告のみ
            # 但しラベル無しなら lang.states に未登録の警告は language_coverage 系の責務外。
            # ここでは「ラベルで差別化されていない同名 state」のみ警告。
            owners = [f"{c}.{a}" for c, a, _ in occurrences]
            findings.append(
                Finding(
                    kind="cross_bc_state_name_collision",
                    path="aggregates[].states",
                    message=(
                        f"state '{state}' が複数 AGG '{owners}' で使われていますが、"
                        f"lang.states での日本語ラベル差別化が確認できません。"
                        f"BC 間で意味が異なる場合は lang.states のラベルを各 BC で書き分けてください"
                    ),
                    slice={"state": state, "owners": owners, "labels": list(labels)},
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


def agg_purpose_minlength(model: dict) -> list[Finding]:
    """aggregates[].purpose が欠落 or 30 字未満なら警告する。

    `references/checks/agg-purpose-quality.md`（意味チェック）の観点 1「purpose は 30 字以上か」
    を構造チェックに降格したもの。単一責任・業務語彙の質的評価は引き続き LLM の責務。
    """
    MIN_LEN = 30
    findings: list[Finding] = []
    for i, agg in enumerate(model.get("aggregates") or []):
        if not isinstance(agg, dict):
            continue
        name = agg.get("name") or f"#{i}"
        purpose = (agg.get("purpose") or "").strip()
        if not purpose:
            findings.append(
                Finding(
                    kind="agg_purpose_minlength",
                    path=f"aggregates[{i}].purpose",
                    message=f"AGG '{name}' に purpose がありません（単一責任を 30 字以上で言語化してください）",
                    slice={"agg": name, "purpose_len": 0},
                )
            )
        elif len(purpose) < MIN_LEN:
            findings.append(
                Finding(
                    kind="agg_purpose_minlength",
                    path=f"aggregates[{i}].purpose",
                    message=(
                        f"AGG '{name}' の purpose が {len(purpose)} 字で短すぎます"
                        f"（{MIN_LEN} 字以上で「何を保証する集約か」を言語化してください）"
                    ),
                    slice={"agg": name, "purpose": purpose, "purpose_len": len(purpose)},
                )
            )
    return findings


def decision_chosen_adopted(model: dict) -> list[Finding]:
    """decisions[].chosen と options[].adopted: true の整合を検査する。

    - chosen が options[].name に存在しない
    - adopted: true の option が 0 件 / 2 件以上
    - adopted: true の option.name が chosen と不一致
    `references/checks/decision-rationale-clarity.md` の観点 4 を構造チェックに降格したもの。
    """
    findings: list[Finding] = []
    for i, d in enumerate(model.get("decisions") or []):
        if not isinstance(d, dict):
            continue
        did = d.get("id") or f"#{i}"
        options = [o for o in (d.get("options") or []) if isinstance(o, dict)]
        if not options:
            continue  # options 未記入の進行中 decision はスキップ
        chosen = d.get("chosen")
        option_names = [o.get("name") for o in options]
        adopted = [o.get("name") for o in options if o.get("adopted") is True]

        if chosen and chosen not in option_names:
            findings.append(
                Finding(
                    kind="decision_chosen_adopted",
                    path=f"decisions[{i}].chosen",
                    message=f"decision '{did}' の chosen '{chosen}' が options[].name に存在しません",
                    slice={"decision": did, "chosen": chosen, "options": option_names},
                )
            )
        if len(adopted) == 0:
            findings.append(
                Finding(
                    kind="decision_chosen_adopted",
                    path=f"decisions[{i}].options",
                    message=f"decision '{did}' に adopted: true の option がありません（chosen と対で記述する）",
                    slice={"decision": did, "chosen": chosen},
                )
            )
        elif len(adopted) >= 2:
            findings.append(
                Finding(
                    kind="decision_chosen_adopted",
                    path=f"decisions[{i}].options",
                    message=f"decision '{did}' で adopted: true が {len(adopted)} 件あります（採用は 1 件だけ）: {adopted}",
                    slice={"decision": did, "adopted": adopted},
                )
            )
        elif chosen and adopted[0] != chosen:
            findings.append(
                Finding(
                    kind="decision_chosen_adopted",
                    path=f"decisions[{i}]",
                    message=f"decision '{did}' の chosen '{chosen}' と adopted: true の option '{adopted[0]}' が不一致",
                    slice={"decision": did, "chosen": chosen, "adopted": adopted[0]},
                )
            )
    return findings


def decision_affects_presence(model: dict) -> list[Finding]:
    """decisions[].affects が欠落 / 空なら警告する。

    採用判断の影響範囲（AGG / Policy / BC）が無い decision は将来の読者がトレースできない。
    `references/checks/decision-rationale-clarity.md` の観点 3 を構造チェックに降格したもの
    （粒度の適切さ＝Policy 連鎖の漏れ等は引き続き LLM の責務）。
    """
    findings: list[Finding] = []
    for i, d in enumerate(model.get("decisions") or []):
        if not isinstance(d, dict):
            continue
        did = d.get("id") or f"#{i}"
        affects = d.get("affects")
        if not affects:
            findings.append(
                Finding(
                    kind="decision_affects_presence",
                    path=f"decisions[{i}].affects",
                    message=(
                        f"decision '{did}' に affects[] がありません"
                        f"（影響を受ける AGG / Policy / BC を記載してください）"
                    ),
                    slice={"decision": did, "topic": d.get("topic")},
                )
            )
    return findings


def err_name_quality(model: dict) -> list[Finding]:
    """scenarios[].errs[].err がコード風 / 汎用的すぎる名前でないかを検査する。

    PascalCase 形式そのもの（`^[A-Z][A-Za-z0-9]*$`）は JSON Schema が担保するため、
    ここでは schema を通過してしまう「業務エラー名として弱い」パターンだけを拾う:
      - 数字を含む（`Err001` / `Http404` のようなコード風）
      - 1 語のみ（`Invalid` / `Error` のような汎用語。大文字が 1 つ＝単語 1 個とみなす）
    `references/checks/scenario-rules-quality.md` の観点 3 の機械化可能部分。
    """
    findings: list[Finding] = []
    for i, s in enumerate(model.get("scenarios") or []):
        if not isinstance(s, dict):
            continue
        sname = s.get("name") or f"#{i}"
        for j, e in enumerate(s.get("errs") or []):
            if not isinstance(e, dict):
                continue
            err = e.get("err") or ""
            if not err:
                continue  # 必須欠落は schema 検証の責務
            if any(ch.isdigit() for ch in err):
                findings.append(
                    Finding(
                        kind="err_name_quality",
                        path=f"scenarios[{i}].errs[{j}].err",
                        message=(
                            f"scenario '{sname}' のエラー名 '{err}' が数字を含みコード風です"
                            f"（業務語彙のエラー名に書き換えを検討: 例 Err001 → QuoteAlreadyConsumed）"
                        ),
                        slice={"scenario": sname, "err": err},
                    )
                )
            elif sum(1 for ch in err if ch.isupper()) < 2:
                findings.append(
                    Finding(
                        kind="err_name_quality",
                        path=f"scenarios[{i}].errs[{j}].err",
                        message=(
                            f"scenario '{sname}' のエラー名 '{err}' が 1 語だけで汎用的すぎます"
                            f"（何が・どう違反したかを含む複合語にしてください: 例 Invalid → ApplyDeadlineInvalid）"
                        ),
                        slice={"scenario": sname, "err": err},
                    )
                )
    return findings


def bc_vocabulary_collision(model: dict) -> list[Finding]:
    """contexts[].lang 辞書の EN↔JP 完全一致衝突を検出する。

    - 同名異義: 同カテゴリの同じ英語識別子が複数 BC で **異なる日本語ラベル** を持つ
    - 異名同義: 同カテゴリの同じ日本語ラベルが **異なる英語識別子** に対応している（BC 内 / BC 間とも）
    `references/checks/bc-vocabulary-consistency.md` の観点 1・2 のうち完全一致で判定できる部分の降格。
    表記ゆれ（近縁語）や意図的な Conformist / ACL の判断は引き続き LLM の責務。
    states は `cross_bc_state_name_collision`（同名 state はラベルで差別化すべし）と方向が
    逆になるため対象外。
    """
    CATEGORIES = ("aggs", "actors", "cmds", "evts", "pols", "qrys", "vos")
    # (cat, en) -> [(ctx, label)], (cat, label) -> [(ctx, en)]
    by_en: dict[tuple[str, str], list[tuple[str, str]]] = {}
    by_label: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for ctx in model.get("contexts") or []:
        if not isinstance(ctx, dict):
            continue
        cname = ctx.get("name") or ""
        lang = ctx.get("lang") or {}
        if not isinstance(lang, dict):
            continue
        for cat in CATEGORIES:
            cat_dict = lang.get(cat) or {}
            if not isinstance(cat_dict, dict):
                continue
            for en, label in cat_dict.items():
                if not en or not isinstance(label, str) or not label:
                    continue
                by_en.setdefault((cat, en), []).append((cname, label))
                by_label.setdefault((cat, label), []).append((cname, en))

    findings: list[Finding] = []
    for (cat, en), occurrences in by_en.items():
        labels = {label for _, label in occurrences}
        if len(labels) >= 2:
            owners = [f"{c}({label})" for c, label in occurrences]
            findings.append(
                Finding(
                    kind="bc_vocabulary_collision",
                    path=f"contexts[].lang.{cat}.{en}",
                    message=(
                        f"同名異義: '{en}' が複数 BC で異なる日本語ラベルを持ちます: {owners}。"
                        f"別概念なら識別子を分けるか、意図的な流用なら note で Conformist / ACL を明示してください"
                    ),
                    slice={"category": cat, "identifier": en, "occurrences": owners},
                )
            )
    for (cat, label), occurrences in by_label.items():
        ens = {en for _, en in occurrences}
        if len(ens) >= 2:
            owners = [f"{c}.{en}" for c, en in occurrences]
            findings.append(
                Finding(
                    kind="bc_vocabulary_collision",
                    path=f"contexts[].lang.{cat}",
                    message=(
                        f"異名同義: 日本語ラベル '{label}' が異なる英語識別子 {sorted(ens)} に対応しています: {owners}。"
                        f"同一概念なら識別子を統一してください"
                    ),
                    slice={"category": cat, "label": label, "identifiers": sorted(ens), "occurrences": owners},
                )
            )
    return findings


def crud_cmd_naming(model: dict) -> list[Finding]:
    """CMD 名が CRUD 風接頭辞（Create/Add/Update/Delete/Get/Set 等）で始まっていないかを検査する。

    CMD は業務行為（Publish / Apply / Conclude ...）で命名するのが Ubiquitous Language の作法。
    `references/checks/bc-vocabulary-consistency.md` の観点 3 のヒューリスティック降格。
    接頭辞の直後が大文字の場合のみフラグ（`Address...` のような偶然の前方一致は除外）。
    """
    CRUD_PREFIXES = (
        "Create", "Add", "Update", "Delete", "Remove",
        "Get", "Set", "Fetch", "Edit", "Modify", "Insert",
    )

    def _is_crud(name: str) -> str | None:
        for p in CRUD_PREFIXES:
            rest = name[len(p):]
            if name.startswith(p) and rest and rest[0].isupper():
                return p
        return None

    # cmd 名の出現箇所を収集（scenarios / policies / lang.cmds）
    seen: dict[str, str] = {}  # cmd -> 最初に見つけた path
    for i, s in enumerate(model.get("scenarios") or []):
        if isinstance(s, dict) and s.get("cmd"):
            seen.setdefault(s["cmd"], f"scenarios[{i}].cmd")
    for i, p in enumerate(model.get("policies") or []):
        if isinstance(p, dict) and p.get("cmd"):
            seen.setdefault(p["cmd"], f"policies[{i}].cmd")
    for i, ctx in enumerate(model.get("contexts") or []):
        if not isinstance(ctx, dict):
            continue
        lang = ctx.get("lang") or {}
        cmds = lang.get("cmds") if isinstance(lang, dict) else None
        if isinstance(cmds, dict):
            for cmd in cmds.keys():
                seen.setdefault(cmd, f"contexts[{i}].lang.cmds.{cmd}")

    findings: list[Finding] = []
    for cmd, path in seen.items():
        prefix = _is_crud(cmd)
        if prefix:
            findings.append(
                Finding(
                    kind="crud_cmd_naming",
                    path=path,
                    message=(
                        f"CMD '{cmd}' が CRUD 風接頭辞 '{prefix}' で始まっています"
                        f"（業務行為の動詞への言い換えを検討: 例 UpdateEvent → RescheduleEvent / PublishEvent）"
                    ),
                    slice={"cmd": cmd, "prefix": prefix},
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
    "flow_chain_resolution": flow_chain_resolution,
    "narrative_entry_consistency": narrative_entry_consistency,
    "narrative_happy_unique": narrative_happy_unique,
    "dangling_lang_entry": dangling_lang_entry,
    "cross_bc_state_name_collision": cross_bc_state_name_collision,
    "question_decision_link": question_decision_link,
    "agg_purpose_minlength": agg_purpose_minlength,
    "decision_chosen_adopted": decision_chosen_adopted,
    "decision_affects_presence": decision_affects_presence,
    "err_name_quality": err_name_quality,
    "bc_vocabulary_collision": bc_vocabulary_collision,
    "crud_cmd_naming": crud_cmd_naming,
}
