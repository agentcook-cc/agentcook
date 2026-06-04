package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class SessionControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;
    @Autowired private SessionRepository sessionRepository;

    @Test
    void createsSessionForExistingUser() throws Exception {
        User user = userRepository.save(User.create("carol@example.com", "Carol"));

        mockMvc.perform(post("/api/v1/sessions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"userId":"%s","title":"Hello"}
                                """.formatted(user.getId().value())))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.title").value("Hello"))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.userId").value(user.getId().value().toString()));
    }

    @Test
    void returns404WhenUserMissing() throws Exception {
        mockMvc.perform(post("/api/v1/sessions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"userId":"00000000-0000-0000-0000-000000000000","title":"x"}
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("USER_NOT_FOUND"));
    }

    @Test
    void listsSessionsByUserId() throws Exception {
        User user = userRepository.save(User.create("frank@example.com", "Frank"));
        Session session = Session.create(user.getId(), "First chat");
        sessionRepository.save(session);

        mockMvc.perform(get("/api/v1/sessions").param("userId", user.getId().value().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].title").value("First chat"));
    }

    @Test
    void createSessionFallsBackToJwtSubjectWhenBodyUserIdBlank() throws Exception {
        User user = userRepository.save(User.create("dana@example.com", "Dana"));
        String sub = user.getId().value().toString();

        mockMvc.perform(post("/api/v1/sessions")
                        .with(jwt().jwt(b -> b.subject(sub)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"title":"Implicit owner via JWT"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.title").value("Implicit owner via JWT"))
                .andExpect(jsonPath("$.userId").value(sub));
    }

    @Test
    void createSessionStillAcceptsExplicitBodyUserIdWhenJwtPresent() throws Exception {
        User explicit = userRepository.save(User.create("explicit@example.com", "Ex"));
        User jwtUser = userRepository.save(User.create("jwt-user@example.com", "Jw"));

        // body.userId wins over JWT subject when both are supplied — admin
        // tooling can still operate on behalf of another user without a
        // session swap.
        mockMvc.perform(post("/api/v1/sessions")
                        .with(jwt().jwt(b -> b.subject(jwtUser.getId().value().toString())))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"userId":"%s","title":"Explicit wins"}
                                """.formatted(explicit.getId().value())))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.userId").value(explicit.getId().value().toString()));
    }
}
