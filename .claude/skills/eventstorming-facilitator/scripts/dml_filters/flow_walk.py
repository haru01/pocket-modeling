"""フロー走査の共有規約（views.py と eventstorming_build.py の単一真実源）。

`narratives[].entry` → `scenarios[].next` / `brs[]` のフロー連鎖を辿るとき、
「どの分岐がメインパスか」「どの EVT がどの POLICY を起動するか」の解釈は
view スライス（flow-causality）と HTML レーン描画で完全に一致していなければならない。
この 2 関数がその規約の唯一の実装。
"""

from __future__ import annotations


def pick_active_branch(sc: dict, flow_id: str) -> dict | None:
    """指定フロー上で「いまアクティブな」brs[] エントリを 1 つ選ぶ。

    優先順位:
      1. `terminal == flow_id` の brs（このフローはここで終わる宣言）
      2. `terminal` を持たない brs（happy 系・デフォルト分岐）
      3. fallback: 最初の brs
    brs が無ければ None を返す。
    """
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


def index_policies_by_trg(model: dict) -> dict[str, list[dict]]:
    """evt 名 → その evt をトリガー（trg / trgs.evts）とする policy のリスト。"""
    idx: dict[str, list[dict]] = {}
    for p in model.get("policies") or []:
        if not isinstance(p, dict):
            continue
        trg = p.get("trg")
        if trg:
            idx.setdefault(trg, []).append(p)
        trgs = p.get("trgs") or {}
        if isinstance(trgs, dict):
            for ev in trgs.get("evts") or []:
                idx.setdefault(ev, []).append(p)
    return idx
