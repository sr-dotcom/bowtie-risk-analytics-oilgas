import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(__dirname, "../../data/demo_scenarios");
const DEST_DIR = join(__dirname, "../public/demo-scenarios");

if (!existsSync(SRC_DIR)) {
  console.error(`copy-demo-scenarios: source directory not found: ${SRC_DIR}`);
  process.exit(1);
}

const jsonFiles = readdirSync(SRC_DIR).filter((f) => f.endsWith(".json"));

if (jsonFiles.length === 0) {
  console.error(`copy-demo-scenarios: source directory is empty: ${SRC_DIR}`);
  process.exit(1);
}

mkdirSync(DEST_DIR, { recursive: true });

for (const file of jsonFiles) {
  const content = readFileSync(join(SRC_DIR, file), "utf8");
  // validate JSON before copying
  JSON.parse(content);
  writeFileSync(join(DEST_DIR, file), content, "utf8");
}

console.log(`copy-demo-scenarios: copied ${jsonFiles.length} scenarios to ${DEST_DIR}`);
