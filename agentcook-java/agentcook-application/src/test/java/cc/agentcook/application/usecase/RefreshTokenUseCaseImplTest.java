package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.InvalidRefreshTokenException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.RefreshTokenCommand;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static cc.agentcook.application.usecase.AuthTestFixtures.tokensFor;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RefreshTokenUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @Mock private AuthTokenIssuer tokenIssuer;
    @InjectMocks private RefreshTokenUseCaseImpl useCase;

    @Test
    void validRefreshTokenForActiveUserIssuesNewPair() {
        User user = User.create("alice@dev.local", "alice");
        when(tokenIssuer.verifyRefreshToken("rt")).thenReturn(user.getId());
        when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
        when(tokenIssuer.issue(user)).thenReturn(tokensFor(user));

        AuthTokens tokens = useCase.execute(new RefreshTokenCommand("rt"));

        assertEquals("access-alice@dev.local", tokens.accessToken());
    }

    @Test
    void invalidTokenPropagatesWithoutLookingUpTheUser() {
        when(tokenIssuer.verifyRefreshToken("bad")).thenThrow(new InvalidRefreshTokenException("bad signature"));

        assertThrows(InvalidRefreshTokenException.class, () -> useCase.execute(new RefreshTokenCommand("bad")));
        verify(userRepository, never()).findById(any());
    }

    @Test
    void deletedUserCannotRefresh() {
        UserId gone = UserId.generate();
        when(tokenIssuer.verifyRefreshToken("rt")).thenReturn(gone);
        when(userRepository.findById(gone)).thenReturn(Optional.empty());

        assertThrows(InvalidRefreshTokenException.class, () -> useCase.execute(new RefreshTokenCommand("rt")));
        verify(tokenIssuer, never()).issue(any());
    }

    @Test
    void suspendedUserCannotRefresh() {
        User user = User.create("alice@dev.local", "alice");
        user.suspend();
        when(tokenIssuer.verifyRefreshToken("rt")).thenReturn(user.getId());
        when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));

        assertThrows(InvalidRefreshTokenException.class, () -> useCase.execute(new RefreshTokenCommand("rt")));
        verify(tokenIssuer, never()).issue(any());
    }
}
