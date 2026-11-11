package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.AccountDisabledException;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.ConsumeQuotaCommand;
import cc.agentcook.application.port.in.QuotaConsumption;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ConsumeQuotaUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @InjectMocks private ConsumeQuotaUseCaseImpl useCase;

    @Test
    void underQuotaConsumesOneQuestionThroughTheLockedRead() {
        User user = User.create("q@example.com", "Q");
        when(userRepository.findByIdForUpdate(user.getId())).thenReturn(Optional.of(user));
        when(userRepository.save(user)).thenReturn(user);

        QuotaConsumption result = useCase.execute(new ConsumeQuotaCommand(user.getId().value().toString()));

        assertFalse(result.exhausted());
        assertEquals(1, result.used());
        assertEquals(User.DEFAULT_FREE_QUOTA, result.quota());
        assertEquals(User.DEFAULT_FREE_QUOTA - 1, result.remaining());
        verify(userRepository).save(user);
        verify(userRepository, never()).findById(any());
    }

    @Test
    void exhaustedQuotaIsNotAnErrorAndWritesNothing() {
        User user = User.create("q@example.com", "Q");
        for (int i = 0; i < User.DEFAULT_FREE_QUOTA; i++) {
            user.consumeFreeQuestion();
        }
        when(userRepository.findByIdForUpdate(user.getId())).thenReturn(Optional.of(user));

        QuotaConsumption result = useCase.execute(new ConsumeQuotaCommand(user.getId().value().toString()));

        assertTrue(result.exhausted());
        assertEquals(User.DEFAULT_FREE_QUOTA, result.used());
        assertEquals(0, result.remaining());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void unknownUserIsNotFound() {
        UserId id = UserId.generate();
        when(userRepository.findByIdForUpdate(id)).thenReturn(Optional.empty());

        assertThrows(UserNotFoundException.class,
                () -> useCase.execute(new ConsumeQuotaCommand(id.value().toString())));
    }

    @Test
    void suspendedUserIsDisabled() {
        User user = User.create("q@example.com", "Q");
        user.suspend();
        when(userRepository.findByIdForUpdate(user.getId())).thenReturn(Optional.of(user));

        assertThrows(AccountDisabledException.class,
                () -> useCase.execute(new ConsumeQuotaCommand(user.getId().value().toString())));
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void malformedUserIdIsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new ConsumeQuotaCommand("not-a-uuid")));
    }
}
