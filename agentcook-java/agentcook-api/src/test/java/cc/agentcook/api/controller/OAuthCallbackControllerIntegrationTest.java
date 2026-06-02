package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class OAuthCallbackControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;

    @Test
    void issuesDummyTokenForSupportedProvider() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"dingtalk","code":"auth-code-xyz","state":"csrf-state"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.provider").value("dingtalk"))
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.expiresIn").value(3600))
                .andExpect(jsonPath("$.accessToken").value(org.hamcrest.Matchers.startsWith("dev-dingtalk-")));
    }

    @Test
    void rejectsUnsupportedProvider() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"wechat","code":"x","state":"y"}
                                """))
                .andExpect(status().isBadRequest());
    }

    // ---------------------------------------------------------------
    // Day 51: OAuth state 字段校验 — current-behaviour record.
    //
    // The Phase 3 dummy callback declares a `state` field on the
    // request DTO (Swagger schema describes it as the CSRF state token)
    // but the controller does not read or compare it against any
    // server-side store. These tests *document* that contract so the
    // Day 51 compliance audit has an authoritative record.
    //
    // Phase 4 Day 33-34 wires the real DingTalk/Feishu/Telegram SDKs and
    // MUST also bind state to a Redis 5-min TTL store, at which point
    // these tests flip from "accepts arbitrary state" to "rejects
    // unknown state" — that's the correct prod contract. We do not
    // write red tests for that contract today because Phase 3 has no
    // /authorize endpoint to mint a known-good state, so a "must reject
    // unknown" assertion would deadlock the frontend OAuth flow tests.
    // ---------------------------------------------------------------

    @Test
    void phase3DummyAcceptsCallback_whenStateFieldIsAbsent() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"feishu","code":"auth-code-no-state"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.provider").value("feishu"))
                .andExpect(jsonPath("$.tokenType").value("Bearer"));
    }

    @Test
    void phase3DummyAcceptsCallback_whenStateFieldIsBlank() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"telegram","code":"auth-code-blank-state","state":""}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.provider").value("telegram"));
    }

    @Test
    void phase3DummyAcceptsCallback_whenStateFieldIsArbitrary() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"discord","code":"auth-code-1","state":"any-attacker-supplied-value"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.provider").value("discord"));
    }

    @Test
    void phase3DummyRejectsMissingCode_butStateRemainsUnchecked() throws Exception {
        // Confirms validation only enforces @NotBlank on provider/code.
        // A real OAuth callback with no `code` is invalid regardless of
        // CSRF — that 400 path is the existing Phase 3 contract.
        mockMvc.perform(post("/api/v1/connectors/oauth/callback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"provider":"slack","state":"only-state-no-code"}
                                """))
                .andExpect(status().isBadRequest());
    }
}
