import { expect, test } from '@playwright/test'

test.describe('PaperAI research workflow', () => {
  test.skip(process.env.PAPERAI_E2E !== 'true', 'Set PAPERAI_E2E=true against the Compose stack')
  test('login, project, reading evidence, and writing flow', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/用户名|邮箱/).fill(process.env.PAPERAI_E2E_USER || 'admin')
    await page.getByLabel(/密码/).fill(process.env.PAPERAI_E2E_PASSWORD || '')
    await page.getByRole('button', { name: /登录/ }).click()
    await expect(page).toHaveURL(/papers|projects/)
    await page.goto('/projects')
    await expect(page.getByText(/研究项目/).first()).toBeVisible()
    // Remaining steps use seeded project/paper data so no online model is required.
    const projectLink = page.getByRole('link', { name: /打开|进入/ }).first()
    if (await projectLink.count()) {
      await projectLink.click()
      await expect(page.getByText('研究工作台')).toBeVisible()
      await page.getByRole('button', { name: '论文库与阅读' }).click()
      await page.getByRole('button', { name: '研究证据' }).click()
      await page.getByRole('button', { name: '论文与章节' }).click()
      await expect(page.getByLabel('Writing V2 编辑器')).toBeVisible()
    }
  })
})
