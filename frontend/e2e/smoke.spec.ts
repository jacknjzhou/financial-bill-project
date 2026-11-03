import { expect, test } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

/**
 * 全链路冒烟：登录 → 上传 11-01 夹具 ×2 → 触发对账 → 结果断言 → 差错处理 → 工作台。
 * 依赖：compose 全栈已起 + `seed_demo` 已执行（10-31 success，11-01 夹具在 data/demo/）。
 */
const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEMO_DIR = process.env.E2E_DEMO_DIR ?? path.resolve(HERE, "../../data/demo");

test("全链路：上传→对账→结果→差错→工作台", async ({ page }) => {
  // 登录
  await page.goto("/login");
  await page.getByPlaceholder("请输入用户名", { exact: false }).or(page.locator("input").first()).first().fill("admin");
  await page.locator("input[type=password]").fill("Admin@123");
  await page.getByRole("button", { name: /登\s*录/ }).click();
  await expect(page).not.toHaveURL(/login/, { timeout: 15000 });

  // 上传 11-01 两个夹具
  await page.getByRole("menuitem", { name: "数据管理" }).click();
  await page.getByRole("menuitem", { name: "文件管理" }).click();
  await page.locator(".el-select").first().click();
  await page.getByRole("option", { name: /平台支付上传/ }).click();
  const fileInput = page.locator("input[type=file]");
  await fileInput.setInputFiles(path.join(DEMO_DIR, "demo-20261101-payment.csv"));
  await page.locator(".el-select").first().click();
  await page.getByRole("option", { name: /渠道清算上传/ }).click();
  await fileInput.setInputFiles(path.join(DEMO_DIR, "demo-20261101-clearing.csv"));
  // 轮询等待解析完成（UI 每 3s 刷新）
  await expect(page.getByText("已入库").first()).toBeVisible({ timeout: 60000 });

  // 触发对账 11-01（页面日期选择器默认昨天，此处显式指定夹具日期）
  await page.getByRole("menuitem", { name: "对账运行", exact: true }).click();
  await page.locator(".el-date-editor input").first().fill("2026-11-01");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: /执行：演示-微信交易对账/ }).click();
  await page.locator(".el-message-box__btns button").last().click(); // 确认
  await expect(page.locator(".el-message-box")).toBeHidden({ timeout: 15000 }); // 已触发
  await page.waitForTimeout(3000); // 等 worker 执行
  await page.reload();

  // 对账运行页断言计数：40 对平 / 10 单边A / 5 单边B / 10 错账
  const row = page.locator("tr", { hasText: "2026-11-01" }).first();
  await expect(row).toBeVisible({ timeout: 30000 });
  await expect(row).toContainText("成功");

  // 对账结果页：总笔数 115
  await page.getByRole("menuitem", { name: "对账结果", exact: true }).click();
  await page.locator(".el-date-editor input").first().fill("2026-11-01");
  await page.keyboard.press("Enter"); // 日期 change 直接触发查询
  await expect(page.locator(".el-pagination__total")).toContainText("115", { timeout: 30000 });

  // 差错处理：处理一条错账（补单 + 备注）
  await page.getByRole("menuitem", { name: "差错处理", exact: true }).click();
  await page.getByRole("button", { name: "处理" }).first().click();
  await page.locator(".el-dialog .el-select").click();
  await page.getByRole("option", { name: "补单" }).click();
  await page.locator(".el-dialog textarea").fill("已按渠道数据补录，验证通过");
  await page.locator(".el-dialog").getByRole("button", { name: "提交" }).click();
  await expect(page.getByText("已提交")).toBeVisible();

  // 工作台：待处理差异数可见
  await page.getByRole("menuitem", { name: "工作台" }).click();
  await expect(page.getByText("待处理差异")).toBeVisible();
});
