/**
 * 冒烟与基本能力测试（CHAT-002 凭据模型：注册铸发 secret 一次性展示，
 * 登录=名字+secret 恢复；会话 token 由服务器铸造/撤销）。
 *
 * 前置：verify_basic.py 自管隔离门已启动后端+前端（CHAT_TEST_MODE=1 +
 * 隔离 CHAT_DATA_DIR；用例自行调用 /api/test/reset）。
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

/** CHAT-002：每个用例 reset 后从空白库开始；secret 按名缓存——
 *  首次认领=注册（铸发 secret），后续=凭 secret 登录（拿新会话 token）。 */
const secrets = new Map<string, string>()

async function claimIdentity(name: string): Promise<{ token: string; id: string }> {
  const post = (path: string, body: unknown) =>
    fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  let token = ''
  let id = ''
  const known = secrets.get(name)
  if (known) {
    const r = await post('/api/login', { name, secret: known })
    const j = (await r.json()) as { ok?: boolean; token?: string; id?: string }
    if (!j.ok) throw new Error(`login ${name} failed`)
    token = j.token ?? ''
    id = j.id ?? ''
  } else {
    const r = await post('/api/register', { name })
    const j = (await r.json()) as { ok?: boolean; secret?: string; token?: string; id?: string }
    if (!j.ok) throw new Error(`register ${name} failed`)
    secrets.set(name, j.secret ?? '')
    token = j.token ?? ''
    id = j.id ?? ''
  }
  return { token, id }
}

/** 兼容旧命名的 token 认领 */
async function claimToken(name: string): Promise<string> {
  return (await claimIdentity(name)).token
}

async function peerIdByName(name: string): Promise<string> {
  const ids = (await (await fetch(`${API}/api/identities`)).json()) as { id: string; name: string }[]
  const hit = ids.find(i => i.name === name)
  return hit ? hit.id : ''
}

/** UI 登录：名字 + 恢复凭据（claimIdentity 已持有该身份的 secret） */
async function login(page: Page, name: string) {
  const { secret } = { secret: secrets.get(name) ?? '' }
  if (!secret) await claimIdentity(name)
  await page.goto('/')
  const input = page.locator('input[placeholder*="名字"]')
  await input.waitFor({ timeout: 10000 })
  await input.fill(name)
  await page.locator('input[placeholder*="恢复凭据"]').fill(secrets.get(name) ?? '')
  await page.getByRole('button', { name: '登录', exact: true }).click()
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
  secrets.clear()
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
  await claimIdentity('乙')
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

  // 乙端经 1s 轮询送达（含换行渲染）
  await expect(pageB.locator('body')).toContainText('第二行💯', { timeout: 8000 })

  // 乙回复，甲端收到
  await composerInput(pageB).fill('甲你好，收到！')
  await pageB.getByRole('button', { name: '发送' }).click()
  await expect(pageA.locator('body')).toContainText('甲你好，收到！', { timeout: 8000 })
  await ctxA.close()
  await ctxB.close()
})

test('T4: 会话隔离——第二个会话不串消息', async ({ browser }) => {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  // 预注册甲、乙、丙；以甲的 token 预置甲乙会话消息
  await claimIdentity('甲')
  await claimIdentity('乙')
  await claimIdentity('丙')
  const me = { token: await claimToken('甲') }
  const yiid = await peerIdByName('乙')
  const open = await fetch(`${API}/api/conversations/open`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, peer_id: yiid }) })
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
  await claimIdentity('乙')
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

test('T6: 跨上下文经鉴权轮询送达（1s RefreshTick）', async ({ browser }) => {
  const ctxA = await browser.newContext()
  const pageA = await ctxA.newPage()
  await login(pageA, '甲')
  const ctxB = await browser.newContext()
  const pageB = await ctxB.newPage()
  await login(pageB, '乙')
  await openConversationWith(pageA, '乙')
  await openConversationWith(pageB, '甲')

  // API 直发（模拟乙的另一客户端），甲端应经轮询在 3s 内看到
  const marker = `poll-${Date.now()}`
  const me = { token: await claimToken('乙') }
  const jiid = await peerIdByName('甲')
  const open = await fetch(`${API}/api/conversations/open`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, peer_id: jiid }) })
  const conv = await open.json() as { id: string }
  const t0 = Date.now()
  await fetch(`${API}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: me.token, conversation_id: conv.id, text: marker, client_msg_id: `cm-poll-${Date.now()}` }) })
  await expect(pageA.locator('body')).toContainText(marker, { timeout: 3000 })
  expect(Date.now() - t0).toBeLessThan(3000)
  await ctxA.close()
  await ctxB.close()
})

test('T7: 空消息不发送；发送后输入框清空', async ({ page }) => {
  await claimIdentity('乙')
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
  await claimIdentity('乙')
  await login(page, '甲')
  await openConversationWith(page, '乙')
  await composerInput(page).fill(`console-${Date.now()}`)
  await page.getByRole('button', { name: '发送' }).click()
  await page.waitForTimeout(1500)
  const real = errors.filter(e => !e.includes('EventSource') && !e.includes('net::ERR'))
  expect(real, `实质错误: ${real.join('; ')}`).toHaveLength(0)
})

// CHAT-003: a new renderer/login starts its local sequence at zero, but it
// must produce a new intent rather than replaying the old cm-0 identity key.
test('T9: 重开恢复后第一条新消息不与旧意图碰撞', async ({ browser }) => {
  await claimIdentity('恢复甲')
  await claimIdentity('恢复乙')
  const ctx = await browser.newContext()
  let page = await ctx.newPage()
  await login(page, '恢复甲')
  await openConversationWith(page, '恢复乙')
  await composerInput(page).fill('重开前第一条54.25')
  const response = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/messages') && r.request().method() === 'POST'),
    page.getByRole('button', { name: '发送', exact: true }).click(),
  ])
  expect((await response[0].json()).ok).toBe(true)
  await expect(page.locator('body')).toContainText('重开前第一条54.25')
  await page.close()
  page = await ctx.newPage()
  await login(page, '恢复甲')
  await openConversationWith(page, '恢复乙')
  await expect(page.locator('body')).toContainText('重开前第一条54.25')
  await composerInput(page).fill('重开后新意图8.125')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.locator('body')).toContainText('重开后新意图8.125', { timeout: 8000 })
  await page.reload()
  await login(page, '恢复甲')
  await openConversationWith(page, '恢复乙')
  await expect(page.getByText('重开后新意图8.125', { exact: true })).toHaveCount(1)
  await ctx.close()
})

test('T10: 旧后端缺少消息前缀时具名拒绝新消息', async ({ page }) => {
  await claimIdentity('兼容甲')
  await page.route('**/api/login', async route => {
    const response = await route.fetch()
    const body = await response.json()
    delete body.send_nonce
    await route.fulfill({ response, json: body })
  })
  await login(page, '兼容甲')
  await expect(page.getByText('服务版本不兼容：请更新后端后重新登录', { exact: true })).toBeVisible()
  await expect(composerInput(page)).toHaveCount(0)
})
