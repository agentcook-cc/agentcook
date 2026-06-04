package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class UserControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;

    @Test
    void createsUserAndReturns201WithLocationHeader() throws Exception {
        mockMvc.perform(post("/api/v1/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"alice@example.com","nickname":"Alice"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().exists("Location"))
                .andExpect(jsonPath("$.email").value("alice@example.com"))
                .andExpect(jsonPath("$.status").value("ACTIVE"));
    }

    @Test
    void returns409OnDuplicateEmail() throws Exception {
        userRepository.save(User.create("bob@example.com", "Bob"));

        mockMvc.perform(post("/api/v1/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"bob@example.com","nickname":"Bob2"}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("DUPLICATE_EMAIL"));
    }

    @Test
    void returns404WhenUserMissing() throws Exception {
        mockMvc.perform(get("/api/v1/users/00000000-0000-0000-0000-000000000000"))
                .andExpect(status().isNotFound());
    }

    @Test
    void updatesUserNickname() throws Exception {
        User user = userRepository.save(User.create("dave@example.com", "Dave"));

        mockMvc.perform(put("/api/v1/users/" + user.getId().value())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"nickname":"DaveUpdated"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nickname").value("DaveUpdated"))
                .andExpect(jsonPath("$.email").value("dave@example.com"));
    }

    @Test
    void deletesUserReturns204() throws Exception {
        User user = userRepository.save(User.create("eve@example.com", "Eve"));

        mockMvc.perform(delete("/api/v1/users/" + user.getId().value()))
                .andExpect(status().isNoContent());
    }

    @Test
    void getCurrentUserResolvesViaJwtSubject() throws Exception {
        // W3 #1 fix — admin's GET /users/me previously routed into
        // GET /users/{id} and returned 400 "Invalid UUID string: me".
        User user = userRepository.save(User.create("me@example.com", "Me"));
        String sub = user.getId().value().toString();

        mockMvc.perform(get("/api/v1/users/me")
                        .with(jwt().jwt(b -> b.subject(sub))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(sub))
                .andExpect(jsonPath("$.email").value("me@example.com"));
    }

    @Test
    void getCurrentUserReturns404WhenSubjectIsNotUuid() throws Exception {
        // Phase 4 / legacy fixture safety: a non-UUID subject must not
        // bubble up as a 500 (Spring's IllegalArgumentException → MVC).
        mockMvc.perform(get("/api/v1/users/me")
                        .with(jwt().jwt(b -> b.subject("alice"))))
                .andExpect(status().isNotFound());
    }

    @Test
    void getCurrentUserReturns404WhenUuidNotInDatabase() throws Exception {
        mockMvc.perform(get("/api/v1/users/me")
                        .with(jwt().jwt(b -> b.subject("00000000-0000-0000-0000-000000000000"))))
                .andExpect(status().isNotFound());
    }
}
