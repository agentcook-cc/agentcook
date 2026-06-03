// e2e specs reuse the Buffer Day 63 codename / private-email block from
// agentcook-app. Without this file, lint-staged in `e2e/` runs eslint
// with no config and exits 2 (couldn't find configuration). The pre-existing
// specs (smoke / chat-page / full-user-journey / audit-screenshot) likely
// landed before simple-git-hooks was installed, which masked the gap.
//
// `root: true` so eslint stops climbing here — this file is the
// configuration for everything under `e2e/`.
const appEslint = require('../agentcook-app/.eslintrc.cjs');

module.exports = {
  ...appEslint,
  root: true,
};
