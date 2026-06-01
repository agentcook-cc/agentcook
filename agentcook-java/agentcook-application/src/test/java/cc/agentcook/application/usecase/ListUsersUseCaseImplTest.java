package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListUsersQuery;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ListUsersUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @InjectMocks private ListUsersUseCaseImpl useCase;

    private static User dummyUser(UserStatus status) {
        return User.reconstitute(UserId.generate(), "u@example.com", "U",
                status, Instant.now(), Instant.now());
    }

    @Test
    void listsAllUsersWhenStatusFilterIsNull() {
        when(userRepository.findAll()).thenReturn(List.of(
                dummyUser(UserStatus.ACTIVE),
                dummyUser(UserStatus.SUSPENDED)));

        List<User> users = useCase.execute(new ListUsersQuery(null));

        assertEquals(2, users.size());
        verify(userRepository, never()).findByStatus(UserStatus.ACTIVE);
    }

    @Test
    void listsOnlyMatchingStatusWhenFilterProvided() {
        when(userRepository.findByStatus(UserStatus.ACTIVE)).thenReturn(List.of(
                dummyUser(UserStatus.ACTIVE)));

        List<User> users = useCase.execute(new ListUsersQuery(UserStatus.ACTIVE));

        assertEquals(1, users.size());
        verify(userRepository, never()).findAll();
    }

    @Test
    void returnsEmptyListWhenNoUsersMatch() {
        when(userRepository.findByStatus(UserStatus.DELETED)).thenReturn(List.of());

        List<User> users = useCase.execute(new ListUsersQuery(UserStatus.DELETED));

        assertEquals(0, users.size());
    }
}
