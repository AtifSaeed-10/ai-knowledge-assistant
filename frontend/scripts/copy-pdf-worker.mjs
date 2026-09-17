import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const pdfjsRoot = dirname(require.resolve("pdfjs-dist/package.json"));
const source = join(pdfjsRoot, "build", "pdf.worker.min.mjs");
const destDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
mkdirSync(destDir, { recursive: true });
copyFileSync(source, join(destDir, "pdf.worker.min.mjs"));
