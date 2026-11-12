import { mkdirSync, writeFileSync } from "node:fs";
import { defineConfig, type Plugin } from "vite";

// Schreibt die Pakete, die tatsächlich im Bundle landen, nach dist/bundled-packages.json.
// scripts/licenses.mjs prüft genau diese Pakete und erzeugt daraus die Lizenzhinweise.
function bundledPackages(): Plugin {
  return {
    name: "coffeenord-bundled-packages",
    generateBundle(_options, bundle) {
      const packages = new Set<string>();
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== "chunk") continue;
        for (const id of Object.keys(chunk.modules)) {
          const match = id.match(/node_modules\/((?:@[^/]+\/)?[^/]+)\//);
          if (match) packages.add(match[1]);
        }
      }
      mkdirSync("dist", { recursive: true });
      writeFileSync("dist/bundled-packages.json", JSON.stringify([...packages].sort(), null, 2));
    },
  };
}

// Ein einzelnes ES-Modul, das Home Assistant als Custom Panel lädt.
// Das Ergebnis wird eingecheckt, weil HACS nur custom_components/ installiert.
export default defineConfig({
  plugins: [bundledPackages()],
  // Im Bibliotheksmodus ersetzt Vite process.env.NODE_ENV nicht selbst. Im Browser
  // gibt es kein process, Lit und ECharts würden sonst beim Laden abbrechen.
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../custom_components/coffeenord/frontend",
    emptyOutDir: false,
    target: "es2022",
    minify: true,
    lib: {
      entry: "src/coffeenord-panel.ts",
      formats: ["es"],
      fileName: () => "coffeenord-panel.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true, minify: true },
    },
  },
});
