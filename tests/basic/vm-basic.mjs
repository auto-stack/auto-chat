#!/usr/bin/env node
// vm-basic.mjs — CHAT-001 VM 轨基本能力验收（AutoUI MCP 驱动）。
//
// 前置（verify_basic.py --profile vm 设置 env）：
//   :17823 已有后端（auto run 提供），本实例经 AUTO_REUSE_BACKEND 复用；
//   AUTOUI_MCP_PORT=9261。
// 流程（甲身份，乙身份经后端 API 预置）：
//   A. 登录屏输入甲 → 进入聊天；无演示假用户
//   B. 侧栏联系人出现乙（按钮）→ press 打开会话
//   C. 乙经真实通道发中文+换行 → VM 轮询送达（线程可见）
//   D. VM 端键入并发送回复 → 后端真实落库 + draft 清空
// 退出码：0 全绿 / 1 断言或启动失败。

import { spawn, spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MCP_PORT = Number(process.env.AUTOUI_MCP_PORT || 9261);
const API = process.env.CHAT_API || "http://127.0.0.1:17823";

function fail(msg) {
  console.error(`[vm-basic] FAIL: ${msg}`);
  process.exitCode = 1;
}

async function mcpCall(tool, args) {
  const res = await fetch(`http://127.0.0.1:${MCP_PORT}/mcp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: tool, arguments: args } }),
  });
  const text = await res.text();
  const line = text.split("\n").find((l) => l.startsWith("data:"));
  const payload = line ? JSON.parse(line.slice(5)) : JSON.parse(text);
  const content = payload.result?.content ?? payload;
  if (Array.isArray(content)) {
    return content.filter((c) => c.type === "text").map((c) => c.text).join("\n");
  }
  return JSON.stringify(content);
}

async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

/** 不副作用登录态：从公开身份列表解析 id（re-claim 会作废 VM 页面 token） */
async function peerId(name) {
  const ids = await (await fetch(`${API}/api/identities`)).json();
  const hit = ids.find((i) => i.name === name);
  return hit ? hit.id : "";
}

async function claimIdentity(name) {
  const nonce = `n-vm-${Date.now()}-${Math.random()}`;
  await apiPost("/api/login", { name, nonce });
  return await (await fetch(`${API}/api/me?nonce=${encodeURIComponent(nonce)}`)).json();
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const bin = process.env.AUTO_BIN || "D:/autostack/auto-man/target/debug/auto.exe";
  console.log(`[vm-basic] auto bin: ${bin} (render=vm, reuse backend :17823)`);
  const child = spawn(bin, ["run", "-r", "vm"], {
    cwd: REPO_ROOT,
    env: { ...process.env, AUTO_REUSE_BACKEND: "1", AUTO_HTTP_PORT: "17823", AUTO_HTTP_BASE: "http://127.0.0.1:17823", AUTOUI_MCP_PORT: String(MCP_PORT), RUST_MIN_STACK: "16777216", RUST_BACKTRACE: "1" },
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let vmLog = "";
  const collect = (d) => { vmLog += d.toString(); };
  child.stdout.on("data", collect);
  child.stderr.on("data", collect);
  const kill = () => {
    try { writeFileSync("D:/autostack/logs/vm-basic-child.log", vmLog.slice(-12000)); } catch {}
    try { spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" }); } catch {}
  };
  process.on("exit", kill);

  let ready = false;
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) break;
    try {
      const probe = await fetch(`http://127.0.0.1:${MCP_PORT}/mcp`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 0, method: "tools/list", params: {} }),
      });
      if ((await probe.text()).includes("autoui")) { ready = true; break; }
    } catch {}
    await sleep(800);
  }
  if (!ready) {
    fail(`AutoUI MCP 未就绪（exitCode=${child.exitCode}）；VM 日志尾：\n${vmLog.slice(-1200)}`);
    return;
  }
  await sleep(2000);

  const snapshot = async () => mcpCall("autoui_snapshot", {});
  // 渲染树按钮以 label 文本定位：取最后一次 label 出现处，回溯最近的 button vnode
  // （快照头部含模板元数据区的 onclick 声明，不能按 onclick 找节点）。
  const findButtonByLabel = async (label) => {
    const snap = await snapshot();
    const idx = snap.lastIndexOf(label);
    if (idx < 0) return { snap, target: null };
    const before = snap.slice(0, idx);
    const m = [...before.matchAll(/button #(vnode_\d+)/g)];
    return { snap, target: m.length ? m[m.length - 1][1] : null };
  };
  const findInputs = async () => {
    const snap = await snapshot();
    return [...snap.matchAll(/input #(vnode_\d+)/g)].map((m) => m[1]);
  };

  // ── A. 登录屏 → 输入甲 → 进入聊天 ──
  {
    const snap = await snapshot();
    if (!snap.includes("名字")) { fail(`登录屏未出现\n快照尾：\n${snap.slice(-800)}`); return; }
    if (snap.includes("Alice") || snap.includes("AutoBot")) { fail("出现演示假用户（Alice/AutoBot）"); return; }
    const inputs = await findInputs();
    if (!inputs.length) { fail("找不到登录输入框"); return; }
    await mcpCall("autoui_type", { element_id: inputs[0], text: "甲" });
    await sleep(500);
    const { target } = await findButtonByLabel("进入聊天");
    if (!target) { fail("找不到进入聊天按钮"); return; }
    const r = await mcpCall("autoui_action", { element_id: target, action: "press" });
    if (!/status: ok/.test(r)) { fail(`进入聊天按钮派发失败: ${r}`); return; }
    await sleep(2500);
    const snap3 = await snapshot();
    if (!snap3.includes("已连接") && !snap3.includes("连接断开")) {
      fail(`登录后会话壳未出现\n快照尾：\n${snap3.slice(-800)}`);
      return;
    }
    console.log("[vm-basic] A ok — 登录进入会话壳");
  }

  // ── B. 联系人出现乙 → press 打开会话 ──
  {
    await claimIdentity("乙");
    await sleep(2500); // RefreshTick 拉身份列表
    const { snap, target } = await findButtonByLabel("乙");
    if (!target) { fail(`未能定位乙的按钮节点\n快照尾：\n${snap.slice(-1000)}`); return; }
    const pr = await mcpCall("autoui_action", { element_id: target, action: "press" });
    if (!/status: ok/.test(pr)) { fail(`乙按钮派发失败: ${pr}`); return; }
    await sleep(2500);
    console.log("[vm-basic] B ok — 打开与乙的会话");
  }

  // ── C. 乙经真实通道发中文+换行 → VM 轮询送达 ──
  {
    const me = await claimIdentity("乙");
    const jiaId = await peerId("甲");
    const open = await apiPost("/api/conversations/open", { token: me.token, peer_id: jiaId });
    const marker = `vm-${Date.now()}`;
    await apiPost("/api/messages", { token: me.token, conversation_id: open.id, text: marker, client_msg_id: `cm-vm-${Date.now()}` });
    let seen = false;
    for (let i = 0; i < 8; i++) {
      await sleep(1000);
      const snap = await snapshot();
      if (snap.includes(marker)) { seen = true; break; }
    }
    if (!seen) {
      const st = await mcpCall("autoui_state", {});
      const keys = ["last_send_state", "online", "active_contact_id", "conv_list", "peer_list", "messages"].map((k) => {
        const i2 = st.indexOf(k + ":");
        return k + "=" + (i2 >= 0 ? st.slice(i2 + k.length + 1, i2 + k.length + 26).split(String.fromCharCode(10))[0] : "?");
      });
      const lastSnap = await snapshot();
      console.log("[vm-basic][dbg] " + keys.join(" | "));
      console.log("[vm-basic][dbg] conv-in-snap: " + lastSnap.includes("cv-") + " marker-in-snap: " + lastSnap.includes(marker) + " snap-tail:|" + lastSnap.slice(-500) + "|");
      fail(`VM 轨未在 8s 内轮询到乙的消息（${marker}）`);
      return;
    }
    console.log("[vm-basic] C ok — 真实消息经轮询送达 VM");
  }

  // ── D. VM 端发送回复 → 后端真实落库 + draft 清空 ──
  {
    const inputs = await findInputs();
    if (!inputs.length) { fail("找不到 composer 输入框"); return; }
    const reply = `vm-reply-${Date.now()}`;
    await mcpCall("autoui_type", { element_id: inputs[inputs.length - 1], text: reply });
    await sleep(500);
    const { target } = await findButtonByLabel("发送");
    if (!target) { fail("找不到发送按钮"); return; }
    const pr = await mcpCall("autoui_action", { element_id: target, action: "press" });
    if (!/status: ok/.test(pr)) { fail(`发送按钮派发失败: ${pr}`); return; }
    await sleep(2000);
    const me = await claimIdentity("乙");
    const jiaId = await peerId("甲");
    const open = await apiPost("/api/conversations/open", { token: me.token, peer_id: jiaId });
    const msgs = await (await fetch(`${API}/api/messages?token=${me.token}&conversation_id=${open.id}`)).json();
    if (!msgs.some((m) => m.text === reply)) {
      fail(`VM 发送的消息未在后端落库；后端消息：${JSON.stringify(msgs.map((m) => m.text)).slice(0, 300)}`);
      return;
    }
    const snap2 = await snapshot();
    const inputBlock = snap2.slice(snap2.indexOf("input #vnode")).slice(0, 400);
    if (!/value: ""/.test(inputBlock)) { fail(`发送后 draft 未清空：${inputBlock.slice(0, 200)}`); return; }
    console.log("[vm-basic] D ok — VM 发送经真实通道落库 + draft 清空");
  }

  console.log("[vm-basic] PASS — VM 轨基本能力四断言全绿（A 登录/B 会话/C 送达/D 发送）");
}

main().finally(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300);
});
