package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class PermissionControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;
    @Autowired private PermissionRepository permissionRepository;

    @Test
    void grantsAndListsPermissionForUser() throws Exception {
        User user = userRepository.save(User.create("alice@example.com", "Alice"));

        mockMvc.perform(post("/api/v1/users/{userId}/permissions", user.getId().value())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"resource":"plugin:dingtalk","action":"activate","effect":"ALLOW"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().exists("Location"))
                .andExpect(jsonPath("$.resource").value("plugin:dingtalk"))
                .andExpect(jsonPath("$.effect").value("ALLOW"));

        mockMvc.perform(get("/api/v1/users/{userId}/permissions", user.getId().value()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].resource").value("plugin:dingtalk"));
    }

    @Test
    void revokesPermissionAndReturns204() throws Exception {
        User user = userRepository.save(User.create("bob@example.com", "Bob"));
        Permission permission = permissionRepository.save(
                Permission.grant(user.getId(), "plugin:feishu", "activate"));

        mockMvc.perform(delete("/api/v1/permissions/{permissionId}", permission.getId().value()))
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/v1/users/{userId}/permissions", user.getId().value()))
                .andExpect(jsonPath("$.length()").value(0));
    }

    @Test
    void revokingUnknownPermissionReturns404() throws Exception {
        mockMvc.perform(delete("/api/v1/permissions/{permissionId}", "00000000-0000-0000-0000-000000000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("PERMISSION_NOT_FOUND"));
    }
}
