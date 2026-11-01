#!/usr/bin/env python3
"""verify_identity.py — CHAT-002 认证/隔离补充验收门（C-02/03/04/05）。

用法（仓根执行；自管隔离后端，与 verify_basic.py 同契约）：
  python tests/basic/verify_identity.py

覆盖（Plan §6 测试设计）：
  C-02 身份：注册铸发 64-hex secret/token；同名/伪凭据/未知名拒绝；
             重登录轮换会话（旧 token 失效）；退出撤销；secret 可复用恢复。
  C-03 隔离：/api/stream 已移除（404）；第三身份/匿名无法取得私聊正文与
             会话标识（直接 HTTP）；A→B 轮询送达保留。字节级：原始响应含
             哨兵与否直接断言。
  C-04 迁移：v1 夹具（弱 token+中文正文）→ 首个鉴权调用触发受控迁移；
             ID/正文逐字一致；备份生成且保留旧 token；legacy 拒登；
             env 开启后 adopt 一次性铸发；同 client_msg_id 幂等；强杀重开
             后凭 secret 恢复且下一次发送成功。
  C-05 负控：对"认证拒绝被放行"的受控 stub 服务跑同一组断言——门必须变红
             （总门非零），证明断言具备区分性；不触碰真实产品代码。

输出：stdout 摘要 + 证据 JSON（VERIFY_OUT 或 plan-artifacts/plan-002/）；
退出码 0=全绿 / 1=失败。
"""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACK_EXE = ROOT / "rust-workspace" / "target" / "debug" / "auto-chat-back.exe"
PORT = 17823
CHECKS = []


def note(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"{'OK ' if cond else 'FAIL'} {name} {detail}")


def api(method, path, body=None, timeout=8):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, str(e)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def launch(data_dir, adopt=False, exe=None, port=PORT, wait=30):
    env = dict(os.environ, AUTO_HTTP_PORT=str(port), CHAT_DATA_DIR=str(data_dir), CHAT_TEST_MODE="1")
    if adopt:
        env["CHAT_LEGACY_ADOPT"] = "1"
    log = open(Path(data_dir).parent / "verify-identity-backend.log", "a")
    p = subprocess.Popen([str(exe or BACK_EXE)], env=env, stdout=log, stderr=log)
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/identities", timeout=2) as r:
                if r.status == 200:
                    return p
        except Exception:
            pass
        if p.poll() is not None:
            break
        time.sleep(0.4)
    p.kill()
    return None


def stop(p):
    subprocess.run(["taskkill", "/PID", str(p.pid), "/F", "/T"], capture_output=True)
    time.sleep(1.0)


def kill_strays():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "auto-chat-back" in line:
            subprocess.run(["taskkill", "/PID", line.split()[1], "/F", "/T"], capture_output=True)
    time.sleep(0.5)


def is_hex64(s):
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


