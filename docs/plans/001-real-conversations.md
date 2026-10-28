---
plan_id: CHAT-001
status: drafting
feature_name: real-conversations
author: [Codex]
created_at: 2026-10-29
updated_at: 2026-10-29
plan_revision: 1
current_step: 0
total_steps: 7
supersedes_spec_components: []
new_spec_components: [docs/specs/chat/basic-capabilities.md]
touched_goals: []
---

# CHAT-001：真实会话、消息通道与历史恢复

## 0. 变更摘要

将预置联系人/固定回复演示补为一种经用户确认身份的真实聊天应用。

本轮只起草执行合同：没有实施功能、运行功能验收或将本app升为A类。auto-chat 的基本能力补齐不依赖 auto-os-distro；Linux 支持另等 Nix＋COSMIC 基础完成，增强设计另会话。

## 1. 目标

在确定是人际通信还是AI客户端后，完成真实发送/接收、会话隔离、明确消息状态和历史重开；不把固定回复或全局消息数组当产品。

非目标：在身份未定前不自行选择 Matrix/自研IM/AI供应商。首版不追加联邦、多端同步、端到端加密协议研发、群管理、音视频或Linux适配；若选择外部协议，其不可省略的安全要求仍保留。

## 2. 架构方案

应用逻辑继续纯 `.at`，前端/后端沿 AutoUI 现有结构；本仓为主导仓。应用工作检出固定 `D:/autostack/auto-os/apps/auto-chat`，工作分支 `main`；执行/复审共用此检出，一个写入者。**不新建app外部worktree或clone，不建任何junction/symlink**。框架缺口在实际owner仓另立前置并按其worktree纪律执行，不在app手写Rust、修改生成Rust或绕过公开SDK。

两路线共用稳定 conversation_id/message_id、发送/失败/确认状态与本地历史模型；不同会话不串消息。AI路线需真实provider及独立配置引用、断网/鉴权/取消语义；人际路线需真实两个客户端/身份与受支持通道的收发确认。最终仅实现用户确认路线，不把两个路线同时纳入首版。凭据不硬编码或写进导出/测试证据。

跨仓总表：[B类基本能力总跟踪表](../../../../docs/plans/b-apps-basic-capabilities.md)。源Spec以所属仓 `docs/specs/` 为准；当前没有该app的canonical模块规范，旧根 `SPEC.md`（如有）只是历史Demo观察/再生描述，不能据此宣布真实功能已完成。新规范路径将在实际复审/merge后落地，本轮不写入已实现Spec。

## 3. 技术栈

Auto / AutoUI、当前匹配的AutoLang/AutoUI/AutoMan工具组合、各app已有widget/store/API；具体存储与平台接缝由T-01用实际源码和探针确认。Vue / VM 两端均需真实任务验收，不因某一后端不通就删掉原任务；如必须显式指定 server=vm 等启动profile，应先验证并记录到执行入口/README，不能静默换成mock。

## 4. 需求分析与背景调查

授权：用户于2026-10-29要求建立总跟踪表、复用Notes/Reader/Blog现有计划，并为其余B类应用准备基本能力补齐计划。此处授权的是**计划准备和必要的文档/组合版本登记**，不宣称已授权/完成本计划具体功能实现，不推定全量竞品复刻或Linux开发已启动。

冻结的观察基线：`8df3f33b3bfedc123287d4324b5e67ae5b00a724`（在本app `main` fetch origin后ff核对）；执行前重新核对HEAD/pin/WIP并记录变化。主产品统计为27个去重产品，B类9个；AutoJade旧名Jade Garden不重复计数。

db.at 联系人/消息为内存种子，bot_reply按联系人返回固定文本；前端composer先清draft且请求失败反馈不足，尚不能证明真实用户/AI通信。当前没有产品身份裁定和canonical Spec。

已读来源（源码/文档观察，不是本轮实测）：

