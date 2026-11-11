package cc.agentcook.domain.user;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class LoginIdentityTest {

    @Test
    void bareUsername_mapsToSyntheticDevLocalAddress() {
        LoginIdentity identity = LoginIdentity.parse("alice");
        assertEquals("alice@dev.local", identity.email());
        assertEquals("alice", identity.username());
    }

    @Test
    void bareUsername_keepsCase_forCompatibilityWithExistingRows() {
        assertEquals("Bob_1.x-y@dev.local", LoginIdentity.parse("Bob_1.x-y").email());
    }

    @Test
    void email_isLowerCasedAndTrimmed() {
        LoginIdentity identity = LoginIdentity.parse("  Alice.Smith@Example.COM ");
        assertEquals("alice.smith@example.com", identity.email());
        assertEquals("alice.smith", identity.username());
    }

    @Test
    void devLocalEmail_isTheSameIdentityAsTheBareUsername() {
        assertEquals(LoginIdentity.parse("carol").email(),
                LoginIdentity.parse("carol@dev.local").email());
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   ", "ab", "this-username-is-way-too-long-for-us", "has space", "emoji☺",
            "semi;colon"})
    void invalidBareUsernames_areRejected(String handle) {
        assertThrows(IllegalArgumentException.class, () -> LoginIdentity.parse(handle));
    }

    @ParameterizedTest
    @ValueSource(strings = {"@example.com", "alice@", "a@b@c", "al ice@example.com"})
    void invalidEmails_areRejected(String handle) {
        assertThrows(IllegalArgumentException.class, () -> LoginIdentity.parse(handle));
    }

    @Test
    void nullHandle_isRejected() {
        assertThrows(IllegalArgumentException.class, () -> LoginIdentity.parse(null));
    }

    @Test
    void localPart_returnsTextBeforeLastAt() {
        assertEquals("alice", LoginIdentity.localPart("alice@dev.local"));
        assertEquals("plain", LoginIdentity.localPart("plain"));
    }

    @Test
    void handleOf_isTheBareUsernameForSyntheticAddressesAndTheEmailOtherwise() {
        assertEquals("alice", LoginIdentity.handleOf("alice@dev.local"));
        assertEquals("alice@example.com", LoginIdentity.handleOf("alice@example.com"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"alice", "Bob_1.x-y", "carol@example.com"})
    void handleOf_parsesBackToTheSameAccount(String handle) {
        String email = LoginIdentity.parse(handle).email();
        assertEquals(email, LoginIdentity.parse(LoginIdentity.handleOf(email)).email());
    }
}