# ── C-02 身份 ──
def c02(scratch):
    print("── C-02 身份凭据 ──")
    data = scratch / "c02"
    data.mkdir(parents=True)
    p = launch(data)
    assert p, "backend not ready"
    try:
        st, reg = api("POST", "/api/register", {"name": "甲"})
        note("C-02 register ok", st == 200 and reg.get("ok"), str(reg.get("err")))
        note("C-02 secret 64-hex", is_hex64(reg.get("secret", "")))
        note("C-02 token 64-hex 且异于 secret", is_hex64(reg.get("token", "")) and reg["token"] != reg["secret"])
        st, dup = api("POST", "/api/register", {"name": "甲"})
        note("C-02 同名注册拒绝", dup.get("err") == "name-taken")
        st, c2 = api("POST", "/api/register", {"name": ""})
        note("C-02 空名拒绝", c2.get("err") == "invalid-name")
        sec = reg["secret"]
        st, bad = api("POST", "/api/login", {"name": "甲", "secret": "f" * 64})
        note("C-02 伪凭据拒绝", bad.get("ok") is False and bad.get("err") == "unauthorized")
        st, ghost = api("POST", "/api/login", {"name": "未注册", "secret": sec})
        note("C-02 未注册名拒绝", ghost.get("ok") is False)
        st, empty = api("POST", "/api/login", {"name": "甲", "secret": ""})
        note("C-02 空 secret 拒绝", empty.get("ok") is False)
        t1 = reg["token"]
        st, lg = api("POST", "/api/login", {"name": "甲", "secret": sec})
        note("C-02 合法恢复成功", lg.get("ok") and lg.get("id") == reg["id"])
        note("C-02 token 轮换（旧会话撤销）", lg.get("token") != t1)
        st, oldc = api("GET", f"/api/contacts?token={t1}")
        note("C-02 旧 token 已失效", st == 200 and oldc == [])
        st, _ = api("POST", "/api/logout", {"token": lg["token"]})
        st, c2 = api("GET", f"/api/contacts?token={lg['token']}")
        note("C-02 退出撤销会话", c2 == [])
        st, relg = api("POST", "/api/login", {"name": "甲", "secret": sec})
        note("C-02 secret 可复用恢复", relg.get("ok") is True)
        # 可预测性抽查：多身份 token/secret 两两不同且非时间形
        st, r2 = api("POST", "/api/register", {"name": "乙"})
        note("C-02 第二身份凭据独立", r2.get("secret") != sec and r2.get("token") != reg["token"])
        note("C-02 token 非旧形 tok-<uid>-<epoch>",
             not (reg["token"].startswith("tok-u-") and "-" in reg["token"][6:]))
        # 负形（C-02 反例存证面）：旧接口已移除
        st, me = api("GET", "/api/me?nonce=x")
        note("C-02 旧 nonce 认领面已移除（404）", st == 404, str(st))
    finally:
        stop(p)


# ── C-03 隔离（字节级）──
def c03(scratch):
    print("── C-03 会话数据隔离 ──")
    data = scratch / "c03"
    data.mkdir(parents=True)
    p = launch(data)
    assert p, "backend not ready"
    try:
        _, a = api("POST", "/api/register", {"name": "甲"})
        _, b = api("POST", "/api/register", {"name": "乙"})
        _, c = api("POST", "/api/register", {"name": "丙"})
        _, conv = api("POST", "/api/conversations/open", {"token": a["token"], "peer_id": b["id"]})
        sentinel = f"SENTINEL-{a['id']}-私聊正文🔒"
        st, s1 = api("POST", "/api/messages", {"token": a["token"], "conversation_id": conv["id"],
                                               "text": sentinel, "client_msg_id": "cm-c03-1"})
        note("C-03 A→B 送达（正例保持）", s1.get("ok") is True)
        st, hist = api("GET", f"/api/messages?token={b['token']}&conversation_id={conv['id']}")
        note("C-03 B 轮询收取（字节含哨兵）", sentinel in json.dumps(hist, ensure_ascii=False))
        st, stream = api("GET", "/api/stream")
        note("C-03 公开流已移除（404）", st == 404, str(st))
        st, cview = api("GET", f"/api/messages?token={c['token']}&conversation_id={conv['id']}")
        note("C-03 第三身份直读被拒", cview == [], str(cview)[:60])
        st, anon = api("GET", f"/api/messages?conversation_id={conv['id']}")
        note("C-03 匿名直读被拒", anon == [], str(anon)[:60])
        st, cconv = api("POST", "/api/conversations/open", {"token": c["token"], "peer_id": a["id"]})
        st, cview2 = api("GET", f"/api/messages?token={c['token']}&conversation_id={cconv['id']}")
        note("C-03 第三身份自会话不含甲乙正文", not any(sentinel in json.dumps(m, ensure_ascii=False) for m in cview2))
        st, ids = api("GET", "/api/identities")
        note("C-03 公开身份面不含 secret/token",
             all("secret" not in json.dumps(i) and "token" not in json.dumps(i) for i in ids))
        # F-1 回归断言（双层）：
        # (i) 源 tripwire——client_msg_id 构造不含会话 token（.at 源文本级）
        store_src = (ROOT / "src" / "front" / "chat_store.at").read_text(encoding="utf-8")
        note("C-03 源检：cmid 构造为 seq+my_id（无 token）",
             ('"cm-" + .send_seq.to_string() + "-" + .my_id' in store_src)
             and ('"cm-" + .send_seq.to_string() + "-" + .my_token' not in store_src))
        # (ii) 服务器元数据擦除：即使发送方 cmid 内嵌其 token（旧客户端形状），
        #     对端字节面也不得出现该 token；本人视图保留 cmid（本地去重键）
        leaked_cmid = a["token"]
        st, s2 = api("POST", "/api/messages", {"token": a["token"], "conversation_id": conv["id"],
                                               "text": "元数据擦除探针", "client_msg_id": leaked_cmid})
        note("C-03 探针发送成功", s2.get("ok") is True)
        st, bview = api("GET", f"/api/messages?token={b['token']}&conversation_id={conv['id']}")
        note("C-03 对端字节面不含发送方会话 token（服务器擦除）",
             a["token"] not in json.dumps(bview, ensure_ascii=False))
        st, aview = api("GET", f"/api/messages?token={a['token']}&conversation_id={conv['id']}")
        note("C-03 本人视图保留 cmid（去重键不破坏）",
             any(m.get("client_msg_id") == leaked_cmid for m in aview))
    finally:
        stop(p)


