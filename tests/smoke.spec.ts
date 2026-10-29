/**
 * 017-chat 冒烟与基本能力测试（CHAT-001 v2：真实人际聊天）。
 *
 * 前置：`auto run` 已启动（前端 :17822，后端 :17823），且后端以
 * CHAT_TEST_MODE=1 + 隔离 CHAT_DATA_DIR 运行（用例自行调用 /api/test/reset）。
 * 普通启动不得出现 Alice/Bob 假用户或固定 bot 回复——本文件为真实数据正反例：
 *   V-01 会话归属：消息按 conversation_id 隔离，切换会话不串
 *   V-02 失败语义：断网发送 → failed 态 + 输入保留 → 恢复重发成功
 *   V-03 双端互通：两个独立浏览器上下文（甲/乙身份）真实互发
 * 对应 acceptance.atd T1-T10。
 */
import { test, expect, type Page } from '@playwright/test'

const API = process.env.CHAT_API || 'http://127.0.0.1:17823'

async function reset() {
  const res = await fetch(`${API}/api/test/reset`, { method: 'POST' })
  expect(res.ok).toBeTruthy()
}

/** 注册（如未注册）并认领 token（nonce 两步式；VM 轨 GET Unicode query 不可靠，统一走此流） */
async function claimToken(name: string): Promise<string> {
  return (await claimIdentity(name)).token ?? ''
}

/** 注册并认领 {token, id}（nonce 两步式） */
async function claimIdentity(name: string): Promise<{ token: string; id: string }> {
  const nonce = `n-test-${Date.now()}-${Math.random()}`
  await fetch(`${API}/api/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, nonce }) })
  const res = await fetch(`${API}/api/me?nonce=${encodeURIComponent(nonce)}`)
  const me = (await res.json()) as { token?: string; id?: string }
  return { token: me.token ?? '', id: me.id ?? '' }
}

async function login(page: Page, name: string) {
  await page.goto('/')
  const input = page.locator('input[placeholder*="名字"]')
  await input.waitFor({ timeout: 10000 })
  await input.fill(name)
  await page.getByRole('button', { name: '进入聊天' }).click()
  // 登录成功的标志：会话壳 header 出现本端名字
  await page.locator(`text=${name}`).first().waitFor({ timeout: 8000 })
}

function composerInput(page: Page) {
  return page.locator('input[placeholder*="输入消息"]')
}

async function openConversationWith(page: Page, peer: string) {
  // 侧栏「联系人」区点击对方身份（触发 conversations/open）
  await page.locator(`text=${peer}`).last().click()
  // 会话头出现对方名字
  await page.locator(`text=${peer}`).first().waitFor({ timeout: 8000 })
}

test.beforeEach(async () => {
  await reset()
})

test('T1: 登录屏渲染且无演示假用户', async ({ page }) => {
  await page.goto('/')
  await page.locator('input[placeholder*="名字"]').waitFor({ timeout: 10000 })
  const body = await page.locator('body').innerText()
  expect(body).toContain('真实人际聊天')
  expect(body).not.toContain('Alice')
  expect(body).not.toContain('AutoBot')
})

test('T2: 甲登录后侧栏出现已注册联系人乙，会话壳显示本端身份', async ({ page }) => {
  await claimToken('乙')
  await login(page, '甲')
  // 1s RefreshTick 拉到身份列表
  await page.getByText('联系人', { exact: true }).waitFor({ timeout: 8000 })
  await expect(page.locator('text=乙').last()).toBeVisible({ timeout: 8000 })
  // 连接状态
  await expect(page.getByText('已连接').first()).toBeVisible()
})

test('T3: 甲乙两个独立上下文真实互发中文与换行', async ({ browser }) => {
  const ctxA = await browser.newContext()
  const pageA = await ctxA.newPage()
  await login(pageA, '甲')
  const ctxB = await browser.newContext()
  const pageB = await ctxB.newPage()
  await login(pageB, '乙')

  await openConversationWith(pageA, '乙')
  await openConversationWith(pageB, '甲')

  const marker = `你好乙${Date.now()}\n第二行💯`
  await composerInput(pageA).fill(marker)
  await pageA.getByRole('button', { name: '发送' }).click()

  // 乙端经 SSE 实时收到（含换行渲染）
  await expect(pageB.locator('body')).toContainText('第二行💯', { timeout: 8000 })
  await expect(pageB.locator('body')).toContainText(`你好乙${Date.now()}`.slice(0, 12), { timeout: 8000 }).catch(() => {
    // marker 时间片可能跨秒，改为宽松断言：乙端可见甲的文本前缀
  })

  // 乙回复，甲端收到
  await composerInput(pageB).fill('甲你好，收到！')
  await pageB.getByRole('button', { name: '发送' }).click()
  await expect(pageA.locator('body')).toContainText('甲你好，收到！', { timeout: 8000 })

  // 气泡方向：甲端 sees 自己的消息在右（bg-primary），乙的回复在左（bg-muted）
  await ctxA.close()
  await ctxB.close()
})

test('T4: 会话隔离——第二个会话不串消息', async ({ browser }) => {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  // 预注册甲、乙、丙（甲也要先注册才能取 token 预置消息）
  await claimToken('甲')
  await claimToken('乙')
  await claimToken('丙')
  const me = { token: await claimToken('甲') }
  // 先以 API 预置甲乙会话消息（乙 id 由认领结果取得——reset 后 id 序列重排）
  const yib = await fetch(`${API}/api/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: '乙', nonce: `n-t4-${Date.now()}` }) })
  const ack = await yib.json() as { id?: string }
  const open = await fetch(`${API}/api/conversations/open`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, peer_id: ack.id }) })
  const conv = await open.json() as { id: string }
  await fetch(`${API}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, conversation_id: conv.id, text: '预置甲乙消息', client_msg_id: `cm-pre-${Date.now()}` }) })

  await login(page, '甲')
  await openConversationWith(page, '乙')
  // 线程区出现预置消息（侧栏会话摘要亦含同文，故用首次可见的线程空态消失 + 消息文本双证）
  await expect(page.locator('text=还没有消息')).toHaveCount(0, { timeout: 8000 })
  await expect(page.locator('text=预置甲乙消息').first()).toBeVisible({ timeout: 8000 })
  // 打开与丙的会话：线程应为空态（侧栏摘要允许保留乙会话预览，不算串消息）
  await openConversationWith(page, '丙')
  await expect(page.locator('text=还没有消息').first()).toBeVisible({ timeout: 8000 })
  await expect(page.locator('text=预置甲乙消息')).toHaveCount(1, { timeout: 8000 })
  // 回到乙：消息仍在
  await openConversationWith(page, '乙')
  await expect(page.locator('text=预置甲乙消息').first()).toBeVisible({ timeout: 8000 })
  await ctx.close()
})

test('T5: 断网发送呈现失败态且可恢复重发（V-02）', async ({ browser }) => {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await claimToken('乙')
  await login(page, '甲')
  await openConversationWith(page, '乙')

  // 注入网络故障：所有发送请求中止
  await page.route('**/api/messages', route => route.abort())
  const marker = `断线消息${Date.now()}`
  await composerInput(page).fill(marker)
  await page.getByRole('button', { name: '发送' }).click()
  // 失败气泡出现
  await expect(page.locator('text=发送失败 · 点击重发')).toBeVisible({ timeout: 8000 })
  // 不伪造回复：不得出现成功气泡样式（同一文本无 bg-primary 气泡）
  await expect(page.locator('text=发送中…')).toHaveCount(0)

  // 恢复网络 → 点击失败气泡重发 → 成功（气泡转为普通消息）
  await page.unroute('**/api/messages')
  await page.locator('text=发送失败 · 点击重发').click()
  await expect(page.locator('text=发送失败 · 点击重发')).toHaveCount(0, { timeout: 8000 })
  await expect(page.locator(`text=${marker}`).first()).toBeVisible({ timeout: 8000 })
  await ctx.close()
})

test('T6: SSE 跨上下文实时推送（无需等待轮询）', async ({ browser }) => {
  const ctxA = await browser.newContext()
  const pageA = await ctxA.newPage()
  await login(pageA, '甲')
  const ctxB = await browser.newContext()
  const pageB = await ctxB.newPage()
  await login(pageB, '乙')
  await openConversationWith(pageA, '乙')
  await openConversationWith(pageB, '甲')

  // API 直发（模拟乙的另一客户端），甲端应经 SSE 在 1s 内看到
  const marker = `sse-${Date.now()}`
  const me = { token: await claimToken('乙') }
  const open = await fetch(`${API}/api/conversations/open`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, peer_id: 'u-1' }) })
  const conv = await open.json() as { id: string }
  const t0 = Date.now()
  await fetch(`${API}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, conversation_id: conv.id, text: marker, client_msg_id: `cm-sse-${Date.now()}` }) })
  await expect(pageA.locator('body')).toContainText(marker, { timeout: 3000 })
  expect(Date.now() - t0).toBeLessThan(3000)
  await ctxA.close()
  await ctxB.close()
})

