// GitHub Pages serves 404.html for any path it has no file for. A copy of
// index.html there lets a deep link or a refresh on /diesel-simulator/enjoy
// load the app, whose router then shows the right page (Phase 8, Pages).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "dist", "app", "browser");
fs.copyFileSync(path.join(dist, "index.html"), path.join(dist, "404.html"));
console.log("pages-404: dist/app/browser/404.html is index.html");
