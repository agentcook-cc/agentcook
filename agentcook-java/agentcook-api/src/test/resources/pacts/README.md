# Pact Java provider contract templates

This directory holds **consumer-shape Pact JSON files** that describe
how `agentcook-app` (and later `agentcook-admin`) expect to talk to
this Java provider.

## Day 24 status (today)

- `agentcook-app-agentcook-java.json` — consumer template for
  `GET /api/v1/plugins` with one published plugin.
- `ContractScaffoldingTest` validates:
  1. the JSON is well-formed and declares the expected interaction shape,
  2. the provider state ("one published plugin exists") is reproducible
     against the real persistence stack,
  3. the live endpoint response matches the pact's expected shape /
     matchers / status code.

This is a **stand-in for full broker verification**. The pact-jvm
`@Provider` / `@PactBroker` `@TestTemplate` machinery is intentionally
deferred to Day 25.

## Day 25+ flow (with Agent C)

1. C wires `pact-broker` publish in CI (`pact-provider-ci.yml`).
2. Frontend (B) generates real pacts from typed clients on `pnpm test`.
3. Java provider replaces `ContractScaffoldingTest` with a real
   `@Provider("agentcook-java")` `@PactBroker(url = ...)`
   `@TestTemplate` test that fetches pacts from the broker and
   verifies them against the live Spring Boot app.
4. CI fails the PR if any consumer's pact breaks against the Java
   provider, gating breaking changes.

## Why scaffolding instead of full pact-jvm today

Day 24 spent the available budget on the spec freeze (java-v1.yaml v1.0)
and Controller / DTO / integration tests. A bring-up of the full
`@Provider` machinery surfaced a pact-jvm 4.6.10 client-level 401 that
does not reproduce against the same endpoint via `HttpURLConnection` —
diagnosing it deeper would have pushed past the daily timebox without
adding value beyond what the scaffolding test already covers
(state + endpoint shape). Day 25 reopens this with C in the loop.
