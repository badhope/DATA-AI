// UI import 验证：用 jiti 直接 import tsx 文件，看是否能成功 import
import { createJiti } from "jiti";
const jiti = createJiti(import.meta.url, {
  esmResolve: true,
  interopDefault: true,
  alias: { "@/": "./src/" },
});

const pages = [
  "pages/dashboard",
  "pages/agents",
  "pages/team",
  "pages/tools",
  "pages/memory",
  "pages/rag",
  "pages/sandbox",
  "pages/skills",
  "pages/models",
  "pages/notifications",
  "pages/settings",
  "pages/office/word",
  "pages/office/excel",
  "pages/office/pdf",
  "pages/office/ppt",
  // 这些需要 router context
  // "pages/agent-detail",
  // "pages/team-detail",
  // "pages/tool-detail",
  // "pages/sandbox-detail",
  // "pages/rag-document",
  // "pages/chat",
];

let pass = 0, fail = 0;
const errs = [];
for (const p of pages) {
  try {
    const m = jiti(`./src/${p}.tsx`);
    const exp = Object.keys(m);
    if (exp.length === 0) throw new Error("no exports");
    console.log("✓", p + ".tsx", "→", exp.join(","));
    pass++;
  } catch (e) {
    console.log("✗", p + ".tsx", "→", String(e?.message || e).slice(0, 250));
    fail++;
    errs.push({ p, err: String(e?.message || e).slice(0, 500) });
  }
}
console.log(`\n=== UI import 验证: ${pass} pass, ${fail} fail ===`);
if (fail > 0) {
  console.log("\n=== 失败 ===");
  for (const e of errs) console.log(" -", e.p, "→", e.err);
}
process.exit(fail > 0 ? 1 : 0);
