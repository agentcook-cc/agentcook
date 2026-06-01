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
}
