import { expect, test } from '@playwright/test'

test.describe('PaperAI research workflow', () => {
  test.skip(process.env.PAPERAI_E2E !== 'true', 'Set PAPERAI_E2E=true against the Compose stack')
  test('login and traverse the canonical V1 project surface', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名或邮箱').fill(process.env.PAPERAI_E2E_USER || 'admin')
    await page.getByPlaceholder('请输入密码').fill(process.env.PAPERAI_E2E_PASSWORD || '')
    await page.getByRole('button', { name: /登录/ }).click()
    await expect(page).toHaveURL(/\/(home|papers|projects)(\/|$)/)
    await page.goto('/projects')
    await expect(page.getByRole('heading', { name: '我的科研项目' })).toBeVisible()

    const projectLink = page.getByRole('link', { name: /打开项目/ }).first()
    if (!(await projectLink.count())) return
    await projectLink.click()
    await expect(page).toHaveURL(/\/projects\/[^/]+\/overview$/)
    await expect(page.getByRole('link', { name: /进入文献发现/ })).toBeVisible()

    await page.getByRole('link', { name: '文献发现', exact: true }).click()
    await expect(page).toHaveURL(/\/projects\/[^/]+\/discover$/)
    await expect(page.getByText('文献发现').first()).toBeVisible()

    await page.getByRole('link', { name: '项目论文', exact: true }).click()
    await expect(page).toHaveURL(/\/projects\/[^/]+\/papers$/)
    await expect(page.getByRole('heading', { name: '项目论文' })).toBeVisible()
    const readerButton = page.getByRole('button', { name: '打开 Reader' }).first()
    if (await readerButton.count()) {
      await readerButton.click()
      await expect(page).toHaveURL(/\/paper\/[^/]+/)
      await page.goBack()
    }

    await page.getByRole('link', { name: '写作', exact: true }).click()
    await expect(page).toHaveURL(/\/projects\/[^/]+\/writing$/)
    await expect(page.getByLabel('正式论文写作工作区')).toBeVisible()
  })
})
