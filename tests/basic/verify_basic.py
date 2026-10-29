#!/usr/bin/env python3
"""verify_basic.py — CHAT-001 基本能力双轨验收入口（T-05 永久回放调度器）。

用法（仓根执行；本脚本只做调度与结果记录，不直接断言 UI 行为）：
  python tests/basic/verify_basic.py --profile vue   # Playwright 真实浏览器双上下文
  python tests/basic/verify_basic.py --profile vm    # VM 轨 AutoUI MCP 驱动

前置（脚本会检测并给出明确失败）：
  vue: `auto run` 已启动（:17822 前端 + :17823 后端），后端 env：
       CHAT_TEST_MODE=1 + CHAT_DATA_DIR=<隔离目录>（不接触真实用户数据）。
  vm:  先有 :17823 后端（可由 `auto run` 提供），再以
       AUTO_REUSE_BACKEND=1 AUTO_HTTP_PORT=17823 AUTO_HTTP_BASE=http://127.0.0.1:17823
       `auto run -r vm` 启动 VM 实例（AutoUI MCP :9261）。

输出：stdout 摘要 + docs/plans/attachments/001/verify-<profile>.json（本地证据，
不入库）；退出码 0=全绿 / 1=存在失败或前置不满足。
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATT = ROOT / "docs" / "plans" / "attachments" / "001"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backend_ready(port=17823) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/identities", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def test_mode_on() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:17823/api/test/reset", method="POST")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def run_vue() -> dict:
    if not backend_ready():
        return {"ok": False, "error": "后端 :17823 不可达——先以 CHAT_TEST_MODE=1 + 隔离 CHAT_DATA_DIR 启动 `auto run`"}
    if not test_mode_on():
        return {"ok": False, "error": "后端未开 CHAT_TEST_MODE=1（/api/test/reset 不可用），拒绝在真实数据上验收"}
    env = dict(os.environ, CHAT_API="http://127.0.0.1:17823", CHAT_URL="http://localhost:17822",
               PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return {"ok": False, "error": "找不到 npx——需要 Node.js 工具链在 PATH"}
    proc = subprocess.run([npx, "playwright", "test"], cwd=ROOT / "tests", env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return {
        "ok": proc.returncode == 0,
        "command": "npx playwright test (tests/)",
        "exit": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_vm() -> dict:
    if not backend_ready():
        return {"ok": False, "error": "后端 :17823 不可达——VM 轨按 profile 复用外部后端，先启动 `auto run`"}
    if not test_mode_on():
        return {"ok": False, "error": "后端未开 CHAT_TEST_MODE=1，拒绝验收"}
    env = dict(os.environ, AUTO_REUSE_BACKEND="1", AUTO_HTTP_PORT="17823",
               AUTO_HTTP_BASE="http://127.0.0.1:17823", AUTOUI_MCP_PORT="9261",
               RUST_MIN_STACK="16777216", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(["node", "tests/basic/vm-basic.mjs"], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return {
        "ok": proc.returncode == 0,
        "command": "node tests/basic/vm-basic.mjs (AutoUI MCP :9261, AUTO_REUSE_BACKEND)",
        "exit": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["vue", "vm"], required=True)
    args = ap.parse_args()

    record = {
        "profile": args.profile,
        "started": datetime.datetime.now().isoformat(),
        "app_base": str(ROOT),
        "base_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                      text=True).stdout.strip(),
        "sources": {
            "api.at": sha256(ROOT / "src" / "back" / "api.at"),
            "db.at": sha256(ROOT / "src" / "back" / "db.at"),
            "repository.at": sha256(ROOT / "src" / "back" / "repository.at"),
            "chat_store.at": sha256(ROOT / "src" / "front" / "chat_store.at"),
        },
    }
    result = run_vue() if args.profile == "vue" else run_vm()
    record["result"] = result
    record["finished"] = datetime.datetime.now().isoformat()

    ATT.mkdir(parents=True, exist_ok=True)
    out = ATT / f"verify-{args.profile}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[verify_basic:{args.profile}] {'PASS' if result.get('ok') else 'FAIL'}")
    print(result.get("stdout_tail", result.get("error", ""))[-1500:])
    print(f"[evidence] {out}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
