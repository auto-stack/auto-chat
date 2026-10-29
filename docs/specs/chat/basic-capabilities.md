# chat 基本能力规范（CHAT-001 v1 首版）

状态：CHAT-001 实现随双轨验收落地后，本文件为 chat 应用的 canonical 基本能力规范。
来源：docs/plans/001-real-conversations.md（SD-01/SD-02）；实现与验收证据见该计划 §9。
边界：本规范只声明已验证能力；未列出的能力（AI 对话、联邦、多端同步、端到端加密、
群管理、音视频、Linux 适配）不受支持，亦不构成承诺。

## 1. 产品定位与用户任务

chat 是真实人与人聊天应用：沿用联系人界面，两个独立客户端以各自身份通过真实通道
互发文字消息。支持的准确用户任务：

- U-1 登录：输入名字进入聊天；同名再登录回到同一身份（历史与会话延续）。
- U-2 发起会话：从联系人列表（其他已注册身份）点击发起；会话幂等（重复打开同一对
  身份得到同一会话）。
- U-3 收发消息：发送文本（含中文、换行、emoji）；对方在线时经 SSE 实时收到（Vue 轨），
  否则经 1s 轮询送达（VM 轨）；气泡方向按消息归属（sender_id == 本端 id）派生。
- U-4 会话隔离：消息按会话归属；切换会话不串消息；未参与会话无法读写（服务器校验）。
- U-5 失败处理：发送失败（断网/无效 token/越权）呈现失败态且不伪造回复；文本保留，
  点击失败气泡重发；重试复用同一 client_msg_id，已确认消息不重复落库。
- U-6 历史恢复：消息、身份、token、会话、已读位持久化于 SQLite；应用退出重开后，
  同名登录即恢复全部历史与会话。
- U-7 未读与在线：侧栏显示每会话未读数与对端在线状态（15s 心跳窗口）；打开会话即
  标记已读。

## 2. 数据模型（服务器权威）

- Identity：`{id "u-<seq>", name（唯一）, avatar（按 id 确定性 emoji）, token, created_sec,
  last_seen_sec}`。
- Conversation：`{id "cv-<loId>-<hiId>"（按双方 id 数值序稳定派生）, user_a, user_b,
  created_sec}`——恰好两个参与者。
- Message：`{id（服务器自增）, conversation_id, sender_id, sender（服务器自身份表填充）,
  text, created_sec, client_msg_id}`；`UNIQUE(conversation_id, client_msg_id)` 保证重试幂等。
- Read：`(conversation_id, reader_id) → last_read_sec`。
- 存储层：SQLite（WAL + busy_timeout=3000，每操作独立连接，单写者事务
  BEGIN IMMEDIATE/COMMIT/ROLLBACK，绝无部分状态）；数据目录
  `CHAT_DATA_DIR` env → 否则 `%APPDATA%/auto-chat/data` 等平台回退。

## 3. API 契约（v2，全部实测）

| 端点 | 方法 | 语义 |
|---|---|---|
| /api/login | POST | `{name, nonce}` → `LoginAck{id,name,avatar}` 并广播 NewLoginAck（无 token） |
| /api/me?nonce= | GET | 按 ASCII 一次性 nonce 认领 `MeInfo{id,name,avatar,token}`（token 唯一交付处，不进广播） |
| /api/identities | GET | `[]Identity`（公开字段；online = 15s 内心跳） |
| /api/heartbeat | POST | `{token}` 刷新在线（void，不广播） |
| /api/contacts?token= | GET | 调用者视角会话摘要（对端/最后消息/相对时间/未读；按最后消息时间降序） |
| /api/conversations/open | POST | `{token, peer_id}` 幂等开会话 → `Conversation` |
| /api/messages | GET | `?token=&conversation_id=` 当前会话全量历史（参与者校验） |
| /api/messages | POST | `{token, conversation_id, text, client_msg_id}` → `SendResult`；成功即落库并广播 NewSendResult |
| /api/typing | POST | `{name, token}`；token 校验通过才广播 Typing（codegen 约束：仅首个 str 参数进载荷） |
| /api/read | POST | `{token, conversation_id}` 标记已读 |
| /api/test/reset | POST | 仅 `CHAT_TEST_MODE=1` 生效；普通模式空操作 |
| /api/stream | GET | SSE 订阅（ChatEvent：NewSendResult / NewLoginAck / Typing） |

访问控制：发送者归属只来自 token 注册表（token 经 /api/me 交付，请求体携带——前端
双轨均无自定义 header 能力，见 §5）；无效/缺失 token 的读写一律拒绝（空结果或
ok:false 错误形状）；非会话参与者读写被拒（not-a-participant）。

## 4. 客户端合同（双轨一致行为）

- Vue 轨：`auto run`（前端 :17822 + 后端 :17823）；两个独立浏览器上下文各自登录即
  两个客户端；SSE 实时送达 + 1s 刷新兜底；断线 EventSource 自动重连（2s 退避）。
- VM 轨：`auto run -r vm` + `AUTO_REUSE_BACKEND=1 AUTO_HTTP_PORT=17823
  AUTO_HTTP_BASE=http://127.0.0.1:17823` 复用外部后端；无 SSE 源（框架缺口 P-15），
  送达经 1s 轮询；功能与 Vue 等价（四断言验收 A 登录/B 会话/C 送达/D 发送）。
- 发送状态机：pending（sending/failed，客户端可视）→ 服务器落库即"已确认"；
  未确认（发送中/失败）消息不跨客户端重启保留（重开后重发）。
- 时间显示为相对时间（服务器/客户端同钟生成，免时区合同）；精确时序以 created_sec
  （epoch 秒）为准。

## 5. 已知边界与框架缺口（非本应用缺陷，owner 在框架仓）

1. 前端 `Http.*` 无自定义 header：token 走请求体；owner auto-ui ts_adapter /
   auto-lang stdlib `auto.http`；关闭条件：Http 支持显式 header 后迁移 Authorization。
2. VM 轨无 SSE 源（P-15）：送达退化为轮询；owner auto-ui/auto-lang VM renderer。
3. SSE 单总线全员广播：跨会话消息文本流经所有连接（UI 层过滤 + 写入侧强校验）；
   owner auto-lang auto-api-gen；关闭条件：流端点按通道路由。
4. VM 轨 `use back.api` 不可链接（P-15 变体）：store 走裸 Http；owner auto-lang。
5. VM/iced 渲染：空文本节点、`bg-x/10` 形slash 类、方括号任意类触发容器布局崩溃
   （chat-001 实测）；VM 轨会话列表条目暂以联系人按钮承担切换。
6. `auto run` 后端 120s 就绪门限 vs 冷构建耗时：首次构建需
   `cargo build -p auto-chat-back` 预热（体验问题，非功能缺陷）。

## 6. 验收入口（永久回放）

- 汇总调度：`python tests/basic/verify_basic.py --profile vue|vm`（前置：被测后端以
  `CHAT_TEST_MODE=1` + 隔离 `CHAT_DATA_DIR` 运行；脚本拒绝在真实数据上验收）。
- Vue 轨：Playwright（tests/smoke.spec.ts，T1–T8，8 用例）。
- VM 轨：AutoUI MCP（tests/basic/vm-basic.mjs，A–D 四断言）。
- 证据：docs/plans/attachments/001/verify-{vue,vm}.json（本地）。
