package cc.agentcook.domain.permission;

import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class PermissionTest {

    @Test
    void grant_shouldCreateAllowPermission() {
        UserId userId = UserId.generate();
        Permission perm = Permission.grant(userId, "plugin:weather", "activate");

        assertNotNull(perm.getId());
        assertEquals(userId, perm.getUserId());
        assertEquals("plugin:weather", perm.getResource());
        assertEquals("activate", perm.getAction());
        assertEquals(PermissionEffect.ALLOW, perm.getEffect());
        assertTrue(perm.isAllowed());
    }

    @Test
    void deny_shouldCreateDenyPermission() {
        UserId userId = UserId.generate();
        Permission perm = Permission.deny(userId, "plugin:secret", "read");

        assertEquals(PermissionEffect.DENY, perm.getEffect());
        assertFalse(perm.isAllowed());
    }

    @Test
    void grant_withBlankResource_shouldThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> Permission.grant(UserId.generate(), "", "activate"));
    }

    @Test
    void grant_withBlankAction_shouldThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> Permission.grant(UserId.generate(), "plugin:x", ""));
    }

    @Test
    void matches_shouldReturnTrueForExactMatch() {
        Permission perm = Permission.grant(UserId.generate(), "plugin:weather", "activate");
        assertTrue(perm.matches("plugin:weather", "activate"));
        assertFalse(perm.matches("plugin:weather", "delete"));
        assertFalse(perm.matches("plugin:other", "activate"));
    }

    @Test
    void equals_sameId_shouldBeEqual() {
        PermissionId id = PermissionId.generate();
        Permission p1 = Permission.reconstitute(id, UserId.generate(), "r1", "a1", PermissionEffect.ALLOW, java.time.Instant.now());
        Permission p2 = Permission.reconstitute(id, UserId.generate(), "r2", "a2", PermissionEffect.DENY, java.time.Instant.now());
        assertEquals(p1, p2);
    }
}
