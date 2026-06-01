package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.user.User;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PermissionRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private PermissionRepositoryAdapter adapter;

    @Autowired
    private UserRepositoryAdapter userAdapter;

    @Test
    void savesAndReadsBackPermission() {
        User user = userAdapter.save(User.create("frank@example.com", "Frank"));
        Permission perm = Permission.grant(user.getId(), "plugin:dingtalk", "activate");

        Permission saved = adapter.save(perm);

        assertTrue(adapter.findById(saved.getId()).isPresent());
        assertTrue(adapter.findById(saved.getId()).get().isAllowed());
    }

    @Test
    void findsByUserIdAndResource() {
        User user = userAdapter.save(User.create("grace@example.com", "Grace"));
        adapter.save(Permission.grant(user.getId(), "plugin:dingtalk", "activate"));
        adapter.save(Permission.deny(user.getId(), "plugin:feishu", "activate"));

        List<Permission> dingtalk = adapter.findByUserIdAndResource(user.getId(), "plugin:dingtalk");

        assertEquals(1, dingtalk.size());
        assertTrue(dingtalk.get(0).isAllowed());
    }
}
