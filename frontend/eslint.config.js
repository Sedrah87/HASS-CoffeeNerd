import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["node_modules/", "dist/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Build-Skripte laufen unter Node.
    files: ["scripts/**/*.mjs", "vite.config.ts"],
    languageOptions: { globals: { console: "readonly", process: "readonly" } },
  },
);
