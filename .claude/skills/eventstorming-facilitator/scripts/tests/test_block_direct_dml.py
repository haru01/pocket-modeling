#!/usr/bin/env python3
"""DML 直接 I/O ブロックフックの回帰テスト（ガードレールの素通り防止）。

依存ゼロ（stdlib unittest）。フックを子プロセスとして起動し exit code を見る。
実行: python3 scripts/tests/test_block_direct_dml.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "block_direct_dml.py"


def run(tool: str, path: str, key: str = "file_path") -> int:
    payload = {"tool_name": tool, "tool_input": {key: path}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    ).returncode


class TestBlock(unittest.TestCase):
    def test_blocks_plain_relative_path(self):
        self.assertEqual(run("Read", "docs/eventstorming/a.dml.yaml"), 2)

    def test_blocks_absolute_path(self):
        self.assertEqual(run("Write", "/repo/docs/eventstorming/a.dml.yaml"), 2)

    def test_blocks_non_normalized_paths(self):
        for p in (
            "./docs/eventstorming/a.dml.yaml",
            "docs/eventstorming/./a.dml.yaml",
            "docs/x/../eventstorming/a.dml.yaml",
        ):
            with self.subTest(path=p):
                self.assertEqual(run("Edit", p), 2)

    def test_blocks_edit_variants(self):
        for tool in ("MultiEdit", "NotebookEdit", "NotebookRead"):
            with self.subTest(tool=tool):
                self.assertEqual(run(tool, "docs/eventstorming/a.dml.yaml"), 2)

    def test_allows_other_paths_and_tools(self):
        self.assertEqual(run("Read", "docs/dimensional/a.dimml.yaml"), 0)
        self.assertEqual(run("Read", "README.md"), 0)
        self.assertEqual(run("Bash", "docs/eventstorming/a.dml.yaml"), 0)


if __name__ == "__main__":
    unittest.main()
