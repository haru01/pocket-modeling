#!/usr/bin/env python3
"""flow-causality view（brs 分岐対応版）の単体テスト。

依存ゼロ（stdlib unittest）。fixture はインライン dict で flow_causality() を直接呼ぶため、
DML ファイルの読み取りフックとも無縁。実行: python3 scripts/tests/test_flow_causality.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dml_filters.views import flow_causality  # noqa: E402


def narrative(id_, entry, kind="alt"):
    return {"id": id_, "kind": kind, "title": id_, "entry": entry, "prose": "x"}


def sc(name, **kw):
    return {"name": name, "ctx": kw.pop("ctx", "bc-a"), "actor": kw.pop("actor", "Actor"), **kw}


def flow_of(result, flow_id):
    return next(f for f in result["flows"] if f["id"] == flow_id)


def walk_all_steps(flow):
    yield from flow["steps"]
    for st in flow.get("sidetracks") or []:
        yield from st["steps"]


class FlowCausalityBranchTest(unittest.TestCase):
    def test_01_taken_branch_next_and_branches_field(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2", "next": "S3"},
                ]),
                sc("S2", cmd="C2", evt="E9"),
                sc("S3", cmd="C3", evt="E8"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        s1 = flow["steps"][0]
        self.assertEqual([b.get("taken") for b in s1["branches"]], [True, None])
        self.assertEqual(s1["evt"], "E1")
        self.assertEqual([s["step"] for s in flow["steps"]], ["S1", "S2"])
        self.assertEqual(flow["sidetracks"][0]["from"], "S1")
        self.assertEqual(flow["sidetracks"][0]["evt"], "E2")
        self.assertEqual([s["step"] for s in flow["sidetracks"][0]["steps"]], ["S3"])

    def test_02_taken_terminal_and_no_false_synthesis(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", evt="E0", next="S2"),
                sc("S2", cmd="C2", brs=[
                    {"cond": "ok", "evt": "E1", "next": "S3"},
                    {"cond": "ng", "evt": "E2", "terminal": "f1"},
                ]),
                sc("S3", cmd="C3", evt="E3"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        s2 = flow["steps"][1]
        self.assertEqual(s2["terminal"], "f1")
        self.assertTrue(s2["branches"][1]["taken"])
        for step in walk_all_steps(flow):
            self.assertNotEqual(step.get("terminal"), False, f"terminal: false 合成が残存: {step}")

    def test_03_non_taken_branch_spawns_sidetrack_chain(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2", "next": "S3"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
                sc("S3", cmd="C3", evt="E4", next="S4"),
                sc("S4", cmd="C4", evt="E5"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        st = flow["sidetracks"][0]
        self.assertEqual(st["cond"], "b")
        self.assertEqual([s["step"] for s in st["steps"]], ["S3", "S4"])

    def test_04_policy_only_sidetrack(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "timeout", "evt": "E2"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
            ],
            "policies": [{"name": "P1", "ctx": "bc-a", "trg": "E2", "cmd": "CmdX"}],
        }
        flow = flow_of(flow_causality(model), "f1")
        st = flow["sidetracks"][0]
        self.assertEqual([s["kind"] for s in st["steps"]], ["policy"])
        self.assertEqual(st["steps"][0]["step"], "P1")

    def test_05_dead_branch_no_sidetrack(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertNotIn("sidetracks", flow)
        self.assertEqual(len(flow["steps"][0]["branches"]), 2)

    def test_06_sidetrack_merging_into_main_becomes_ref(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2", "next": "S2"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        st = flow["sidetracks"][0]
        self.assertEqual(st["steps"], [{"step": "S2", "kind": "scenario-ref"}])

    def test_07_two_sidetracks_merging_each_other(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2", "next": "S9"},
                    {"cond": "c", "evt": "E3", "next": "S9"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
                sc("S9", cmd="C9", evt="E9"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        st1, st2 = flow["sidetracks"]
        self.assertEqual(st1["steps"][0]["kind"], "scenario")
        self.assertEqual(st2["steps"], [{"step": "S9", "kind": "scenario-ref"}])

    def test_08_branch_inside_sidetrack_appends_flat(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2", "next": "S3"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
                sc("S3", cmd="C3", brs=[
                    {"cond": "c", "evt": "E4", "next": "S4"},
                    {"cond": "d", "evt": "E5", "next": "S5"},
                ]),
                sc("S4", cmd="C4", evt="E6"),
                sc("S5", cmd="C5", evt="E7"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        froms = [st["from"] for st in flow["sidetracks"]]
        self.assertEqual(froms, ["S1", "S3"])
        self.assertEqual([s["step"] for s in flow["sidetracks"][1]["steps"]], ["S5"])

    def test_09_loop_stops_with_ref(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", evt="E1", next="S2"),
                sc("S2", cmd="C2", evt="E2", next="S1"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertEqual(
            [(s["step"], s["kind"]) for s in flow["steps"]],
            [("S1", "scenario"), ("S2", "scenario"), ("S1", "scenario-ref")],
        )

    def test_10_next_dict_without_flow_key_emits_verbatim_and_stops(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", evt="E1", next={"other-flow": "S2"}),
                sc("S2", cmd="C2", evt="E2"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertEqual(len(flow["steps"]), 1)
        self.assertEqual(flow["steps"][0]["next"], {"other-flow": "S2"})

    def test_11_unresolved_next(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [sc("S1", cmd="C1", evt="E1", next="Missing")],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertEqual(flow["steps"][1], {"step": "Missing", "kind": "unresolved"})

    def test_12_simple_chain_backward_compat(self):
        model = {
            "narratives": [narrative("f1", "S1", kind="happy")],
            "scenarios": [
                sc("S1", cmd="C1", evt="E1", next="S2"),
                sc("S2", cmd="C2", evt="E2"),
            ],
            "policies": [{"name": "P1", "ctx": "bc-a", "trg": "E1", "cmd": "CmdX"}],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertEqual([s["step"] for s in flow["steps"]], ["S1", "P1", "S2"])
        for step in flow["steps"]:
            self.assertNotIn("terminal", step)
            self.assertNotIn("branches", step)
        self.assertNotIn("sidetracks", flow)

    def test_13_all_branches_terminal_for_other_flow(self):
        model = {
            "narratives": [narrative("f1", "S1"), narrative("f2", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", next="S2", brs=[{"cond": "a", "evt": "E1", "terminal": "f2"}]),
                sc("S2", cmd="C2", evt="E2"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        s1 = flow["steps"][0]
        self.assertNotIn("terminal", s1)  # 他フローの terminal は f1 の終端ではない
        self.assertEqual([s["step"] for s in flow["steps"]], ["S1", "S2"])

    def test_14_brmode_passthrough_only_when_present(self):
        model = {
            "narratives": [narrative("f1", "S1")],
            "scenarios": [
                sc("S1", cmd="C1", brMode="concurrent", brs=[
                    {"cond": "a", "evt": "E1", "next": "S2"},
                    {"cond": "b", "evt": "E2"},
                ]),
                sc("S2", cmd="C2", evt="EE"),
            ],
        }
        flow = flow_of(flow_causality(model), "f1")
        self.assertEqual(flow["steps"][0]["brMode"], "concurrent")

    def test_15_id_filter(self):
        model = {
            "narratives": [narrative("f1", "S1"), narrative("f2", "S1")],
            "scenarios": [sc("S1", cmd="C1", evt="E1")],
        }
        result = flow_causality(model, id="f2")
        self.assertEqual([f["id"] for f in result["flows"]], ["f2"])


if __name__ == "__main__":
    unittest.main()
