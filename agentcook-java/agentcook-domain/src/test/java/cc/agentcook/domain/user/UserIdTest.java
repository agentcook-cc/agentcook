package cc.agentcook.domain.user;

import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class UserIdTest {

    @Test
    void generate_shouldCreateUniqueIds() {
        UserId id1 = UserId.generate();
        UserId id2 = UserId.generate();
        assertNotEquals(id1, id2);
    }

    @Test
    void fromUuid_shouldPreserveValue() {
        UUID raw = UUID.randomUUID();
        UserId id = UserId.from(raw);
        assertEquals(raw, id.value());
    }

    @Test
    void fromString_shouldParseValidUuid() {
        String raw = "550e8400-e29b-41d4-a716-446655440000";
        UserId id = UserId.from(raw);
        assertEquals(UUID.fromString(raw), id.value());
    }

    @Test
    void fromNull_shouldThrow() {
        assertThrows(NullPointerException.class, () -> UserId.from((UUID) null));
    }

    @Test
    void equals_symmetry() {
        UUID raw = UUID.randomUUID();
        UserId id1 = UserId.from(raw);
        UserId id2 = UserId.from(raw);
        assertEquals(id1, id2);
        assertEquals(id2, id1);
        assertEquals(id1.hashCode(), id2.hashCode());
    }

    @Test
    void toString_shouldContainUuid() {
        UUID raw = UUID.randomUUID();
        UserId id = UserId.from(raw);
        assertTrue(id.toString().contains(raw.toString()));
    }
}
