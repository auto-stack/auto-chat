# auto-chat

人与人聊天，使用 AutoLang / AutoUI 开发。更新：2026-10-31。

## 当前能力与边界

[CHAT-001](docs/plans/archived/001-real-conversations.md) 已交付归档：联系人、一对一文字收发、会话隔离、失败重发、SQLite 历史与重开；原验收 Vue 8/8、VM 4/4。现实现合同见[基本能力规范](docs/specs/chat/basic-capabilities.md)。

当前名字登录不是可靠的身份认证，旧 token 可预测；SSE 单总线会把消息载荷送到非参与连接。仅按已声明的本机/可信测试范围理解旧结果，不能据 UI 隐藏声明私聊隔离已完成。

后续 [CHAT-002：独立启动、身份凭据与会话数据隔离](docs/plans/002-standalone-identity-and-isolation.md) 为 drafting/r1、0/9，**尚未实施**。优先复用现有认证/随机能力及鉴权轮询，只有服务器可定向隔离时才保留私密 SSE；补齐独立原生启动、受控旧库迁移和真实三身份反例。

## 运行与验证

安装匹配版本的 auto CLI，仓根执行 `auto run`（Vue，前端17822、Rust后端17823）。共享 StyleKit 位于固定的 `vendor/stylekit`。

旧版原生验收需先有本 app 后端，再在 PowerShell 配置后运行：

```powershell
$env:AUTO_REUSE_BACKEND = '1'
$env:AUTO_HTTP_PORT = '17823'
$env:AUTO_HTTP_BASE = 'http://127.0.0.1:17823'
auto run -r vm
```

这项手工后端依赖和冷构建就绪问题由002接续，当前不承诺全新环境一次命令即完成。数据目录使用 `CHAT_DATA_DIR` 覆盖；不要对真实用户库运行测试或 reset。

现有双端入口：`python tests/basic/verify_basic.py --profile vue` / `--profile vm`。它依赖事先准备的隔离服务；旧 reset 返回200不充分证明测试模式，002将补自管PID/数据根/模式校验。新增认证门在002实施后才可运行。

## 计划与开发

[路线图](docs/roadmap-v0.6.md) · [当前后续计划002](docs/plans/002-standalone-identity-and-isolation.md) · [AutoOS基础总表](https://github.com/auto-stack/auto-os/blob/main/docs/plans/b-apps-basic-capabilities.md)

开发、计划与顺序复审使用 `D:/autostack/auto-chat` 独立 clone 的 main。当前只准备计划/README/roadmap并推送；不实现、不更新 AutoOS 子模块，后续由统一集成计划登记精确交付版本。Linux 等发行版 Nix＋COSMIC 基础；跨应用通讯另排。

## 来源与组合

来源提交与文件 hash 见 `SOURCE-IMPORT.json`；历史 `source-sync` 保留来源基线。AutoOS 组合目录为 [apps/auto-chat](https://github.com/auto-stack/auto-os/tree/main/apps/auto-chat)，其 pin 可能落后本仓，不作为默认开发目录。旧 Demo 目录仅属历史。
