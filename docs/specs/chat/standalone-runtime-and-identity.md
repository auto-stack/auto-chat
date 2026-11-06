# chat 独立运行与身份凭据规范（CHAT-002 交付）

状态：随 CHAT-002 复审通过落地，本文件为 chat 独立运行与身份凭据的 canonical 规范。
来源：docs/plans/archived/002-standalone-identity-and-isolation.md（SD-02）；实现与验收证据见该计划 §9。
边界：只声明已验证能力。群聊、音视频、AI、端到端加密、公网部署、OS 集成、Linux 不在范围内。

## 1. 身份与凭据（服务器权威）

- **注册**：`POST /api/register {name}` → 服务器铸造 256-bit 恢复凭据
  （`secure_hex(32)`，64 位小写 hex）与会话 token，随本响应一次性交付
  `{ok,err,id,name,avatar,secret,token}`；同名（含 legacy）拒绝 `name-taken`。
  secret 只出现这一次（UI 一次性横幅），不入广播/日志/URL。
- **登录/恢复**：`POST /api/login {name, secret}` → 服务端精确匹配；
  `status='active'` 才可登录；成功签发新会话 token 并撤销旧会话（单活跃会话）；
  失败一律 `unauthorized`（不区分未注册/错凭据，防枚举）。
- **退出**：`POST /api/logout {token}` 服务端撤销；客户端丢弃本地副本。
- **凭据来源**：`a2r_std::rand::secure_hex`（auto-lang Plan 907，OS CSPRNG：
  Windows ProcessPrng / Unix getrandom(2)）。禁止以 `uuid()`（epoch 纳秒）、
  SQLite `randomblob()`（bundled build Windows 种子仅时间+PID）充当凭据熵源。
- **消息元数据**：`client_msg_id` 只由客户端序号+本端公开 id 构成，绝不含
  token/secret；服务器只把 `client_msg_id` 回给发送者本人（`message_rows`
  CASE 擦除，他人一律空串）——凭据不得出现在对端可见的任何字节面。

## 2. 旧库受控迁移（v1 → v2）

- 触发：首个鉴权调用前 `identities_v2_ready()`（PRAGMA table_info 检测 secret 列）。
- 顺序：`VACUUM INTO` 一致性备份（`chat.db.pre-v2-<ts>.bak`）→ 单事务
  `ALTER TABLE` 补 `secret/status/legacy_token` 列；备份失败即中止零写入。
- legacy 锁定：既有身份全部 `status='legacy'`，旧弱 token 移入 `legacy_token`
  后 `token` 清空（旧 token 不再通行任何鉴权）。
- 受控恢复：仅当服务器以 `CHAT_LEGACY_ADOPT=1` 启动时，
  `POST /api/legacy/adopt {name, legacy_token}` 一次性核验旧 token →
  铸发新 secret 并激活（legacy_token 随即清除）。env 未开恒拒绝 `adopt-disabled`，
  拒绝/取消路径零写入。

## 3. 独立运行与验收 profile

- 首个受验部署 profile：本机回环后端 + 独立客户端；端口由
  `AUTO_HTTP_PORT`/`AUTO_FRONT_PORT` 驱动（`auto run --back-port/--front-port`）。
- 验收自管隔离门（无需外部预启动服务）：有界准备（缺生成物时 `auto build`
  ≤300s / `cargo build -p auto-chat-back` ≤300s）→ 随机空闲端口 → 隔离
  `CHAT_DATA_DIR` → 端口→PID 归属断言 → 只读就绪探针（绝不向既有服务发 reset）
  → 仅收割本次子树。
- 入口：`python tests/basic/verify_basic.py --profile vue|vm`（双端功能；
  Vue 8 用例 / VM 4 断言）+ `python tests/basic/verify_identity.py`
  （C-02 身份 15 / C-03 隔离 11 / C-04 迁移 18 / C-05 负控 2，共 45+2 断言；
  C-05 用放行型 stub 证明门可红）。证据 JSON 落本地 plan-artifacts，不入库。
- 冷准备有界：就绪探针只读；失败分类 build-failed/bind-failed/crash/ready-timeout。

## 4. 交付时依赖版本（证据）

| 组件 | 版本 |
|---|---|
| auto-lang | `eda930b0`（Plan 907 `9381e0746` 归档 `6ee01e0a6` + riders `ed38cf973`/`eda930b09`） |
| auto-man | `55c98c7`（CLI 消费修复；工具链二进制随之重建） |
| auto-web | `ec9c4ba`（被引生成器文件与本计划 §4 记录逐字一致） |
| auto-ui | `6ab7f2d`（HEAD 后续 docs-only 前进不触代码面） |
| rustc/cargo | 1.98.0；rusqlite 0.30 / libsqlite3-sys 0.27（bundled SQLite） |

## 5. 已知边界（如实声明）

1. GET 端点经 query 携带 token（框架无自定义 header 能力，CHAT-001 已记录；
   生成后端不打印请求行，本机回环内可接受）；关闭条件同 001 §5.1。
2. secret/token 按 bearer 模型明文存 SQLite（与 001 token 信任面一致；
   DB 文件泄露即凭据泄露）。常时比较原语不可用（回环 256-bit 随机值下
   时序泄露不可操作化），已记录为局限。
3. 单活跃会话/身份：同身份第二处登录使前一会话失效（设计行为）。
4. VM 轨 `auto.random` natives 为时间种子 Xorshift（auto-lang 侧已知），
   仅用于非凭据场景；后端轨凭据一律 `rand.secure_hex`。
5. 送达粒度为 1s 轮询（双轨一致）；typing/在线外观信号随 SSE 移除而精简。

## 6. 消息意图跨会话身份（CHAT-003）

成功注册或恢复登录的响应新增 `send_nonce`，由后端独立调用既有
`rand.secure_hex(32)` 生成。它是公开的新意图编号前缀，不是登录能力，
不由secret/token派生。随机生成失败在仓储操作前返回entropy-failed；
认证失败不交付前缀。旧客户端可忽略新增响应字段，SQLite无结构迁移。

客户端用send_nonce＋当前会话序号＋身份ID生成新消息client_msg_id，成功登录
后赋新前缀并从零计数，退出清前缀。重开后的首条新消息必须新增；失败重试
仍复用pending中的原编号，服务器既有UNIQUE/参与者校验保持。同身份新登录
仍撤销旧token。连接缺少send_nonce的旧后端时保留注册凭据展示，显示服务版本
不兼容提示且不提供发送输入框，不能静默复用旧编号。

永久入口 `tests/smoke.spec.ts` T9/T10，以及显式连接自有隔离服务的
`tests/basic/verify_session_intents.py`；录屏、trace和失败截图默认关闭，避免
保存真实输入的恢复凭据。Playwright报告/结果由CHAT_TEST_ARTIFACTS选择仓外
目录，默认D:/autostack/plan-artifacts/auto-chat-tests。
