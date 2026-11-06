---
plan_id: CHAT-003
status: executing
feature_name: 重开后新消息与失败重试编号隔离
author: [Codex]
created_at: 2026-11-06
updated_at: 2026-11-06
plan_revision: 1
current_step: 1
total_steps: 4
base_branch: main
base_commit: 378a7f2fb99eb2f8954f13ec73ae2d4346ec20da
supersedes_spec_components: [docs/specs/chat/standalone-runtime-and-identity.md]
new_spec_components: []
touched_goals: []
---

# CHAT-003：重开后新消息与失败重试编号隔离

## 0. 变更摘要

OS054真实原生双端互发后，关闭重开甲、恢复登录、再发送不同正文，数据库仍只有两条：新消息重用了cm-0-u-2。CHAT-002归档不重开，本计划补齐既有新意图与重试的生命周期区分。

## 1. 目标

新登录客户端从零计数也不与旧消息编号碰撞；失败重试继续使用同一编号，服务端UNIQUE与权限校验不变。Vue与原生真实关闭重开继续发送；不把身份/token放入公开消息元数据。

## 2. 架构方案

使用独立D:/autostack/auto-chat main，一app一个写入者；OS054授权补必要app前置并最终交付，包含本有界修复/检查/提交/push/组合消费。无新worktree、链接、服务supervisor或认证模式；只改纯.at。认证结果新增公开send_nonce字段，后端用既有rand.secure_hex(32)独立抽取，绝不由secret/token派生。普通登录/注册前若随机失败，返回ok=false具名错误且不调用仓储写入。成功时新前缀+当前序号+身份ID构成client_msg_id；前端登录/注册赋新前缀并重置序号，退出清前缀。该前缀不是授权能力，读写仍由token及参与者关系裁决。

## 3. 技术栈

现有api.at→db.at→repository.at/SQLite，既有Rust HTTP服务、Vue与iced。公共UI060bcacacf7补回调发射，是原生消费前置，不在本app内改生成代码。

## 4. 需求与证据

源378a7f2；src/front/chat_store.at SendText拼cm-seq-my_id，send_seq仅实例内。实际反例native-chat-reopen-probe-r152.json在plan054/t04，已接受控制甲乙两条可读且发送者正确。目标同原054 AC03；原始截图/日志仅plan-artifacts/plan-003，父消费证据保留054，不入Git。依赖根显式OS054组，保留旧库，无迁移/reset真实用户数据。

## 5. 详细设计与规范增量

register/login响应分别新增send_nonce str，不删除旧字段；旧客户端可忽略新字段。新客户端缺前缀时不发送新意图，避免连接旧后端时静默复用编号；显示具名兼容错误。重试沿pending.client_msg_id，不生成新key。随机失败在仓储之前，数据库无身份/token变化。对同一消息的retry幂等，不宣称无限计数或跨版本新认证兼容。Spec记录当前会话前缀、零计数重开和旧后端拒绝。

## 6. 验证设计

| ID | 路径/不变量 | 输入与区分oracle | owner |
|---|---|---|---|
| C01 | 生成Rust后端实际认证响应 | 注册与同身份恢复两次，独立send_nonce不同、64hex、不等于secret/token；失败凭据无有效身份响应 | work |
| C02 | 真UI新意图与retry | Vue真实界面两身份发信→重载/凭据登录→不同正文发送，数据库新增恰一条；断网retry原key不多写，沿既有失败流程 | work |
| C03 | 原生指针+键盘+共享Rust | 同上新会话序号0仍新增，历史可读；甲乙归属和C读写拒绝保持 | work/OS054 |
| C04 | 兼容与失败 | 无send_nonce应答不发送新消息且可见错误；真实旧编号碰撞反例为red，不删除旧消息使测试绿 | work |

实施/内部检查/最终app artifact复审顺序同clone；同上下文复审须明确局限，不冒充OS054要求的独立最终复审。代码冻结后复审绑定修订与提交；通过后push、组合pin消费，清理仅本计划独占证据/输出，父验收所需建立具名hold。

## 7. 验收标准

- AC01：成功注册/登录返回独立CSPRNG公开前缀；随机失败不得先修改仓储。
- AC02：两端真实重开恢复后新消息新增一次，retry保留原编号与幂等。
- AC03：C隔离/无token泄漏/旧历史不变；旧后端兼容错误可见。
- AC04：Spec、README、修订绑定复审、push与OS消费可追溯。

## 8. 任务清单

- [x] T00(work)：纯.at后端前缀与前端新意图/缺前缀拒绝，永久复现测试。实际C01 8断言、Vue T5/T9/T10 3通过，原生和最终artifact审查仍待T01/T02。
- [ ] T01(work)：C01..04实际双端/数据库控制，Spec更新，冻结提交。
- [ ] T02(review)：绑定当前修订/提交的最终artifact复审，限制作实声明。
- [ ] T03(merge)：push、归档、消费hold与清理回执，OS054更新固定pin。

## 9. 复审记录

- stage: new | plan_id: CHAT-003 | plan_revision: r1 | outcome: pass | next: work/T00
  原生实际red与源码一致；现有CSPRNG在repository成功使用，采用相同Rust生成支持。保持认证/幂等/隔离标准和repo范围。用户完整054目标授权必要前置，未新增用户决策。

## 10. 待决事项

无；原生054整体验收和独立最终复审仍由父计划承担。

- stage: work | plan_id: CHAT-003 | plan_revision: r1 | round: 1 | outcome: T00 passed; native pending | next: work/T01
  .at additive auth response send_nonce independently generated before repository register/login; failed auth clears it; UI assigns new prefix/resetseq, logout clears, missing prefix hides composer and displays compatibility error while retaining registration secret banner. Retry path unchanged. Real generated Rust backend prepare exit0/1m54s. First auto run cold backend exceeded existing120s readiness window; owned children absent afterward, then explicit Cargo preparation completed, retry uses same now-built profile and becomes ready; not treated as a test pass from timeout.
  Owner service17827 PID28972/Vite3414 PID32148 are isolated CHAT_DATA_DIR plan003/data/chat, CHAT_TEST_MODE=1, no legacy mode. C01 permanent Python response contract8assertions pass; first harness incorrectly parsed void logout as JSON, corrected without weakening payload assertions. Vue permanent smoke T5 offline/retry, T9 new page/recovery/next message/full reload, T10 response missing nonce all3passed/8.7s, session-intents-playwright.log. Windows .cmd grep quoting rejected before tests; final uses direct Node Playwright CLI, not a hidden skip. Playwright artifacts are outside checkout; trace/video/failure screenshot disabled to avoid credentials. No native task or app delivery/push claimed.
