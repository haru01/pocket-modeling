#!/usr/bin/env python3
"""PreToolUse hook — `docs/eventstorming/*.dml.yaml` への直接 Read/Edit/Write をブロックする。

Claude Code の PreToolUse hook として `.claude/settings.json` に登録される。
stdin に流れてくる JSON ペイロードから `tool_name` と `tool_input.file_path` を読み、
パスが DML セッションファイル（`docs/eventstorming/<name>.dml.yaml`）に該当し
ツールが Read/Edit/Write のいずれかなら、exit 2 + stderr でブロックする。

AI への案内: dmlctl 経由（view/init/set/add/remove/update）を使うよう促す。
Bash 経由の dmlctl 呼び出しは本フックを通らないので、`dmlctl set ...` などは通る。

dmlctl 自身は本ファイルを編集しないので、本フックの影響を受けない。
"""

from __future__ import annotations

import json
import re
import sys

# パターンは絶対パス／相対パス両方を許容（リポジトリルートからの相対が一般的）
DML_PATH_RE = re.compile(r"(^|/)docs/eventstorming/[^/]+\.dml\.yaml$")
BLOCKED_TOOLS = {"Read", "Edit", "Write"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"[block_direct_dml] payload を JSON として解析できません: {e}", file=sys.stderr)
        return 0  # フック内エラーで誤ブロックしない

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or ""

    if tool_name not in BLOCKED_TOOLS:
        return 0
    if not DML_PATH_RE.search(target):
        return 0

    print(
        f"[block_direct_dml] {tool_name} on {target} is forbidden.\n"
        f"DML ファイルへの直接 I/O は禁止されています。dmlctl 経由で操作してください：\n"
        f"\n"
        f"  読む（観点別）:\n"
        f"    python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py view {target} --view=<name>\n"
        f"    （view 名一覧: dmlctl views）\n"
        f"\n"
        f"  読む（全文・サイズ警告付き）:\n"
        f"    python3 .claude/skills/eventstorming-facilitator/scripts/dmlctl.py view {target} --view=full\n"
        f"\n"
        f"  書く（既存ファイル）:\n"
        f"    dmlctl set    {target} --path=<a.b.c> (--value=<lit> | --value-file=<path>)\n"
        f"    dmlctl add    {target} --to=<list-path> (--item=<lit> | --item-file=<path>)\n"
        f"    dmlctl update {target} --path=<list-path> --where=<key=value> (--set-key=... --value=... | --merge-yaml=...)\n"
        f"    dmlctl remove {target} --path=<a.b.c> [--where=<key=value>]\n"
        f"\n"
        f"  新規ファイル作成:\n"
        f"    dmlctl init <new-path> --session-id=... --domain=... [--goal=...]\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
