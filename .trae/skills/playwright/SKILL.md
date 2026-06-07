---
name: playwright
description: Web自动化测试和浏览器操作。Invoke when user needs end-to-end testing, browser automation, web scraping, UI testing, or cross-browser compatibility testing.
---

# 🎭 Playwright

Playwright is a framework for Web Testing and Automation. It allows testing Chromium, Firefox and WebKit with a single API.

## 使用场景

- 端到端测试 (E2E Testing)
- 浏览器自动化操作
- 网页截图和PDF生成
- UI交互自动化
- 跨浏览器兼容性测试
- Web爬虫任务

## 快速开始

### 安装

```bash
npm init playwright@latest
```

### 基本用法

```typescript
import { test, expect } from '@playwright/test';

test('basic test', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example/);
});
```

### 常用命令

- `npx playwright test` - 运行测试
- `npx playwright test --headed` - 有头模式运行
- `npx playwright test --debug` - 调试模式
- `npx playwright show-report` - 查看测试报告
- `npx playwright codegen` - 代码生成器

## 核心功能

### 页面操作

```typescript
// 导航
await page.goto('https://example.com');

// 点击元素
await page.click('button');

// 填写表单
await page.fill('input[name="email"]', 'test@example.com');

// 获取文本
const text = await page.textContent('.title');

// 截图
await page.screenshot({ path: 'screenshot.png' });
```

### 选择器

- CSS选择器: `page.click('button.primary')`
- 文本选择器: `page.click('text=Submit')`
- XPath: `page.click('xpath=//button')`
- 角色选择器: `page.getByRole('button', { name: 'Submit' })`

### 等待策略

Playwright 自动等待元素可操作，无需手动添加等待：

```typescript
// 自动等待元素可见并可点击
await page.click('button');

// 等待网络空闲
await page.waitForLoadState('networkidle');

// 等待特定选择器
await page.waitForSelector('.loaded');
```

## 最佳实践

1. **使用语义化选择器** - 优先使用 `getByRole`, `getByText`, `getByLabel`
2. **避免硬编码等待** - 依赖 Playwright 的自动等待机制
3. **使用 Page Object 模式** - 封装页面操作逻辑
4. **并行执行测试** - 利用 Playwright 的并行测试能力
5. **截图和追踪** - 失败时自动截图，便于调试

## 调试技巧

- 使用 `--debug` 标志启动调试模式
- 使用 `page.pause()` 暂停执行
- 查看 HTML 报告: `npx playwright show-report`
- 使用 Trace Viewer: `npx playwright show-trace trace.zip`
