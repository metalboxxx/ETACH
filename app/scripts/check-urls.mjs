// Offline guard (PRD §11): fails on any http(s):// URL in src/ or index.html that is not
// 127.0.0.1 / localhost. No CDN links, no Google Fonts, no analytics.
// Generated types (src/gen) are included: they are only types, but a URL there would still be
// worth a look. Run: `npm run check:urls` (also run inside `npm test`, see urls.test.ts).
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const URL_RE = /https?:\/\/([^\s"'`)<>/:]+)/g;
const ALLOWED_HOSTS = new Set(["127.0.0.1", "localhost"]);
const EXTS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".css", ".html", ".json", ".svg"]);

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else if (EXTS.has(path.extname(entry.name))) yield p;
  }
}

export async function findExternalUrls(root = appDir) {
  const files = [path.join(root, "index.html")];
  for await (const f of walk(path.join(root, "src"))) files.push(f);
  const hits = [];
  for (const file of files) {
    const lines = (await readFile(file, "utf8")).split(/\r?\n/);
    lines.forEach((line, i) => {
      for (const m of line.matchAll(URL_RE)) {
        if (!ALLOWED_HOSTS.has(m[1])) {
          hits.push(`${path.relative(root, file).replaceAll("\\", "/")}:${i + 1}: ${m[0]}`);
        }
      }
    });
  }
  return hits;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const hits = await findExternalUrls();
  if (hits.length) {
    console.error(`External URLs found (the app must stay offline):\n${hits.join("\n")}`);
    process.exit(1);
  }
  console.log("check:urls: no external URLs in src/ or index.html");
}
