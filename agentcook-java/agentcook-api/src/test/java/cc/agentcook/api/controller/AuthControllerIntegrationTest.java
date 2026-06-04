package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Base64;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AuthControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void loginReturnsDummyBearerToken() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"dev"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").isNotEmpty())
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.expiresIn").value(3600));
    }

    @Test
    void loginRejectsBlankPassword() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"x"}
                                """))
                .andExpect(status().isOk());

        // password trimmed to empty in the body would also fail — the
        // controller's blank check covers that path; 400 is asserted by
        // the validation layer when the field is missing entirely.
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":""}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    void loginIssuesJwtWithUserUuidSubject() throws Exception {
        // W3 #1 fix — the JWT subject must be a UUID (the user's
        // aggregate id), not the raw username, so that downstream
        // routes can resolve the caller via SecurityContext.
        UUID sub = decodeSubject(login("brand-new-bob"));
        assertThat(userRepository.findById(cc.agentcook.domain.user.UserId.from(sub)))
                .as("login should auto-provision a User aggregate keyed off <username>@dev.local")
                .isPresent();
    }

    @Test
    void loginIsIdempotentForRepeatedUsername() throws Exception {
        UUID first = decodeSubject(login("repeat-bob"));
        UUID second = decodeSubject(login("repeat-bob"));
        assertThat(second)
                .as("repeated logins for the same username must resolve to the same User aggregate")
                .isEqualTo(first);
    }

    private String login(String username) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"dev"}
                                """.formatted(username)))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode body = objectMapper.readTree(result.getResponse().getContentAsString());
        return body.get("accessToken").asText();
    }

    private UUID decodeSubject(String jwt) throws Exception {
        String[] parts = jwt.split("\\.");
        String payload = new String(Base64.getUrlDecoder().decode(parts[1]));
        return UUID.fromString(objectMapper.readTree(payload).get("sub").asText());
    }
}
