# chat 基本能力规范（CHAT-002 修订）

状态：CHAT-001 首版经 CHAT-002 凭据/隔离修订（SD-01），本文件为 chat 应用的 canonical 基本能力规范。
来源：docs/plans/archived/001-real-conversations.md（首版）与
docs/plans/archived/002-standalone-identity-and-isolation.md（本修订）；实现与验收证据见各计划 §9。
边界：本规范只声明已验证能力；未列出的能力（AI 对话、联邦、多端同步、端到端加密、
群管理、音视频、Linux 适配）不受支持，亦不构成承诺。

## 1. 产品定位与用户任务

chat 是真实人与人聊天应用：沿用联系人界面，两个独立客户端以各自身份通过真实通道
互发文字消息。支持的准确用户任务：

- U-1 登录：以名字 + 恢复凭据（secret）登录；注册时服务器铸发 256-bit
  secret 并一次性展示；同名不再授予身份（凭据错误一律拒绝）。
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

- Identity：`{id "u-<seq>", name（唯一）, avatar（按 id 确定性 emoji）, token（会话，
  secure_hex(32)，单活跃、重登轮换、退出清空）, created_sec, last_seen_sec,
  secret（256-bit 恢复凭据，secure_hex(32)）, status（active/legacy）,
  legacy_token（迁移期旧 token，仅供一次性受控恢复）}`。
- Conversation：`{id "cv-<loId>-<hiId>"（按双方 id 数值序稳定派生）, user_a, user_b,
  created_sec}`——恰好两个参与者。
- Message：`{id（服务器自增）, conversation_id, sender_id, sender（服务器自身份表填充）,
  text, created_sec, client_msg_id}`；`UNIQUE(conversation_id, client_msg_id)` 保证重试幂等。
- Read：`(conversation_id, reader_id) → last_read_sec`。
- 存储层：SQLite（WAL + busy_timeout=3000，每操作独立连接，单写者事务
  BEGIN IMMEDIATE/COMMIT/ROLLBACK，绝无部分状态）；数据目录
  `CHAT_DATA_DIR` env → 否则 `%APPDATA%/auto-chat/data` 等平台回退。

## 3. API 契约（v3，CHAT-002 凭据模型，全部实测）

| 端点 | 方法 | 语义 |
|---|---|---|
| /api/register | POST | `{name}` → `RegisterResult{ok,err,id,name,avatar,secret,token}`；铸发 256-bit secret（一次性交付），同名拒绝 name-taken |
| /api/login | POST | `{name, secret}` → `LoginResult{ok,err,id,name,avatar,token}`；精确匹配；签发新会话 token 并撤销旧会话；失败一律 unauthorized |
| /api/logout | POST | `{token}` 撤销本会话（服务端失效） |
| /api/legacy/adopt | POST | `{name, legacy_token}` → `AdoptResult{ok,err,secret}`；仅 `CHAT_LEGACY_ADOPT=1` 启动时开放，一次性核验旧 token 铸发新凭据 |
| /api/identities | GET | `[]Identity`（公开字段；online = 15s 内心跳；不含 secret/token） |
| /api/heartbeat | POST | `{token}` 刷新在线 |
| /api/contacts?token= | GET | 调用者视角会话摘要（对端/最后消息/相对时间/未读；按最后消息时间降序） |
| /api/conversations/open | POST | `{token, peer_id}` 幂等开会话 → `Conversation` |
| /api/messages | GET | `?token=&conversation_id=` 当前会话全量历史（参与者校验；`client_msg_id` 只回给发送者本人，他人置空） |
| /api/messages | POST | `{token, conversation_id, text, client_msg_id}` → `SendResult`；成功落库，对端经轮询收取 |
| /api/typing | POST | `{name, token}`（校验保留；SSE 移除后无广播面） |
| /api/read | POST | `{token, conversation_id}` 标记已读 |
| /api/test/reset | POST | 仅 `CHAT_TEST_MODE=1` 生效；普通模式空操作 |

