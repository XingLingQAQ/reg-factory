import {mkdir} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright-core";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = path.join(root, "test-results");
const executablePath = process.env.PLAYWRIGHT_BROWSER_PATH
  || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

await mkdir(outputDir, {recursive: true});
const browser = await chromium.launch({headless: true, executablePath});

try {
  for (const target of [
    {name: "desktop", width: 1440, height: 1000},
    {name: "mobile", width: 390, height: 844},
  ]) {
    const page = await browser.newPage({viewport: {width: target.width, height: target.height}});
    const errors = [];
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => localStorage.setItem("k12-console-tenant-id", "verification_ui"));
    await page.goto("http://127.0.0.1:8806/", {waitUntil: "networkidle"});
    await page.locator("h1").waitFor({state: "visible"});

    const metrics = await page.evaluate(() => ({
      title: document.title,
      h1: document.querySelector("h1")?.textContent?.trim(),
      bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      clippedButtons: [...document.querySelectorAll("button")]
        .filter((button) => button.offsetParent !== null && button.scrollWidth > button.clientWidth + 2)
        .map((button) => button.getAttribute("aria-label") || button.textContent?.trim() || "button"),
      taskPanelHeight: Math.round(document.querySelector(".task-panel")?.getBoundingClientRect().height || 0),
    }));

    const image = await page.screenshot({path: path.join(outputDir, `ui-${target.name}.png`), fullPage: true});

    if (metrics.title !== "Codex K12 | Reg Factory" || metrics.h1 !== "Codex K12") {
      throw new Error(`${target.name}: brand content was not rendered`);
    }
    if (metrics.bodyOverflow) throw new Error(`${target.name}: page has horizontal overflow`);
    if (metrics.clippedButtons.length) throw new Error(`${target.name}: clipped buttons: ${metrics.clippedButtons.join(", ")}`);
    if (metrics.taskPanelHeight < 400 || image.length < 10000) throw new Error(`${target.name}: primary surface is blank or undersized`);

    await page.getByRole("button", {name: "打开设置"}).click();
    const dialog = page.getByRole("dialog", {name: "Sub2API 和 K12 配置"});
    await dialog.waitFor({state: "visible"});
    const dialogMetrics = await dialog.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        left: rect.left,
        right: rect.right,
        width: rect.width,
        innerOverflow: element.scrollWidth > element.clientWidth + 1,
      };
    });
    const dialogImage = await page.screenshot({path: path.join(outputDir, `ui-${target.name}-settings.png`), fullPage: true});
    if (dialogMetrics.left < 0 || dialogMetrics.right > target.width + 1 || dialogMetrics.innerOverflow) {
      throw new Error(`${target.name}: settings dialog overflows viewport`);
    }
    if (dialogImage.length < 10000) throw new Error(`${target.name}: settings dialog is blank`);
    if (errors.length) throw new Error(`${target.name}: browser errors: ${errors.join(" | ")}`);
    await page.close();
    console.log(`${target.name}: ok (${image.length + dialogImage.length} bytes)`);
  }
} finally {
  await browser.close();
}
