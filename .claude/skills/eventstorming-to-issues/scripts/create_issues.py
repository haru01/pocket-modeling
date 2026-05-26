#!/usr/bin/env python3
"""GitHub Issue 冪等起票

使い方:
    python3 create_issues.py <session-dir> [--dry-run] [--repo owner/repo]

処理順序:
    1. ラベル冪等作成
    2. AGG Epic (epics/*.md) を起票 or 更新（1 AGG = 1 Issue）
    3. AGG 跨ぎ統合 SCENARIO (integration/*.md) を起票
    4. Cross-BC Saga (cross-bc/*.md) を起票
    5. _state.json 更新

設計: 1 AGG Epic = 1 PR = AI エージェント 1 担当。CMD/QRY/受信 POLICY の
詳細は Epic 本文に inline されているため Sub-issue は廃止。
AGG 跨ぎは統合 Issue として別建て。

冪等性:
    - 各 MD 本文先頭の <!-- es-key: ... --> で既存 Issue を検索
    - ヒットすれば gh issue edit --body-file で更新 (タイトル・ラベルは変更しない)
    - ヒットしなければ gh issue create
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ES_KEY_RE = re.compile(r"<!-- es-key: ([^ ]+) -->")
TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)


# ============================================================
# 補助
# ============================================================


def run(cmd: list[str], dry_run: bool = False, capture: bool = True, check: bool = True) -> str:
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}")
        return ""
    result = subprocess.run(cmd, capture_output=capture, text=True, check=False)
    if check and result.returncode != 0:
        sys.stderr.write(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
        raise SystemExit(result.returncode)
    return result.stdout.strip()


def extract_eskey(body: str) -> str | None:
    m = ES_KEY_RE.search(body)
    return m.group(1) if m else None


def extract_title(body: str) -> str | None:
    m = TITLE_RE.search(body)
    return m.group(1).strip() if m else None


def strip_title_line(body: str) -> str:
    """gh issue create では --title 引数とは別に本文先頭の # を残す必要なし"""
    return TITLE_RE.sub("", body, count=1).lstrip()


# ============================================================
# Label
# ============================================================


def load_labels(session_dir: Path) -> list[dict]:
    """_labels.md から Name/Color を再パース"""
    md = (session_dir / "_labels.md").read_text(encoding="utf-8")
    labels = []
    for line in md.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*`#([0-9A-Fa-f]{6})`\s*\|\s*(.+?)\s*\|", line)
        if m:
            labels.append({"name": m.group(1), "color": m.group(2), "description": m.group(3)})
    return labels


def ensure_labels(labels: list[dict], repo_args: list[str], dry_run: bool):
    print("== Ensure labels ==")
    out = run(["gh"] + repo_args + ["label", "list", "--json", "name", "--limit", "300"],
              dry_run=False)  # 既存取得は dry-run でも行う
    existing = {item["name"] for item in json.loads(out or "[]")}
    for lab in labels:
        if lab["name"] in existing:
            print(f"  skip (exists): {lab['name']}")
            continue
        cmd = ["gh"] + repo_args + [
            "label", "create", lab["name"],
            "--color", lab["color"],
            "--description", lab["description"],
        ]
        run(cmd, dry_run=dry_run)
        print(f"  created: {lab['name']}")


# ============================================================
# Issue upsert
# ============================================================


def find_issue_by_eskey(eskey: str, repo_args: list[str]) -> int | None:
    """es-key で既存 Issue を検索"""
    out = run(
        ["gh"] + repo_args + ["issue", "list",
        "--search", f"es-key:{eskey} in:body",
        "--state", "all",
        "--json", "number,body",
        "--limit", "20"],
        dry_run=False,
    )
    items = json.loads(out or "[]")
    # body に es-key 完全一致を含むものを優先 (検索はファジー)
    for item in items:
        if f"es-key: {eskey} " in item.get("body", "") or f"es-key: {eskey} -->" in item.get("body", ""):
            return item["number"]
    return None


