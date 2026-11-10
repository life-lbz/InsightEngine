/* eslint-env node */
module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: "detect" } },
  plugins: ["react-hooks", "@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: ["dist", "node_modules", "coverage", "*.config.js", "*.config.cjs"],
  rules: {
    // React Hooks 规则：生产环境必须严格
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    // 以下为 react-hooks v6 激进新规则，暂关闭（引入 Query 层 / 重构 hook 后自然消除）：
    // purity：连 Date.now 都会报；set-state-in-effect：禁止 fetch-on-mount 常见模式；
    // refs：误报 render 期间写 ref 的 latest-ref 模式（React 官方允许）
    "react-hooks/purity": "off",
    "react-hooks/set-state-in-effect": "off",
    "react-hooks/refs": "off",
    "react-hooks/immutability": "off",
    // TypeScript 纪律
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    // 代码卫生：保留 warn/error 日志，调试 log 需移除
    "no-console": ["warn", { allow: ["warn", "error"] }],
    "no-constant-condition": ["error", { checkLoops: false }],
  },
};
