const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const out = path.resolve('test-results');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.env.APP_URL || 'http://127.0.0.1:8765');
    await page.getByRole('button', { name: '新建活动', exact: true }).click();
    for (let i = 0; i < 7; i++) {
      await page.keyboard.press('Tab');
      assert(await page.evaluate(() => !!document.activeElement.closest('[role=dialog]')), 'Keyboard focus must stay within the open dialog');
    }
    const activityTitle = `浏览器验收活动 ${Date.now()}`;
    await page.getByLabel('活动名称').fill(activityTitle);
    await page.getByRole('button', { name: '创建活动', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    await page.getByRole('heading', { name: activityTitle, exact: true }).waitFor();
    await page.getByLabel('想留下什么').fill('周六下午在公园见面');
    await page.getByRole('button', { name: '保存记录', exact: true }).click();
    await page.getByText('周六下午在公园见面', { exact: true }).waitFor();
    await page.getByRole('button', { name: '更正这条记录' }).click();
    await page.getByLabel('想留下什么').fill('改成周日下午');
    await page.getByRole('button', { name: '保存记录', exact: true }).click();
    await page.getByText('改成周日下午', { exact: true }).waitFor();
    await page.getByRole('button', { name: '接上这件事', exact: true }).click();
    await page.getByRole('button', { name: '这次有帮助', exact: true }).click();
    await page.getByText('已记录反馈').waitFor();
    await page.getByRole('button', { name: '暂停帮助', exact: true }).click();
    await page.getByRole('button', { name: '恢复帮助', exact: true }).waitFor();
    assert(await page.getByRole('button', { name: '接上这件事', exact: true }).isDisabled());
    await page.getByRole('button', { name: '恢复帮助', exact: true }).click();
    await page.getByRole('button', { name: '暂停帮助', exact: true }).waitFor();
    await page.getByLabel('想留下什么').fill('活动后的测试照片');
    await page.locator('input[type=file]').setInputFiles(path.resolve('tests/fixtures/photo.png'));
    await page.getByRole('button', { name: '保存记录', exact: true }).click();
    await page.getByAltText('这条记录附带的照片，来源：我').waitFor();
    assert(await page.getByAltText('这条记录附带的照片，来源：我').evaluate(img => img.complete && img.naturalWidth > 0));
    await page.locator('.experiment > summary').click();
    await page.getByRole('button', { name: '人工导入 GPT 回复', exact: true }).click();
    await page.getByLabel('模型名称与使用日期').fill('人工构造回复，非模型调用 2026-11-13');
    await page.getByLabel('实际使用的提示').fill('这是一条浏览器工程验收输入，不是真实 LLM 实验');
    await page.getByLabel('粘贴模型回复').fill('已导入的测试说明，不将其写为事实');
    await page.getByRole('button', { name: '保存为模型解释', exact: true }).click();
    await page.getByText('已导入的测试说明，不将其写为事实', { exact: true }).waitFor();
    await page.getByRole('heading', {name: activityTitle, exact:true}).click();
    await page.screenshot({ path: path.join(out, 'desktop.png'), fullPage: true });
    await page.reload();
    await page.getByText('改成周日下午', { exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(out, 'mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.getByRole('button', { name: '研究与启动材料', exact: true }).click();
    await page.getByRole('heading', { name: '从一次完整经历开始' }).waitFor();
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(out,'research.png'),fullPage:true});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: 'passed', errors, viewports: ['1440x1000', '390x844'] }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
