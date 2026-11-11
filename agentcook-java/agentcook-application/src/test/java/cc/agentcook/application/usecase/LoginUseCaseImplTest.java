package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.AccountDisabledException;
import cc.agentcook.application.exception.InvalidCredentialsException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.LoginCommand;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.time.Instant;
import java.util.Optional;

import static cc.agentcook.application.usecase.AuthTestFixtures.tokensFor;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class LoginUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @Mock private AuthTokenIssuer tokenIssuer;
    private final AuthTestFixtures.FakePasswordHasher hasher = new AuthTestFixtures.FakePasswordHasher();

    @BeforeEach
    void stubCollaborators() {
        when(tokenIssuer.issue(any(User.class))).thenAnswer(inv -> tokensFor(inv.getArgument(0)));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    private LoginUseCaseImpl useCase(boolean autoProvision) {
        return new LoginUseCaseImpl(userRepository, hasher, tokenIssuer, autoProvision);
    }

    private static User userWithPassword(String email, String password, UserStatus status) {
        Instant now = Instant.now();
        return User.reconstitute(UserId.generate(), email, "n", status, now, now, 0, 2,
                "hashed:" + password);
    }

    private static User legacyUser(String email, UserStatus status) {
        Instant now = Instant.now();
        return User.reconstitute(UserId.generate(), email, "n", status, now, now);
    }

    @Test
    void correctPasswordIssuesTokensWithoutWriting() {
        User alice = userWithPassword("alice@dev.local", "s3cret-pw", UserStatus.ACTIVE);
        when(userRepository.findByEmail("alice@dev.local")).thenReturn(Optional.of(alice));

        AuthTokens tokens = useCase(false).execute(new LoginCommand("alice", "s3cret-pw"));

        assertEquals("access-alice@dev.local", tokens.accessToken());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void emailHandleIsLowerCasedBeforeLookup() {
        User alice = userWithPassword("alice@example.com", "s3cret-pw", UserStatus.ACTIVE);
        when(userRepository.findByEmail("alice@example.com")).thenReturn(Optional.of(alice));

        AuthTokens tokens = useCase(false).execute(new LoginCommand(" Alice@Example.COM ", "s3cret-pw"));

        assertEquals("access-alice@example.com", tokens.accessToken());
    }

    @Test
    void wrongPasswordIsRejected() {
        User alice = userWithPassword("alice@dev.local", "s3cret-pw", UserStatus.ACTIVE);
        when(userRepository.findByEmail("alice@dev.local")).thenReturn(Optional.of(alice));

        assertThrows(InvalidCredentialsException.class,
                () -> useCase(true).execute(new LoginCommand("alice", "wrong-pw")));
        verify(tokenIssuer, never()).issue(any());
    }

    @Test
    void suspendedAccountWithCorrectPasswordIsDisabledNotInvalid() {
        User alice = userWithPassword("alice@dev.local", "s3cret-pw", UserStatus.SUSPENDED);
        when(userRepository.findByEmail("alice@dev.local")).thenReturn(Optional.of(alice));

        assertThrows(AccountDisabledException.class,
                () -> useCase(false).execute(new LoginCommand("alice", "s3cret-pw")));
        verify(tokenIssuer, never()).issue(any());
    }

    @Test
    void suspendedAccountWithWrongPasswordLooksLikeAnyOtherFailure() {
        User alice = userWithPassword("alice@dev.local", "s3cret-pw", UserStatus.SUSPENDED);
        when(userRepository.findByEmail("alice@dev.local")).thenReturn(Optional.of(alice));

        assertThrows(InvalidCredentialsException.class,
                () -> useCase(false).execute(new LoginCommand("alice", "guess")));
    }

    @Test
    void unknownUserIsRejectedWhenAutoProvisionIsOff() {
        when(userRepository.findByEmail("ghost@dev.local")).thenReturn(Optional.empty());

        assertThrows(InvalidCredentialsException.class,
                () -> useCase(false).execute(new LoginCommand("ghost", "whatever-pw")));

        verify(userRepository, never()).save(any(User.class));
        assertTrue(hasher.matchCalls.get() >= 1,
                "a rejected login still spends a hash comparison (timing equaliser)");
    }

    @Test
    void unknownUserIsCreatedWithHashedPasswordWhenAutoProvisionIsOn() {
        when(userRepository.findByEmail("newbie@dev.local")).thenReturn(Optional.empty());

        AuthTokens tokens = useCase(true).execute(new LoginCommand("newbie", "first-pw-1"));

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        assertEquals("newbie@dev.local", saved.getValue().getEmail());
        assertEquals("newbie", saved.getValue().getNickname());
        assertEquals("hashed:first-pw-1", saved.getValue().getPasswordHash());
        assertEquals("access-newbie@dev.local", tokens.accessToken());
    }

    @Test
    void legacyRowWithoutPasswordIsRejectedWhenAutoProvisionIsOff() {
        when(userRepository.findByEmail("admin@agentcook.cc"))
                .thenReturn(Optional.of(legacyUser("admin@agentcook.cc", UserStatus.ACTIVE)));

        assertThrows(InvalidCredentialsException.class,
                () -> useCase(false).execute(new LoginCommand("admin@agentcook.cc", "anything")));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void firstLoginClaimsLegacyRowWhenAutoProvisionIsOn() {
        User legacy = legacyUser("old@dev.local", UserStatus.ACTIVE);
        when(userRepository.findByEmail("old@dev.local")).thenReturn(Optional.of(legacy));
        when(userRepository.findByIdForUpdate(legacy.getId())).thenReturn(Optional.of(legacy));

        useCase(true).execute(new LoginCommand("old", "claim-pw-1"));

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        assertEquals(legacy.getId(), saved.getValue().getId());
        assertEquals("hashed:claim-pw-1", saved.getValue().getPasswordHash());
    }

    @Test
    void concurrentClaimIsVerifiedAgainstTheWinnersPassword() {
        User legacy = legacyUser("old@dev.local", UserStatus.ACTIVE);
        Instant now = Instant.now();
        User claimedMeanwhile = User.reconstitute(legacy.getId(), "old@dev.local", "n", UserStatus.ACTIVE,
                now, now, 0, 2, "hashed:winner-pw");
        when(userRepository.findByEmail("old@dev.local")).thenReturn(Optional.of(legacy));
        when(userRepository.findByIdForUpdate(legacy.getId())).thenReturn(Optional.of(claimedMeanwhile));

        assertThrows(InvalidCredentialsException.class,
                () -> useCase(true).execute(new LoginCommand("old", "loser-pw")));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void legacySuspendedRowIsNotClaimed() {
        when(userRepository.findByEmail("old@dev.local"))
                .thenReturn(Optional.of(legacyUser("old@dev.local", UserStatus.SUSPENDED)));

        assertThrows(AccountDisabledException.class,
                () -> useCase(true).execute(new LoginCommand("old", "claim-pw-1")));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void malformedUsernameIsAnInvalidCredential() {
        assertThrows(InvalidCredentialsException.class,
                () -> useCase(true).execute(new LoginCommand("x", "whatever-pw")));
        verify(userRepository, never()).findByEmail(any());
    }
}
