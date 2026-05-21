import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { minify } from "html-minifier-terser";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const mobileDir = resolve(scriptDir, "..");
const repoDir = resolve(mobileDir, "..");
const sourceDir = resolve(repoDir, "output", "posts");
const targetDir = resolve(mobileDir, "public", "posts");
const publicDir = resolve(mobileDir, "public");

await rm(targetDir, { force: true, recursive: true });
await mkdir(dirname(targetDir), { recursive: true });
await cp(sourceDir, targetDir, { recursive: true });

// posts_index.json 은 들여쓰기를 떼고 단일 라인으로 저장.
const indexSrcPath = resolve(repoDir, "output", "posts_index.json");
const indexDstPath = resolve(publicDir, "posts_index.json");
const indexSrc = await readFile(indexSrcPath, "utf8");
const indexBefore = Buffer.byteLength(indexSrc, "utf8");
let indexAfter = indexBefore;
try {
  const parsed = JSON.parse(indexSrc);
  const compact = JSON.stringify(parsed);
  await writeFile(indexDstPath, compact, "utf8");
  indexAfter = Buffer.byteLength(compact, "utf8");
} catch (error) {
  console.warn(`[sync-post-assets] posts_index.json compact 실패, 원본 복사: ${error.message}`);
  await cp(indexSrcPath, indexDstPath);
}

await cp(
  resolve(repoDir, "output", "app_logo_80x80_rounded.png"),
  resolve(publicDir, "app_logo_80x80_rounded.png"),
);

// 번들된 포스트 HTML 이 IPA 사이즈의 가장 큰 단일 기여 카테고리 (~19MB).
// 동작 변경 없이 공백/주석/inline CSS·JS 만 정리해 사이즈 축소.
// output/posts/* 원본은 그대로 두고 mobile-app/public/posts/* 복사본만 minify.
const minifyOptions = {
  collapseWhitespace: true,
  conservativeCollapse: false,
  removeComments: true,
  minifyCSS: true,
  minifyJS: true,
  decodeEntities: false,
  preserveLineBreaks: false,
};

async function* walkHtml(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkHtml(full);
    } else if (entry.isFile() && entry.name.endsWith(".html")) {
      yield full;
    }
  }
}

let htmlBefore = 0;
let htmlAfter = 0;
let htmlCount = 0;
let htmlFailed = 0;
for await (const file of walkHtml(targetDir)) {
  const src = await readFile(file, "utf8");
  const before = Buffer.byteLength(src, "utf8");
  htmlBefore += before;
  htmlCount += 1;
  try {
    const min = await minify(src, minifyOptions);
    await writeFile(file, min, "utf8");
    htmlAfter += Buffer.byteLength(min, "utf8");
  } catch (error) {
    console.warn(`[sync-post-assets] minify 실패, 원본 유지: ${file} (${error.message})`);
    htmlAfter += before;
    htmlFailed += 1;
  }
}

const fmt = (bytes) => `${(bytes / 1024 / 1024).toFixed(2)} MB`;
console.log(`Synced post assets: ${sourceDir} -> ${targetDir}`);
console.log(
  `  posts_index.json: ${fmt(indexBefore)} -> ${fmt(indexAfter)} (-${fmt(indexBefore - indexAfter)})`,
);
console.log(
  `  post.html x${htmlCount}: ${fmt(htmlBefore)} -> ${fmt(htmlAfter)} (-${fmt(htmlBefore - htmlAfter)}, failed=${htmlFailed})`,
);
