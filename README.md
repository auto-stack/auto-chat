# auto-chat

人与人聊天，使用 AutoLang / AutoUI 开发。更新：2026-10-31。

## 当前能力与边界

[CHAT-001](docs/plans/archived/001-real-conversations.md) 已交付归档：联系人、一对一文字收发、会话隔离、失败重发、SQLite 历史与重开。现实现合同见[基本能力规范](docs/specs/chat/basic-capabilities.md)。

[CHAT-002](docs/plans/002-standalone-identity-and-isolation.md) 进行中（executing，3/9）：T-00 决策稿、T-01 自管隔离验收门、T-03 移除公开 SSE 私聊旁路（送达统一为已鉴权按会话轮询，Vue/VM 双轨 8/8、4/4 回归通过）已交付。**身份凭据部分阻塞**：当前工具链后端轨不存在受支持的 ≥128-bit 安全随机原语（a2r-std 无 rand；bundled SQLite Windows 种子非 CSPRNG），最小前置 P-REQ-1 已提请 auto-lang owner，见计划 §10。

## 运行与验证

安装匹配版本的 auto CLI，仓根执行 `auto run`（Vue，前端17822、Rust后端17823）。共享 StyleKit 位于固定的 `vendor/stylekit`。

旧版原生验收需先有本 app 后端，再在 PowerShell 配置后运行：

```powershell
$env:AUTO_REUSE_BACKEND = '1'
$env:AUTO_HTTP_PORT = '17823'
$env:AUTO_HTTP_BASE = 'http://127.0.0.1:17823'
auto run -r vm
```

数据目录使用 `CHAT_DATA_DIR` 覆盖；不要对真实用户库运行测试或 reset。

双端验收入口（CHAT-002 T-01 起自管隔离门，无需外部预启动服务）：
`python tests/basic/verify_basic.py --profile vue` / `--profile vm`。脚本自管准备（有界 auto build + cargo build）、随机端口、隔离 `CHAT_DATA_DIR` 与端口→PID 归属检查，仅收割本次子树；证据 JSON 落 `D:/autostack/plan-artifacts/plan-002/`（本地，不入库）。新增认证门仍待 002 的框架前置（见上）。

## 计划与开发

[路线图](docs/roadmap-v0.6.md) · [当前后续计划002](docs/plans/002-standalone-identity-and-isolation.md) · [AutoOS基础总表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)

开发、计划与顺序复审使用 `D:/autostack/auto-chat` 独立 clone 的 main。当前只准备计划/README/roadmap并推送；不实现、不更新 AutoOS 子模块，后续由统一集成计划登记精确交付版本。Linux 等发行版 Nix＋COSMIC 基础；跨应用通讯另排。

## 来源与组合

来源提交与文件 hash 见 `SOURCE-IMPORT.json`；历史 `source-sync` 保留来源基线。AutoOS 组合目录为 [apps/auto-chat](https://github.com/auto-stack/auto-os/tree/main/apps/auto-chat)，其 pin 可能落后本仓，不作为默认开发目录。旧 Demo 目录仅属历史。
