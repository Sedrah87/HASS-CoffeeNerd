// Prüft die Lizenzen aller Pakete, die tatsächlich im Panel-Bundle landen, und
// schreibt ihre Lizenz- und NOTICE-Texte nach THIRD_PARTY_NOTICES.md im
// Integrationsordner. So liegen die Hinweise auch bei einer HACS-Installation bei.
// Die Paketliste schreibt der Build (vite.config.ts) nach dist/bundled-packages.json,
// darum läuft dieses Skript nach `npm run build`.
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ALLOWED = new Set(["MIT", "ISC", "0BSD", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0"]);
const OUTPUT = "../custom_components/coffeenord/frontend/THIRD_PARTY_NOTICES.md";
const BUNDLED = "dist/bundled-packages.json";

if (!existsSync(BUNDLED)) {
  console.error(`❌ ${BUNDLED} fehlt, zuerst npm run build ausführen.`);
  process.exit(1);
}
const packages = new Map(
  JSON.parse(readFileSync(BUNDLED, "utf8")).map((name) => {
    const path = join("node_modules", name);
    const { version } = JSON.parse(readFileSync(join(path, "package.json"), "utf8"));
    return [`${name}@${version}`, { path }];
  }),
);

const failures = [];
const sections = [];
for (const [id, info] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
  const pkg = JSON.parse(readFileSync(join(info.path, "package.json"), "utf8"));
  const license = typeof pkg.license === "string" ? pkg.license : "UNKNOWN";
  if (!ALLOWED.has(license)) failures.push(`${id}: ${license}`);

  const texts = readdirSync(info.path)
    .filter((file) => /^(licen[cs]e|notice|copying)(\.|$)/i.test(file))
    .sort()
    .map((file) => readFileSync(join(info.path, file), "utf8").trim());
  if (texts.length === 0) failures.push(`${id}: keine Lizenzdatei gefunden`);
  sections.push(`## ${id} (${license})\n\n\`\`\`\n${texts.join("\n\n")}\n\`\`\``);
}

if (failures.length) {
  console.error("❌ Lizenzprüfung fehlgeschlagen:\n  " + failures.join("\n  "));
  process.exit(1);
}

const header =
  "# Third-party notices\n\n" +
  "Das Panel-Bundle (coffeenord-panel.js) enthält die folgenden Pakete.\n" +
  "Diese Datei wird von frontend/scripts/licenses.mjs erzeugt.\n";
const content = `${header}\n${sections.join("\n\n")}\n`;
if (!existsSync(OUTPUT) || readFileSync(OUTPUT, "utf8") !== content) {
  writeFileSync(OUTPUT, content);
}
console.log(`✅ ${packages.size} Pakete im Bundle, alle Lizenzen erlaubt.`);