def upsert_issue(
    body_file: Path,
    labels: list[str],
    state: dict,
    repo_args: list[str],
    dry_run: bool,
) -> tuple[int | None, str]:
    """body_file の Issue を冪等起票。(issue_number, eskey) を返す"""
    body = body_file.read_text(encoding="utf-8")
    eskey = extract_eskey(body)
    title = extract_title(body)
    if not eskey or not title:
        print(f"  WARN: skip {body_file} (es-key or title missing)")
        return None, ""

    # 状態キャッシュ確認
    cached = state.get(eskey)
    existing = cached or find_issue_by_eskey(eskey, repo_args) if not dry_run else None

    if existing:
        cmd = ["gh"] + repo_args + ["issue", "edit", str(existing),
               "--body-file", str(body_file)]
        run(cmd, dry_run=dry_run)
        print(f"  updated #{existing}: {title[:60]}")
        return existing, eskey
    else:
        label_args: list[str] = []
        for l in labels:
            label_args += ["--label", l]
        cmd = (["gh"] + repo_args + ["issue", "create",
               "--title", title, "--body-file", str(body_file)]
               + label_args)
        if dry_run:
            print(f"[dry-run] {' '.join(cmd)}")
            return None, eskey
        url = run(cmd, dry_run=False)
        # URL の末尾が Issue 番号
        m = re.search(r"/issues/(\d+)$", url)
        number = int(m.group(1)) if m else None
        print(f"  created #{number}: {title[:60]}")
        return number, eskey


# ============================================================
# main
# ============================================================


def labels_for_path(rel_path: str, labels_md: list[dict]) -> list[str]:
    """ファイル名から必要な Label セットを推定（AGG Epic / 統合 / Saga のみ）"""
    parts = rel_path.replace("\\", "/").split("/")
    kind = parts[0] if parts else ""
    name = parts[-1]

    result: list[str] = []
    if kind == "epics" and "__" in name:
        bc, rest = name.split("__", 1)
        agg_part = rest.rsplit(".", 1)[0]
        result.append(f"bc:{bc}")
        result.append(f"agg:{agg_part}")
        result.append("type:aggregate")
    elif kind == "integration":
        result.append("type:scenario")
        result.append("cross-bc")
    elif kind == "cross-bc":
        result.append("type:saga")
        result.append("cross-bc")

    # 重複排除しつつ順序保持
    seen: set[str] = set()
    return [l for l in result if not (l in seen or seen.add(l))]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("session_dir", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--repo", type=str, default=None, help="owner/repo (gh -R)")
    args = p.parse_args()

    sdir = args.session_dir
    if not sdir.is_dir():
        sys.exit(f"Not a directory: {sdir}")

    state_path = sdir / "_state.json"
    state: dict[str, int | None] = (
        json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    )

    repo_args = ["-R", args.repo] if args.repo else []

    # 1. Labels
    labels_md = load_labels(sdir)
    ensure_labels(labels_md, repo_args, args.dry_run)

    # 2. AGG Epics
    print("\n== AGG Epics ==")
    epic_paths = sorted((sdir / "epics").glob("*.md"))
    for ep in epic_paths:
        rel = str(ep.relative_to(sdir))
        labels = labels_for_path(rel, labels_md)
        num, eskey = upsert_issue(ep, labels, state, repo_args, args.dry_run)
        if num is not None:
            state[eskey] = num
            time.sleep(1.5)

    # 3. AGG 跨ぎ統合 SCENARIO
    print("\n== Integration (AGG 跨ぎ統合 SCENARIO) ==")
    int_paths = sorted((sdir / "integration").glob("*.md"))
    for ip in int_paths:
        rel = str(ip.relative_to(sdir))
        labels = labels_for_path(rel, labels_md)
        num, eskey = upsert_issue(ip, labels, state, repo_args, args.dry_run)
        if num is not None:
            state[eskey] = num
            time.sleep(1.5)

    # 4. Cross-BC Saga
    print("\n== Cross-BC Saga ==")
    saga_paths = sorted((sdir / "cross-bc").glob("*.md"))
    for sp in saga_paths:
        rel = str(sp.relative_to(sdir))
        labels = labels_for_path(rel, labels_md)
        num, eskey = upsert_issue(sp, labels, state, repo_args, args.dry_run)
        if num is not None:
            state[eskey] = num
            time.sleep(1.5)

    # 5. Save state
    if not args.dry_run:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nState saved: {state_path}")
    else:
        print("\n(dry-run: _state.json not written)")


if __name__ == "__main__":
    main()
