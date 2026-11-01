// Render ADR-024's app icons from scripts/icon.svg into public/icons/ (run by hand after
// changing the drawing; the PNGs are committed):
//
//   CHROME_PATH=/path/to/chrome node scripts/make-icons.mjs
//
// icon-*.png: rounded corners on a transparent ground ("any"); maskable-512.png and
// apple-touch-icon.png: full bleed, since Android's mask and iOS round them themselves.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const svg = fs.readFileSync(path.join(here, "icon.svg"), "utf8");
const out = path.resolve(here, "..", "public", "icons");
fs.mkdirSync(out, { recursive: true });

const ICONS = [
  { file: "icon-192.png", size: 192, rounded: true },
  { file: "icon-512.png", size: 512, rounded: true },
  { file: "maskable-512.png", size: 512, rounded: false },
  { file: "apple-touch-icon.png", size: 180, rounded: false },
];

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ["--no-sandbox"] });
try {
  const page = await browser.newPage();
  for (const { file, size, rounded } of ICONS) {
    const drawn = rounded ? svg.replace('<rect id="bg"', '<rect id="bg" rx="96"') : svg;
    await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 });
    await page.setContent(`<html><body style="margin:0;background:transparent">${drawn.replace(/width="512" height="512"/, `width="${size}" height="${size}"`)}</body></html>`);
    await page.screenshot({ path: path.join(out, file), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
    console.log(`make-icons: ${file} ${size}x${size}`);
  }
} finally {
  await browser.close();
}