已退役：`GET /api/me?nonce=`（nonce 认领）、pending_login 表、`/api/stream`
SSE 订阅及其全部广播（单全局总线会把私聊载荷投给任意连接——2026-10-31 实测
匿名与第三身份均收到私聊正文；送达改已鉴权轮询后事件面整体移除）。

访问控制：发送者归属只来自 token 注册表（token 随响应交付，请求体/query 携带——
前端双轨均无自定义 header 能力，见 §5）；无效/缺失 token 的读写一律拒绝（空结果或
ok:false 错误形状）；非会话参与者读写被拒；凭据（secret/token）不得出现在对端
可见的消息元数据中。

## 4. 客户端合同（双轨一致行为）

- 登录屏：名字 + 恢复凭据输入；「登录」恢复既有身份，「注册新身份」铸发并
  一次性展示 secret（琥珀色横幅，确认已保存后进入）；Header「退出」撤销会话。
- Vue 轨：`auto run`（前端 :17822 + 后端 :17823，或 CLI 旗标自定义端口）；两个
  独立浏览器上下文各自登录即两个客户端；送达经 1s RefreshTick 鉴权轮询。
- VM 轨：`auto run -r vm` + `AUTO_REUSE_BACKEND=1 AUTO_HTTP_PORT=<P>
  AUTO_HTTP_BASE=http://127.0.0.1:<P>` 复用外部后端；送达同为 1s 轮询；
  功能与 Vue 等价（四断言验收 A 登录/B 会话/C 送达/D 发送）。
- 发送状态机与重试幂等不变；client_msg_id 只由序号+本端公开 id 构成。
- 发送状态机：pending（sending/failed，客户端可视）→ 服务器落库即"已确认"；
  未确认（发送中/失败）消息不跨客户端重启保留（重开后重发）。
- 时间显示为相对时间（服务器/客户端同钟生成，免时区合同）；精确时序以 created_sec
  （epoch 秒）为准。

## 5. 已知边界与框架缺口（非本应用缺陷，owner 在框架仓）

1. 前端 `Http.*` 无自定义 header：GET 端点 token 走 query；owner auto-ui ts_adapter /
   auto-lang stdlib `auto.http`；关闭条件：Http 支持显式 header 后迁移 Authorization。
2. ~~SSE 单总线全员广播~~（CHAT-002 关闭）：公开流已整体移除，送达=已鉴权按会话
   轮询；若未来恢复定向流，必须按连接鉴权后才可承载私聊载荷。
3. VM 轨 `use back.api` 不可链接（P-15 变体）：store 走裸 Http；owner auto-lang。
4. VM/iced 渲染：空文本节点、`bg-x/10` 形 slash 类、方括号任意类触发容器布局崩溃
   （chat-001 实测）；VM 轨会话列表条目暂以联系人按钮承担切换。
5. ~~`auto run` 120s 就绪门 vs 冷构建~~（CHAT-002 关闭）：verify_basic 自管门
   有界准备（≤300s 分类失败）；交互开发仍建议预热。
6. 凭据面边界见 standalone-runtime-and-identity.md §5（明文存储/常时比较/
   GET query token/单活跃会话）。

## 6. 验收入口（永久回放）

- 双端功能门（自管隔离门，无需外部预启动服务）：`python tests/basic/verify_basic.py
  --profile vue|vm`（Playwright T1–T8 / AutoUI MCP A–D；自管准备+随机端口+隔离
  CHAT_DATA_DIR+PID 归属，仅收割本次子树）。
- 认证/隔离/迁移门：`python tests/basic/verify_identity.py`（C-02/03/04/05，
  45+2 断言，含放行型 stub 负控）。
- 证据 JSON 落 `D:/autostack/plan-artifacts/plan-002/`（本地，不入库）。
- 交付记录：docs/plans/archived/002-standalone-identity-and-isolation.md §9。
