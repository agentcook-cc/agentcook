package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

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
}
