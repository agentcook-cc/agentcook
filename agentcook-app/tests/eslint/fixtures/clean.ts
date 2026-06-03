// Fixture 5/5: clean baseline using public-substitution names.
// Expected to PASS ESLint (exit code 0). This proves the rule is
// targeted enough not to over-flag normal code.

export const middlewareName = "gRPC";
export const queueLabel = `kafka-prod-queue`;
const Redis = { host: "localhost", port: 6379 };
export const ownerEmail = "alice@example.com";
export { Redis };