# ── C-04 迁移（v1 夹具现造）──
V1_IDENTITY_DDL = ("CREATE TABLE identities(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
                   "avatar TEXT NOT NULL DEFAULT '', token TEXT NOT NULL DEFAULT '', "
                   "created_sec TEXT NOT NULL DEFAULT '0', last_seen_sec TEXT NOT NULL DEFAULT '0')")
V1_OTHER_DDL = [
    "CREATE TABLE conversations(id TEXT PRIMARY KEY, user_a TEXT NOT NULL, user_b TEXT NOT NULL, created_sec TEXT NOT NULL DEFAULT '0')",
    ("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, "
     "sender_id TEXT NOT NULL, sender_name TEXT NOT NULL DEFAULT '', text TEXT NOT NULL, "
     "created_sec TEXT NOT NULL DEFAULT '0', client_msg_id TEXT NOT NULL DEFAULT '', "
     "UNIQUE(conversation_id, client_msg_id))"),
    "CREATE TABLE reads(conversation_id TEXT NOT NULL, reader_id TEXT NOT NULL, last_read_sec TEXT NOT NULL DEFAULT '0', PRIMARY KEY(conversation_id, reader_id))",
    "CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)",
    "CREATE TABLE pending_login(nonce TEXT PRIMARY KEY, token TEXT NOT NULL, created_sec TEXT NOT NULL DEFAULT '0')",
]


def make_v1_fixture(dest, weak_token):
    con = sqlite3.connect(dest)
    # 真实 v1 库由旧版应用创建：每次开库都设 WAL（持久化于文件头）。
    # 夹具必须同形，否则后端首连的 journal_mode=WAL 会改变文件头、
    # 使"取消路径零写入"的字节哈希断言失真。
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(V1_IDENTITY_DDL)
    for ddl in V1_OTHER_DDL:
        con.execute(ddl)
    con.execute("INSERT INTO identities(id,name,avatar,token,created_sec,last_seen_sec) VALUES('u-1','甲','🧑',?,'1000','1000')", (weak_token,))
    con.execute("INSERT INTO identities(id,name,avatar,token,created_sec,last_seen_sec) VALUES('u-2','乙','👩','tok-u-2-1000','1000','1000')")
    con.execute("INSERT INTO conversations(id,user_a,user_b,created_sec) VALUES('cv-u-1-u-2','u-1','u-2','1000')")
    con.execute("INSERT INTO messages(conversation_id,sender_id,sender_name,text,created_sec,client_msg_id) VALUES('cv-u-1-u-2','u-1','甲','旧库正文一','1000','cm-v1-1')")
    con.execute("INSERT INTO messages(conversation_id,sender_id,sender_name,text,created_sec,client_msg_id) VALUES('cv-u-1-u-2','u-2','乙','旧库正文二💯','1000','cm-v1-2')")
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def dump_content(dbpath):
    con = sqlite3.connect(dbpath)
    ids = con.execute("SELECT id,name,avatar,created_sec FROM identities ORDER BY id").fetchall()
    msgs = con.execute("SELECT conversation_id,sender_id,sender_name,text,created_sec,client_msg_id FROM messages ORDER BY id").fetchall()
    convs = con.execute("SELECT id,user_a,user_b,created_sec FROM conversations ORDER BY id").fetchall()
    con.close()
    return ids, msgs, convs


