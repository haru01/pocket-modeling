#!/usr/bin/env python3
"""HTML 生成のエスケープ／置換に関するセキュリティ回帰テスト。

依存ゼロ（stdlib unittest）。fixture はインライン dict。
実行: python3 scripts/tests/test_html_escaping.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventstorming_build import DMLDocument, esc, render_html  # noqa: E402


class TestEsc(unittest.TestCase):
    def test_escapes_angle_brackets_and_amp(self):
        self.assertEqual(esc("<script>&"), "&lt;script&gt;&amp;")

    def test_escapes_quotes(self):
        """属性値へ埋め込まれても抜け出せないよう引用符もエスケープする。"""
        out = esc('" onmouseover=alert(1) x="')
        self.assertNotIn('"', out)
        out = esc("' onmouseover=alert(1) x='")
        self.assertNotIn("'", out)


class TestRenderHtmlReplacement(unittest.TestCase):
    """DML 由来のバックスラッシュが re.sub の後方参照として解釈されないこと。"""

    def _doc(self, **session):
        return DMLDocument(
            session={"id": "s", "domain": "D", "phase": "1", **session},
            model={},
        )

    def test_backslash_in_domain(self):
        html = render_html(self._doc(domain=r"Payments \1 domain"))
        self.assertIn(r"Payments \1 domain", html)

    def test_group_reference_in_goal(self):
        html = render_html(self._doc(goal=r"match \g<0> pattern"))
        self.assertIn(r"match \g&lt;0&gt; pattern", html)


if __name__ == "__main__":
    unittest.main()
