// Buffer Day 58 (B) — overrides the inline `lint-staged` field in
// package.json. Reason: ESLint v8 default espree can't parse TS
// (`interface`, `type`) or Vue SFCs, and ESLint ignorePatterns does NOT
// apply to CLI-explicit paths (only to directory scans). lint-staged
// hands every changed file to eslint as an explicit path, so without
// this filter the pre-commit hook fails on any src/*.{tsx,vue} change
// with `Parsing error: 'interface' is reserved` / `Unexpected token <`.
//
// Until vue-eslint-parser + @typescript-eslint/parser are installed
// (cross-cutting Buffer item — adds devDeps + plugin resolution), src/
// in both frontends runs prettier only at commit time. Codename /
// private-email block (Buffer Day 63) still runs on .cjs / .js /
// non-TS .ts and on the dedicated fixture set, which was the original
// scope of `agentcook-{admin,app}/.eslintrc.cjs` per their headers.
const isFrontendSrc = (file) =>
  file.includes('/agentcook-admin/src/') || file.includes('/agentcook-app/src/');

module.exports = {
  '*.{ts,tsx,vue}': (files) => {
    const lintable = files.filter((f) => !isFrontendSrc(f));
    const cmds = [];
    if (lintable.length > 0) {
      cmds.push(`eslint --fix ${lintable.map((f) => `"${f}"`).join(' ')}`);
    }
    cmds.push(`prettier --write ${files.map((f) => `"${f}"`).join(' ')}`);
    return cmds;
  },
  '*.{css,scss,json,md}': ['prettier --write'],
};
