# auto-chat

人与人聊天，使用 AutoLang / AutoUI 开发。更新：2026-10-31。

## 当前能力与边界

[CHAT-001](docs/plans/archived/001-real-conversations.md) 已交付归档：联系人、一对一文字收发、会话隔离、失败重发、SQLite 历史与重开。现实现合同见[基本能力规范](docs/specs/chat/basic-capabilities.md)。

[CHAT-002](docs/plans/002-standalone-identity-and-isolation.md) 进行中（executing 8/9，复审中）。已交付：

- **凭据模型**：注册时服务器铸发 256-bit 恢复凭据（secret）并一次性展示；登录=名字+secret，服务端精确匹配；会话 token 高熵随机、重登即轮换、退出即撤销；同名不再授予身份。
- **送达**：移除公开 SSE 单总线（会把私聊载荷投给任意连接），送达统一为已鉴权按会话轮询（双轨一致，1s 粒度）。
- **旧库受控迁移**：首个鉴权调用前自动备份（`chat.db.pre-v2-<ts>.bak`）并加列；旧身份全部 `legacy` 锁定（旧弱 token 失效）；仅当服务器以 `CHAT_LEGACY_ADOPT=1` 启动时，凭旧 token 一次性认领（`POST /api/legacy/adopt`）铸发新凭据。
- **验收**：`python tests/basic/verify_basic.py --profile vue|vm`（自管隔离门，Vue 8/8、VM 4/4）+ `python tests/basic/verify_identity.py`（认证/隔离/迁移/负控，41 断言）。

框架前置已解除：安全随机原语由 auto-lang 交付（Plan 907 `a2r_std::rand::secure_hex`，OS CSPRNG），CLI 消费修复见 auto-man `55c98c7`；均按各自 owner 仓规约落地。AutoOS 组合 pin 不在本轮范围。

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

双端验收入口（CHAT-002 自管隔离门，无需外部预启动服务）：
`python tests/basic/verify_basic.py --profile vue` / `--profile vm`（准备/启动/PID 归属全自动），
`python tests/basic/verify_identity.py`（认证/隔离/迁移/负控 41 断言）。
证据 JSON 落 `D:/autostack/plan-artifacts/plan-002/`（本地，不入库）。
不向真实用户库运行测试或 reset（`CHAT_DATA_DIR` 覆盖；迁移与 adopt 仅作用于被测库）。

## 计划与开发

[路线图](docs/roadmap-v0.6.md) · [身份交付002](docs/plans/archived/002-standalone-identity-and-isolation.md) · [重开消息修复003](docs/plans/003-session-message-intent-identity.md) · [AutoOS基础总表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)

开发、计划与顺序复审使用 `D:/autostack/auto-chat` 独立 clone 的 main。CHAT-003由AutoOS PLAN-054真实验收反例触发，实施和复审顺序使用本clone；交付后由统一集成计划登记精确组合版本。Linux 等发行版 Nix＋COSMIC 基础；跨应用通讯另排。

## 来源与组合

来源提交与文件 hash 见 `SOURCE-IMPORT.json`；历史 `source-sync` 保留来源基线。AutoOS 组合目录为 [apps/auto-chat](https://github.com/auto-stack/auto-os/tree/main/apps/auto-chat)，其 pin 可能落后本仓，不作为默认开发目录。旧 Demo 目录仅属历史。

## 主题（auto-os/PLAN-056 接入）

本产品已接入 AutoUI **官方主题包**正式消费面（2026-11-03，PLAN-056 T-02）：

- `vendor/themes` 为 UI 管理渠道发布的固定版本快照（`themes` 0.2.0，内容
  digest `9fa07742dc68aa5377ae06cb2d966386002063f184c515b6c5dddf8a6bef838e`），
  经 `pac.at` `dep themes` 消费；快照不可二次编辑、非第二权威源。
- 主合同在 **auto-os/PLAN-056**：本产品 pac 无 `theme` 键 = **follow 宿主**；
  `src/front/app.at` `design { theme: "Auto", mode: "light" }` 为独立默认腿
  ——本产品无 dark_mode 位（认证/会话/凭据隔离业务不含外观状态），静态
  light 保现默认语义；`use themes.themes: Auto` 注册收集链（C-11 合同）。
  Rust secure_hex 身份/凭据隔离原样。
