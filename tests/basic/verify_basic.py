#!/usr/bin/env python3
"""verify_basic.py — 基本能力双轨验收入口（自管隔离门，CHAT-002 T-01 重构）。

用法（仓根执行；本脚本自管被测服务，不依赖外部已启动实例）：
  python tests/basic/verify_basic.py --profile vue   # 自管后端+vite+Playwright 真实浏览器双上下文
  python tests/basic/verify_basic.py --profile vm    # 自管后端+AutoUI MCP 驱动 VM 实例

自管契约（CHAT-002 T-01/决策稿 §3）：
  1. 准备（有界）：rust-workspace/auto-chat-back 缺失 → `auto build`（≤300s）；
     后端 exe 缺失 → `cargo build -p auto-chat-back`（≤300s）。失败分类非零退出。
  2. 隔离启动：随机空闲端口（vue 轨后端/前端均随机；vm 轨渲染器由 vm-basic.mjs
     驱动，后端端口经 env 透传）；隔离 CHAT_DATA_DIR（本次新建）；CHAT_TEST_MODE=1。
  3. 身份检查：后端就绪探针 GET /api/identities（只读；绝不向既有服务发 reset）；
     端口→PID 映射必须等于本脚离子进程 PID；启动前断言端口空闲。
  4. 清理：仅 taskkill 本次子进程树；不触碰 17822/17823 等既有服务。

输出：stdout 摘要 + 证据 JSON（VERIFY_OUT 或 D:/autostack/plan-artifacts/plan-002/
verify-<profile>.json，本地证据不入库）；退出码 0=全绿 / 1=失败或前置不满足。
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACK_EXE = ROOT / "rust-workspace" / "target" / "debug" / "auto-chat-back.exe"
BACK_CRATE = ROOT / "rust-workspace" / "auto-chat-back"
FRONT_DIR = ROOT / "gen" / "front" / "vue"
AUTO_EXE = Path(os.environ.get("AUTO_BIN", r"D:\autostack\auto-man\target\debug\auto.exe"))
COLD_TIMEOUT = 300
READY_TIMEOUT = 90


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def port_free(port: int) -> bool:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def pid_of_port(port: int) -> int:
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f"127.0.0.1:{port}" in line and "LISTENING" in line:
            try:
                return int(line.split()[-1])
            except ValueError:
                return -1
    return -1


def run_bounded(cmd, cwd, timeout, log_path):
    """有界子进程；超时/非零都返回 (ok, tail)。"""
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        try:
            p = subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                               timeout=timeout, shell=True)
            ok = p.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
    return ok, tail


def ensure_backend_bin(record: dict) -> str | None:
    """准备（有界）：缺生成物先 auto build，缺 exe 再 cargo build。返回错误或 None。"""
    if not BACK_CRATE.exists():
        ok, tail = run_bounded(f'"{AUTO_EXE}" build', ROOT, COLD_TIMEOUT,
                               Path(tempfile.gettempdir()) / "chat-verify-autobuild.log")
        if not ok:
            return f"auto build 失败（准备阶段，详见日志 tail）：{tail[-500:]}"
        record["prep_auto_build"] = "ran"
    if not BACK_EXE.exists():
        t0 = time.time()
        ok, tail = run_bounded("cargo build -p auto-chat-back", ROOT / "rust-workspace",
                               COLD_TIMEOUT, Path(tempfile.gettempdir()) / "chat-verify-cargo.log")
        record["prep_cargo_seconds"] = round(time.time() - t0, 1)
        if not ok:
            return f"cargo build 失败（冷准备 ≤{COLD_TIMEOUT}s，详见日志 tail）：{tail[-500:]}"
    if not BACK_EXE.exists():
        return "后端 exe 仍缺失（准备后）"
    return None


def wait_ready(url: str, child: subprocess.Popen, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if child.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def kill_tree(pid: int):
    subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, text=True)


def start_backend(record: dict, data_dir: Path, port: int):
    """隔离启动后端（副本 exe，避免 auto run 重生成时的 relink 文件锁）。"""
    bin_copy = Path(record["scratch"]) / "bin" / "auto-chat-back.exe"
    bin_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(BACK_EXE, bin_copy)
    log = open(Path(record["scratch"]) / f"backend-{record['profile']}.log", "w")
    p = subprocess.Popen([str(bin_copy)],
                         env=dict(os.environ, AUTO_HTTP_PORT=str(port),
                                  CHAT_DATA_DIR=str(data_dir), CHAT_TEST_MODE="1"),
                         stdout=log, stderr=log)
    ok = wait_ready(f"http://127.0.0.1:{port}/api/identities", p, READY_TIMEOUT)
    pid_ok = pid_of_port(port) == p.pid
    record["backend"] = {"pid": p.pid, "port": port, "ready": ok, "pid_match": pid_ok,
                         "data_dir": str(data_dir)}
    if not ok:
        kill_tree(p.pid)
        tail = Path(record["scratch"]) / f"backend-{record['profile']}.log"
        return None, f"后端未就绪（≤{READY_TIMEOUT}s；分类 ready-timeout/crash rc={p.returncode}）: {tail.read_text(encoding='utf-8', errors='replace')[-400:] if tail.exists() else ''}"
    if not pid_ok:
        kill_tree(p.pid)
        return None, f"端口→PID 归属检查失败（监听者非本次子进程 {p.pid}），拒绝在共享端口上验收"
    return p, None


def run_vue(record: dict) -> tuple[bool, str]:
    err = ensure_backend_bin(record)
    if err:
        return False, err
    back_port, front_port = free_port(), free_port()
    if back_port == front_port or not port_free(back_port) or not port_free(front_port):
        return False, "随机端口预检失败"
    data_dir = Path(record["scratch"]) / "data-vue"
    data_dir.mkdir(parents=True, exist_ok=True)
    back, err = start_backend(record, data_dir, back_port)
    if err:
        return False, err
    procs = [back]
    try:
        flog = open(Path(record["scratch"]) / "vite.log", "w")
        vite = subprocess.Popen(["pnpm", "dev"], cwd=str(FRONT_DIR), shell=True,
                                env=dict(os.environ, AUTO_HTTP_PORT=str(back_port),
                                         AUTO_FRONT_PORT=str(front_port)),
                                stdout=flog, stderr=subprocess.STDOUT)
        procs.append(vite)
        if not wait_ready(f"http://localhost:{front_port}/", vite, READY_TIMEOUT):
            return False, f"vite 未就绪（≤{READY_TIMEOUT}s）rc={vite.returncode}"
        env = dict(os.environ, CHAT_API=f"http://127.0.0.1:{back_port}",
                   CHAT_URL=f"http://localhost:{front_port}",
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx:
            return False, "找不到 npx——需要 Node.js 工具链在 PATH"
        pw = subprocess.run([npx, "playwright", "test"], cwd=str(ROOT / "tests"), env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=600)
        record["suite"] = {"command": "npx playwright test", "exit": pw.returncode}
        (Path(record["scratch"]) / "vue-playwright.out").write_text(pw.stdout, encoding="utf-8")
        return pw.returncode == 0, pw.stdout[-2500:]
    finally:
        for p in procs:
            kill_tree(p.pid)


def run_vm(record: dict) -> tuple[bool, str]:
    err = ensure_backend_bin(record)
    if err:
        return False, err
    port = free_port()
    data_dir = Path(record["scratch"]) / "data-vm"
    data_dir.mkdir(parents=True, exist_ok=True)
    back, err = start_backend(record, data_dir, port)
    if err:
        return False, err
    try:
        mcp_port = free_port()
        env = dict(os.environ, AUTO_REUSE_BACKEND="1", AUTO_HTTP_PORT=str(port),
                   AUTO_HTTP_BASE=f"http://127.0.0.1:{port}",
                   CHAT_API=f"http://127.0.0.1:{port}",
                   AUTOUI_MCP_PORT=str(mcp_port), RUST_MIN_STACK="16777216",
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.run(["node", "tests/basic/vm-basic.mjs"], cwd=str(ROOT), env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=600)
        record["suite"] = {"command": "node tests/basic/vm-basic.mjs", "exit": proc.returncode}
        (Path(record["scratch"]) / "vm-basic.out").write_text(
            proc.stdout + "\n===STDERR===\n" + proc.stderr, encoding="utf-8")
        return proc.returncode == 0, (proc.stdout + proc.stderr)[-2500:]
    finally:
        kill_tree(back.pid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["vue", "vm"], required=True)
    args = ap.parse_args()

    out_dir = Path(os.environ.get(
        "VERIFY_OUT", r"D:\autostack\plan-artifacts\plan-002"))
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f"chat-verify-{args.profile}-"))

    record = {
        "profile": args.profile,
        "started": datetime.datetime.now().isoformat(),
        "app_base": str(ROOT),
        "scratch": str(scratch),
        "base_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                      text=True).stdout.strip(),
        "sources": {
            "api.at": sha256(ROOT / "src" / "back" / "api.at"),
            "db.at": sha256(ROOT / "src" / "back" / "db.at"),
            "repository.at": sha256(ROOT / "src" / "back" / "repository.at"),
            "chat_store.at": sha256(ROOT / "src" / "front" / "chat_store.at"),
        },
    }
    t0 = time.time()
    if args.profile == "vue":
        ok, detail = run_vue(record)
    else:
        ok, detail = run_vm(record)
    record["result"] = {"ok": ok, "seconds": round(time.time() - t0, 1), "detail": detail}
    record["finished"] = datetime.datetime.now().isoformat()

    out = out_dir / f"verify-{args.profile}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[verify_basic:{args.profile}] {'PASS' if ok else 'FAIL'} ({record['result']['seconds']}s)")
    print(detail[-1500:])
    print(f"[evidence] {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
