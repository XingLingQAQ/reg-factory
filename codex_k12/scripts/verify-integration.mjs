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
    {name: "desktop", width: 1440, height: 960},
    {name: "mobile", width: 390, height: 844},
  ]) {
    const page = await browser.newPage({viewport: {width: target.width, height: target.height}});
    const errors = [];
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(error.message));

    await page.goto("http://127.0.0.1:8799/", {waitUntil: "domcontentloaded"});
    await page.locator("#dot-k12.on").waitFor({state: "visible", timeout: 10000});
    await page.locator('[data-view="k12"]').click();
    await page.locator("#k12-channel-status.on").waitFor({state: "visible", timeout: 20000});
    const frame = page.frameLocator("#k12-frame");
    await frame.locator("h1", {hasText: "Codex K12"}).waitFor({state: "visible", timeout: 20000});
    await frame.locator(".service-dot.active").waitFor({state: "visible", timeout: 20000});

    const metrics = await page.evaluate(() => {
      const frameElement = document.querySelector("#k12-frame");
      const rect = frameElement?.getBoundingClientRect();
      return {
        bodyOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        frameWidth: Math.round(rect?.width || 0),
        frameHeight: Math.round(rect?.height || 0),
        offlineVisible: getComputedStyle(document.querySelector("#k12-offline")).display !== "none",
      };
    });
    const image = await page.screenshot({path: path.join(outputDir, `integration-${target.name}.png`), fullPage: true});

    if (metrics.bodyOverflow) throw new Error(`${target.name}: integrated page has horizontal overflow`);
    if (metrics.frameWidth < target.width * 0.7 || metrics.frameHeight < 450) {
      throw new Error(`${target.name}: K12 channel is undersized (${metrics.frameWidth}x${metrics.frameHeight})`);
    }
    if (metrics.offlineVisible) throw new Error(`${target.name}: offline overlay remained visible`);
    if (image.length < 10000) throw new Error(`${target.name}: integrated view is blank`);
    if (errors.length) throw new Error(`${target.name}: browser errors: ${errors.join(" | ")}`);
    await page.close();
    console.log(`${target.name}: ok (${metrics.frameWidth}x${metrics.frameHeight})`);
  }
} finally {
  await browser.close();
}
