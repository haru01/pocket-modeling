#!/usr/bin/env python3
"""hint（resolve_hint）の条件付き必須・排他表示の単体テスト。

依存ゼロ（stdlib unittest + pyyaml）。schema を実ファイルから読んで resolve_hint を直接呼ぶ。
実行: python3 scripts/tests/test_hints.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from dml_filters.hints import resolve_hint  # noqa: E402

SCHEMA = yaml.safe_load(
    (SCRIPT_DIR.parent / "references" / "dml.schema.yaml").read_text(encoding="utf-8")
)


def items_hint(path: str) -> dict:
    """array パスの items（要素）の hint dict を返す。"""
    r = resolve_hint(SCHEMA, path)
    return r["hint"]["items"]


class HintConditionalTest(unittest.TestCase):
    def test_policy_conditional_bulk_qry(self):
        h = items_hint("policies")
        self.assertIn("conditional", h)
        joined = " / ".join(h["conditional"])
        self.assertIn("bulk: true", joined)
        self.assertIn("qry", joined)

    def test_policy_exclusive_trg_trgs(self):
        h = items_hint("policies")
        self.assertIn("exclusive", h)
        self.assertTrue(any("trg" in e and "trgs" in e for e in h["exclusive"]))

    def test_scenario_conditional_brmode_brs(self):
        h = items_hint("scenarios")
        self.assertIn("conditional", h)
        joined = " / ".join(h["conditional"])
        self.assertIn("brMode", joined)
        self.assertIn("brs", joined)

    def test_scenario_exclusive_evt_brs(self):
        h = items_hint("scenarios")
        self.assertIn("exclusive", h)
        self.assertTrue(any("evt" in e and "brs" in e for e in h["exclusive"]))

    def test_branch_exclusive_next_terminal(self):
        # branch は node 直下の not（allOf でない）。scenarios[].brs 経由で解決。
        h = items_hint("scenarios.brs")
        self.assertIn("exclusive", h)
        self.assertTrue(any("next" in e and "terminal" in e for e in h["exclusive"]))

    def test_scalar_path_has_no_conditional(self):
        r = resolve_hint(SCHEMA, "session.goal")
        self.assertNotIn("conditional", r["hint"])
        self.assertNotIn("exclusive", r["hint"])

    def test_required_still_present(self):
        # 既存の required 表示が壊れていない回帰確認
        h = items_hint("policies")
        self.assertEqual(sorted(h.get("required", [])), ["ctx", "name"])

    def test_nested_object_expands_one_level(self):
        # ⑭ hint --path=domains の subs が array<object{...}> まで1階層展開される
        h = items_hint("domains")
        self.assertIn("subs", h["properties"])
        subs = h["properties"]["subs"]
        self.assertTrue(subs.startswith("array<object{"), subs)
        self.assertIn("name", subs)
        self.assertIn("type", subs)

    def test_nested_expansion_stops_at_one_level(self):
        # 無限展開しない: 展開された内側にネストした波括弧が二重に出ない
        h = items_hint("domains")
        subs = h["properties"]["subs"]
        self.assertEqual(subs.count("{"), 1, subs)


if __name__ == "__main__":
    unittest.main()
