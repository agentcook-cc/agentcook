package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.DuplicateEmailException;
import cc.agentcook.application.port.in.CreateUserCommand;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CreateUserUseCaseImplTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private CreateUserUseCaseImpl useCase;

    @Test
    void createsUserWhenEmailIsNew() {
        when(userRepository.existsByEmail("alice@example.com")).thenReturn(false);
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        UserId id = useCase.execute(new CreateUserCommand("alice@example.com", "Alice"));

        assertNotNull(id);
        verify(userRepository).save(any(User.class));
    }

    @Test
    void rejectsBlankEmailFromDomainInvariant() {
        when(userRepository.existsByEmail("")).thenReturn(false);

        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new CreateUserCommand("", "Alice")));

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void rejectsDuplicateEmail() {
        when(userRepository.existsByEmail("alice@example.com")).thenReturn(true);

        assertThrows(DuplicateEmailException.class,
                () -> useCase.execute(new CreateUserCommand("alice@example.com", "Alice")));

        verify(userRepository, never()).save(any(User.class));
    }
}
