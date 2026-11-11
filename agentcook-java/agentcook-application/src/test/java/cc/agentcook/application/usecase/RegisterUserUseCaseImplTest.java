package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.InvalidRegistrationException;
import cc.agentcook.application.exception.UserAlreadyExistsException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.RegisterUserCommand;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.domain.user.User;
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
class RegisterUserUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @Mock private AuthTokenIssuer tokenIssuer;
    private RegisterUserUseCaseImpl useCase;

    @BeforeEach
    void setUp() {
        useCase = new RegisterUserUseCaseImpl(userRepository, new AuthTestFixtures.FakePasswordHasher(), tokenIssuer);
        when(tokenIssuer.issue(any(User.class))).thenAnswer(inv -> tokensFor(inv.getArgument(0)));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    @Test
    void registersBareUsernameUnderSyntheticAddressAndStoresOnlyTheHash() {
        AuthTokens tokens = useCase.execute(new RegisterUserCommand("alice", "correct-horse", null));

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        User user = saved.getValue();
        assertEquals("alice@dev.local", user.getEmail());
        assertEquals("alice", user.getNickname());
        assertEquals("hashed:correct-horse", user.getPasswordHash());
        assertEquals(UserStatus.ACTIVE, user.getStatus());
        assertEquals("access-alice@dev.local", tokens.accessToken());
    }

    @Test
    void registersLowerCasedEmailWithExplicitNickname() {
        useCase.execute(new RegisterUserCommand("Bob@Example.com", "correct-horse", "  Bobby "));

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        assertEquals("bob@example.com", saved.getValue().getEmail());
        assertEquals("Bobby", saved.getValue().getNickname());
    }

    @Test
    void rejectsExistingIdentity() {
        when(userRepository.existsByEmail("alice@dev.local")).thenReturn(true);

        assertThrows(UserAlreadyExistsException.class,
                () -> useCase.execute(new RegisterUserCommand("alice", "correct-horse", null)));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void enforcesPasswordLengthBounds() {
        InvalidRegistrationException tooShort = assertThrows(InvalidRegistrationException.class,
                () -> useCase.execute(new RegisterUserCommand("alice", "short", null)));
        assertTrue(tooShort.getMessage().startsWith("password: "), tooShort.getMessage());
        assertThrows(InvalidRegistrationException.class,
                () -> useCase.execute(new RegisterUserCommand("alice", "x".repeat(129), null)));
        verify(userRepository, never()).save(any(User.class));

        useCase.execute(new RegisterUserCommand("alice", "x".repeat(8), null));
        useCase.execute(new RegisterUserCommand("alice2", "x".repeat(128), null));
    }

    @Test
    void rejectsInvalidUsername() {
        InvalidRegistrationException invalid = assertThrows(InvalidRegistrationException.class,
                () -> useCase.execute(new RegisterUserCommand("a b", "correct-horse", null)));
        assertTrue(invalid.getMessage().startsWith("username: "), invalid.getMessage());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void commandToStringNeverContainsThePassword() {
        String rendered = new RegisterUserCommand("alice", "correct-horse", null).toString();
        assertEquals(-1, rendered.indexOf("correct-horse"));
    }
}