- `src/back/api.at`：SHA256 `4430a679f76f68edb3698ced0ff9717a8c25fb2e61aa1a0b4d1ac31d3ed35ec2`。
- `src/back/db.at`：SHA256 `decfdb2533f491df3308a4395b665eac81d730d4ba84e12e275330b36cc75deb`。
- `src/front/chat_store.at`：SHA256 `7695e2dac2aad500bb6afa3b60ae8e1e96bac38cf3498715ced4e974f1d7b998`。
- `src/front/composer.at`：SHA256 `514effb15062ac82b908d066d2121d0e82db74b2c4bbabf74e9c6c2fe0f772c4`。
- `tests/smoke.spec.ts`：SHA256 `312b646c6e0da732a1d8de0783a57ee318bbdd6e5cdd6add46569295d7a8b8ad`。
- `tests/acceptance.atd`：SHA256 `26bd0ade7d62fc83041261d1caf1b179231af2a4230ef49f93881578c2de6b73`。

## 5. 详细设计

### 执行入口和依赖

首个就绪任务仅T-01：在上述应用检出核对版本、清单、当前工具链、真实API与测试入口，用隔离数据跑能力探针。输出允许后续实现依赖的接口与不支持项；缺口需具名指向owner/前置计划及关闭条件。不得假造未存在API、跳过基础正确性，或以“将来Linux会解决”替代当前端的基本能力。

T-02..04按下列任务依赖顺序推进；T-05将本节拟议测试做成真实可复现入口，T-06/07保持未来阶段未勾选。合并后只有基础合同的全部必需工作/复审通过且父仓pin指向交付版本，才更新总表分类。发布包/所有Linux发行版不在本计划的成功声明里。

### 规范增量

| delta_id | action | docs/specs target | before/after rule | rationale | AC |
|---|---|---|---|---|---|
| SD-01 | add | `docs/specs/chat/basic-capabilities.md`（新） | Demo/未定义 → 本计划首版用户任务、数据模型和准确支持范围 | 以真实基本能力作为产品准入 | AC-01/02 |
| SD-02 | add | 同上，失败/恢复及交互节 | 未定义 → 保存/输出/失败、重启和两端行为的可验合同 | 防止假成功、旧数据丢失和单端冒充 | AC-03/04 |

根README/历史SPEC在实现落地时反链canonical目标，保留历史来源、不覆盖未经审查的旧约定；本计划不在draft阶段修改canonical知识或ledger。

## 6. 测试设计

本轮没有执行下列功能测试。先以真实应用入口和真实文件/服务为准，既有脚本若只验证演示数据，需要补有辨别力的真实数据正反例；禁止仅把UI文案变绿或用相同生产函数生成期望值。

| case_id | AC/task与责任 | 输入/设置 | 实际入口 | 必须观察的结果 |
|---|---|---|---|---|
| V-01 | T-01..05 / AC-01..04；由T-05制作永久回放 | 两会话相同显示名、延迟返回与切会话 | 真实通道→存储→UI | 消息按conversation_id归属，不因当前选中变化写错会话。 |
| V-02 | T-01..05 / AC-01..04；由T-05制作永久回放 | 发送超时/断网/确认后重试/重启 | 公开发送与重试入口 | 失败不伪造回复，输入/待处理状态可恢复；已确认消息不重复落库。 |
| V-03 | T-01..05 / AC-01..04；由T-05制作永久回放 | AI真实provider一轮；或两个独立人际客户端 | 所选路线实际会话入口 | 真实交互可追溯，fixture bot仅显式测试模式，不计功能通过。 |

测试隔离：所有文件/数据库/服务均使用临时用户数据目录及明确测试端口，不接触真实用户数据；占用端口/不可写/损坏时明确失败。多个实例/取消/退出与恢复按本计划声明范围验证。资源预算若需限制，T-01明确单位/语义/拒绝或截断结果并在dependent实现前冻结；没有提出上限不等于无限规模承诺，不以隐藏硬上限代替验收。

可复现入口（**均由T-05新增/接通**）：`python tests/basic/verify_basic.py --profile vue`、`python tests/basic/verify_basic.py --profile vm`。入口应实际调用应用后端与两端UI，记录源码/工具/依赖版本、fixture hash及运行结果；不得仅调内存helper替代。按可用工具复用现有Playwright或VM MCP/autoui-verifier驱动。T-01记录真实启动命令、数据env、端口与适用CLI参数；两端都要证实实际支持的用户任务。

角色：本轮仅起草，没有派执行/复审agent。实现与最终复审按四技能分阶段；无明确独立上下文时如实声明并从工件重建，不能自称独立或擅自创建新会话/agent。只改app不触auto-lang crates时禁止跑其cargo t/docs_gen；框架前置按owner自己的门档验证。

## 7. 验收标准