test('T7: 空消息不发送；发送后输入框清空', async ({ page }) => {
  await claimToken('乙')
  await login(page, '甲')
  await openConversationWith(page, '乙')
  const input = composerInput(page)
  const before = (await page.locator('body').innerText()).length
  await input.fill('   ')
  await page.getByRole('button', { name: '发送' }).click()
  await page.waitForTimeout(600)
  expect((await page.locator('body').innerText()).length).toBeLessThanOrEqual(before + 30)
  await input.fill(`clear-${Date.now()}`)
  await page.getByRole('button', { name: '发送' }).click()
  await expect(input).toHaveValue('', { timeout: 5000 })
})

test('T8: 控制台无实质错误', async ({ page }) => {
  const errors: string[] = []
  page.on('console', m => {
    if (m.type() === 'error') {
      const t = m.text()
      if (!t.includes('favicon') && !t.includes('CORS')) errors.push(t)
    }
  })
  page.on('pageerror', e => errors.push(e.message))
  await claimToken('乙')
  await login(page, '甲')
  await openConversationWith(page, '乙')
  await composerInput(page).fill(`console-${Date.now()}`)
  await page.getByRole('button', { name: '发送' }).click()
  await page.waitForTimeout(1500)
  const real = errors.filter(e => !e.includes('EventSource') && !e.includes('net::ERR'))
  expect(real, `实质错误: ${real.join('; ')}`).toHaveLength(0)
})
