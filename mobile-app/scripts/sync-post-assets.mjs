import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const mobileDir = resolve(scriptDir, "..");
const repoDir = resolve(mobileDir, "..");
const sourceDir = resolve(repoDir, "output", "posts");
const targetDir = resolve(mobileDir, "public", "posts");
const publicDir = resolve(mobileDir, "public");

await rm(targetDir, { force: true, recursive: true });
await mkdir(dirname(targetDir), { recursive: true });
await cp(sourceDir, targetDir, { recursive: true });
await cp(resolve(repoDir, "output", "posts_index.json"), resolve(publicDir, "posts_index.json"));
await cp(resolve(repoDir, "output", "app_logo_80x80_rounded.png"), resolve(publicDir, "app_logo_80x80_rounded.png"));

console.log(`Synced post assets: ${sourceDir} -> ${targetDir}`);