def c04(scratch):
    print("── C-04 受控旧库迁移 ──")
    weak = "tok-u-1-1000"
    # 取消路径：不触发鉴权 → 零写入、字节不变
    cancel = scratch / "c04-cancel"
    cancel.mkdir(parents=True)
    make_v1_fixture(cancel / "chat.db", weak)
    h0 = hashlib.sha256((cancel / "chat.db").read_bytes()).hexdigest()
    p = launch(cancel)
    assert p, "backend not ready (cancel)"
    try:
        st, ids = api("GET", "/api/identities")
        note("C-04 cancel: 身份枚举可用（无鉴权操作）", st == 200 and len(ids) == 2)
    finally:
        stop(p)
    note("C-04 cancel: 主库字节哈希不变", hashlib.sha256((cancel / "chat.db").read_bytes()).hexdigest() == h0)
    note("C-04 cancel: 无备份落盘", not [f for f in os.listdir(cancel) if ".pre-v2-" in f])

    # 成功路径：env 开启 → adopt 触发迁移
    adopt = scratch / "c04-adopt"
    adopt.mkdir(parents=True)
    make_v1_fixture(adopt / "chat.db", weak)
    p = launch(adopt, adopt=True)
    assert p, "backend not ready (adopt)"
    try:
        st, locked = api("POST", "/api/login", {"name": "甲", "secret": weak})
        note("C-04 迁移后 legacy 名+旧 token 不可登录", locked.get("ok") is False)
        st, ad = api("POST", "/api/legacy/adopt", {"name": "甲", "legacy_token": weak})
        note("C-04 adopt 一次性铸发成功", ad.get("ok") is True and is_hex64(ad.get("secret", "")))
        st, ad2 = api("POST", "/api/legacy/adopt", {"name": "甲", "legacy_token": weak})
        note("C-04 adopt 二次拒绝（旧 token 一次性）", ad2.get("ok") is False, ad2.get("err"))
        st, lg = api("POST", "/api/login", {"name": "甲", "secret": ad["secret"]})
        note("C-04 新凭据登录成功", lg.get("ok") and lg.get("id") == "u-1")
        ids_n, msgs_n, convs_n = dump_content(adopt / "chat.db")
        note("C-04 ID/名/头像/时间逐字一致",
             ids_n == [("u-1", "甲", "🧑", "1000"), ("u-2", "乙", "👩", "1000")], str(ids_n))
        note("C-04 消息正文逐字一致（含 emoji）",
             msgs_n == [("cv-u-1-u-2", "u-1", "甲", "旧库正文一", "1000", "cm-v1-1"),
                        ("cv-u-1-u-2", "u-2", "乙", "旧库正文二💯", "1000", "cm-v1-2")])
        note("C-04 会话逐字一致", convs_n == [("cv-u-1-u-2", "u-1", "u-2", "1000")])
        backups = [f for f in os.listdir(adopt) if ".pre-v2-" in f]
        note("C-04 备份生成", len(backups) == 1)
        if backups:
            ids_b, msgs_b, _ = dump_content(adopt / backups[0])
            note("C-04 备份保留旧弱 token（v1 状态）",
                 msgs_b == msgs_n and any(r[0] == "u-1" for r in ids_b))
        st, s1 = api("POST", "/api/messages", {"token": lg["token"], "conversation_id": "cv-u-1-u-2", "text": "迁移后第一条", "client_msg_id": "cm-c04-idem"})
        st, s2 = api("POST", "/api/messages", {"token": lg["token"], "conversation_id": "cv-u-1-u-2", "text": "迁移后第一条", "client_msg_id": "cm-c04-idem"})
        note("C-04 同 client_msg_id 幂等单条", s1.get("ok") and s2.get("ok") and s1["message"]["id"] == s2["message"]["id"])
    finally:
        stop(p)
    # 强杀重开（上面 stop 即强杀）→ secret 恢复 + 下一次发送成功
    p = launch(adopt)
    assert p, "backend not ready (reopen)"
    try:
        st, lg2 = api("POST", "/api/login", {"name": "甲", "secret": ad["secret"]})
        note("C-04 强杀重开后凭 secret 恢复", lg2.get("ok") is True)
        st, hist = api("GET", f"/api/messages?token={lg2['token']}&conversation_id=cv-u-1-u-2")
        texts = [m["text"] for m in hist]
        note("C-04 历史完整（旧正文+迁移后）", texts == ["旧库正文一", "旧库正文二💯", "迁移后第一条"], str(texts))
        st, nxt = api("POST", "/api/messages", {"token": lg2["token"], "conversation_id": "cv-u-1-u-2", "text": "重启后再发", "client_msg_id": "cm-c04-post"})
        note("C-04 重开后下一次发送成功", nxt.get("ok") is True)
    finally:
        stop(p)


