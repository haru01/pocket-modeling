#!/usr/bin/env python3
"""暫定フロー（entry/next 未設定時のフォールバック描画）の単体テスト。

依存ゼロ（stdlib unittest）。fixture はインライン dict。
実行: python3 scripts/tests/test_provisional_flow.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventstorming_build import (  # noqa: E402
    build_provisional_flow,
    render_flows,
    select_flows,
)


def sc(name, ctx, **kw):
    return {"name": name, "ctx": ctx, "actor": "Customer", **kw}


def labels(lane):
    return [n.label for n in lane.notes]


class BuildProvisionalFlowTest(unittest.TestCase):
    def test_01_builds_flow_in_dml_order_when_no_entry(self):
        model = {
            "narratives": [{"id": "happy", "kind": "happy", "prose": "x"}],
            "scenarios": [
                sc("S1", "ordering", cmd="C1", evt="E1"),
                sc("S2", "payment", cmd="C2", evt="E2"),
            ],
        }
        flow = build_provisional_flow(model, {})
        self.assertIsNotNone(flow)
        self.assertEqual([lane.bc_name for lane in flow.lanes], ["ordering", "payment"])
        self.assertIn("C1", labels(flow.lanes[0]))
        self.assertIn("E2", labels(flow.lanes[1]))

    def test_02_merges_consecutive_same_ctx_into_one_lane(self):
        model = {
            "scenarios": [
                sc("S1", "ordering", cmd="C1", evt="E1"),
                sc("S2", "ordering", cmd="C2", evt="E2"),
                sc("S3", "payment", cmd="C3", evt="E3"),
            ],
        }
        flow = build_provisional_flow(model, {})
        self.assertEqual([lane.bc_name for lane in flow.lanes], ["ordering", "payment"])
        self.assertIn("C1", labels(flow.lanes[0]))
        self.assertIn("C2", labels(flow.lanes[0]))

    def test_03_lists_every_branch_event_without_following_them(self):
        model = {
            "scenarios": [
                sc(
                    "S1",
                    "trade-in",
                    cmd="C1",
                    brs=[
                        {"cond": "a", "evt": "E1"},
                        {"cond": "b", "evt": "E2", "terminal": "alt"},
                    ],
                ),
            ],
        }
        flow = build_provisional_flow(model, {})
        self.assertEqual(len(flow.lanes), 1)
        self.assertIn("E1", labels(flow.lanes[0]))
        self.assertIn("E2", labels(flow.lanes[0]))

    def test_04_localizes_labels_via_glossary(self):
        model = {"scenarios": [sc("S1", "ordering", cmd="PlaceOrder", evt="OrderPlaced")]}
        flow = build_provisional_flow(model, {"PlaceOrder": "注文を確定する"})
        self.assertIn("注文を確定する", labels(flow.lanes[0]))

    def test_05_returns_none_when_no_scenario_yields_notes(self):
        self.assertIsNone(build_provisional_flow({"scenarios": []}, {}))
        self.assertIsNone(build_provisional_flow({}, {}))


class SelectFlowsTest(unittest.TestCase):
    def test_06_prefers_declared_flow_and_is_not_provisional(self):
        model = {
            "narratives": [
                {"id": "happy", "kind": "happy", "title": "H", "entry": "S1", "prose": "x"}
            ],
            "scenarios": [sc("S1", "ordering", cmd="C1", evt="E1")],
        }
        flows, provisional = select_flows(model, {})
        self.assertFalse(provisional)
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0].title, "H")

    def test_07_falls_back_to_provisional_when_no_entry(self):
        model = {
            "narratives": [{"id": "happy", "kind": "happy", "prose": "x"}],
            "scenarios": [sc("S1", "ordering", cmd="C1", evt="E1")],
        }
        flows, provisional = select_flows(model, {})
        self.assertTrue(provisional)
        self.assertEqual(len(flows), 1)

    def test_08_returns_empty_when_nothing_to_draw(self):
        flows, provisional = select_flows({"scenarios": []}, {})
        self.assertEqual(flows, [])
        self.assertFalse(provisional)


class RenderFlowsTest(unittest.TestCase):
    def test_09_provisional_badge_rendered_only_when_provisional(self):
        model = {"scenarios": [sc("S1", "ordering", cmd="C1", evt="E1")]}
        flow = build_provisional_flow(model, {})
        html = render_flows([flow], provisional=True)
        self.assertIn("provisional-flow-badge", html)
        self.assertIn("暫定", html)
        self.assertNotIn("provisional-flow-badge", render_flows([flow]))

    def test_10_placeholder_points_at_phase_3(self):
        html = render_flows([])
        self.assertIn("todo-placeholder", html)
        self.assertIn("フェーズ3", html)


if __name__ == "__main__":
    unittest.main()