| ID | owner_stage | observable / verification |
|---|---|---|
| AC-01 | work | 身份与可行性：用户确认一种首版身份与最小通道profile，T-01真实路径探针成功；没有确认不得开展依赖实现。 |
| AC-02 | work | 真实发送接收：AI路线使用实际provider（受控服务仅验证错误分支，至少一个真实交互）；人际路线两个独立客户端真实收发。最终按所选路线验，不能用mock回复替代。 |
| AC-03 | work | 隔离与持久化：至少两个会话不串消息；中文/换行历史和发送状态在退出重开后按合同恢复；已确认消息重试不重复落库。 |
| AC-04 | work | 失败与双端：超时/断网/无效凭据/存储失败有真实状态且编辑可恢复；Vue/VM各完成一次真实交互和历史重开。凭据不进入日志/导出。 |
| AC-05 | review | 冻结已提交实现与依赖，逐个重验AC-01..04和独立反例；核对SD-01/02与范围、实际证据，输出明确review结论；未闭项不可忽略。 |
| AC-06 | merge | 通过对应最终门后交付main并推送，父仓gitlink和组合验证可追溯；canonical/ledger/归档收尾完成，app显式detached；总表有证据地标A，A类Linux仍等待发行版前置。 |

## 8. 执行步骤

- [ ] T-01（owner_stage=work；依赖 无；AC-01..04）：基线与全路径探针：T-01先完成用户身份选择记录（已提出异步问题，未提交的预选不是确认）；给出唯一最小连接profile、既有服务可复用范围与真实端到端探针。身份未确认，只可调查和形成决策材料，不实施某一路线。通道与凭据缺项须具名，不用固定回复占位后标通过。沿用17822/17823，先核既有连接/流API。 输出新文件 `docs/plans/evidence/001/capability-decision.md`，记录可用API、版本/资源边界、缺项owner和最小闭环。
- [ ] T-02（owner_stage=work；依赖 T-01；AC-01..04）：会话模型与存储：仅在身份确认后新增会话仓储/版本化历史（拟议 src/back/conversations.at / repository.at）；conversation_id/message_id稳定，不共享一张无会话归属列表。
- [ ] T-03（owner_stage=work；依赖 T-02；AC-01..04）：真实通道与状态：按T-01唯一选择接真实人际收发或AI响应；发送/重试/失败/确认状态真实，重试不重复插入已确认消息；明确生命周期与退出恢复。
- [ ] T-04（owner_stage=work；依赖 T-03；AC-01..04）：前端真实会话：chat_store.at/composer.at以稳定身份路由，发送失败保留或可恢复输入；普通启动不出现Alice/Bob假用户或固定bot回复，测试fixture显式隔离。
- [ ] T-05（owner_stage=work；依赖 T-02..04；AC-01..04）：完成独立数据/失败回放和两端真实UI验收，新建 `tests/basic/verify_basic.py` 调度入口（可复用既有脚本），同时保存命令/输入hash/真实结果与原始失败；准备 canonical Spec 增量，提交实现，转 execution_done。
- [ ] T-06（owner_stage=review；依赖 T-05；AC-05）：在同一app检出暂停实现，按冻结提交、真实数据和独立反例最终复审；核对Spec增量与双端结果，说明上下文独立性限制；未满足返回修复，不将数据错误降为债务。
- [ ] T-07（owner_stage=merge；依赖 T-06；AC-06）：完成实际提交/推送/父仓gitlink验证，沉淀canonical Spec与derived ledger、归档；刷新总表A/B与证据，app显式detach。Linux仍等待发行版门，不因文档或脚本存在宣布已可用。

## 9. 复审记录

- stage: new | plan_id: CHAT-001 | plan_revision: 1 | outcome: blocked（依赖用户产品身份决策；草案已准备，T-01可继续调查） | next: 用户确认身份后完成T-01决策，再实施依赖任务。
- 本轮核对源码/Spec缺口、历史任务、路径、基线和计划唯一性；未执行实现/功能测试，所有7项任务保持未勾选；通过的是草案结构/相互引用检查，不是产品验收。

## 10. 待澄清事项

待用户确认：人际聊天还是AI对话，以及对应最小连接profile。已提出异步问题；尚未收到答复不默认接受预选。此项阻塞T-02..T-05的路线实现，不阻塞其他五个app的计划准备。