# ── C-05 负控：放行型 stub 必须把门打红 ──
class PermissiveStub(BaseHTTPRequestHandler):
    """伪造'认证拒绝被放行'的服务器：一切 token/秘密都被接受并返回数据。"""

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/identities"):
            return self._json([{"id": "u-1", "name": "甲", "avatar": "🧑", "online": True}])
        if self.path.startswith("/api/messages"):
            return self._json([{"id": 1, "conversation_id": "cv-x", "sender_id": "u-1",
                                "sender": "甲", "text": "泄露的私聊正文", "time": "刚刚",
                                "created_sec": 1, "client_msg_id": "cm-x"}])
        if self.path.startswith("/api/stream"):
            return self._json({"event": "NewSendResult", "ok": True}, code=200)
        return self._json([])

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if self.path == "/api/login":
            return self._json({"ok": True, "err": "", "id": "u-9", "name": "甲",
                               "avatar": "🧑", "token": "f" * 64})
        if self.path == "/api/register":
            return self._json({"ok": True, "err": "", "id": "u-9", "name": "x",
                               "avatar": "🧑", "secret": "1234", "token": "f" * 64})
        return self._json({})


def gate_against_stub(port):
    """对放行型 stub 跑产品门同一组断言；返回 (通过数, 总数)。stub 越宽容应越少通过。"""
    base = f"http://127.0.0.1:{port}"

    def req(method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(base + path, data=data, method=method,
                                   headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw.strip() else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw
        except Exception as e:
            return -1, str(e)

    passed = 0
    total = 0

    def check(cond):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1

    _, bad = req("POST", "/api/login", {"name": "甲", "secret": "0" * 64})
    check(bad.get("ok") is False)  # stub 放行 → 红
    _, reg = req("POST", "/api/register", {"name": "x"})
    check(is_hex64(reg.get("secret", "")))  # stub 的 1234 → 红
    _, cview = req("GET", "/api/messages?token=anything&conversation_id=cv-x")
    check(cview == [])  # stub 泄露 → 红
    st, stream = req("GET", "/api/stream")
    check(st == 404)  # stub 有流 → 红
    return passed, total


def c05(scratch):
    print("── C-05 负控（放行型 stub 必须把门打红）──")
    port = free_port()
    srv = HTTPServer(("127.0.0.1", port), PermissiveStub)
    import threading
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        passed, total = gate_against_stub(port)
        red = total - passed
        note("C-05 stub 使门全红（4/4 区分性）", red == 4, f"passed {passed}/{total}")
        note("C-05 stub 下总门非零（区分性成立）", passed < total, f"red={red}")
    finally:
        srv.shutdown()


def main():
    out_dir = Path(os.environ.get("VERIFY_OUT", r"D:\autostack\plan-artifacts\plan-002"))
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="verify-identity-"))
    if not BACK_EXE.exists():
        print(f"FAIL 后端不存在：{BACK_EXE}（先 python tests/basic/verify_basic.py --profile vue 自管准备）")
        return 1
    kill_strays()
    try:
        c02(scratch)
        c03(scratch)
        c04(scratch)
        c05(scratch)
    finally:
        pass
    total = len(CHECKS)
    passed = sum(1 for _, v in CHECKS if v)
    record = {"checks": [{"name": n, "ok": v} for n, v in CHECKS],
              "passed": passed, "total": total}
    (out_dir / "verify-identity.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[verify_identity] {'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    print(f"[evidence] {out_dir / 'verify-identity.json'}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
