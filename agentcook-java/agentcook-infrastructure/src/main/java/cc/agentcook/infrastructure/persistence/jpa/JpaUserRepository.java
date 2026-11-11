package cc.agentcook.infrastructure.persistence.jpa;

import cc.agentcook.domain.user.UserStatus;
import cc.agentcook.infrastructure.persistence.entity.UserEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface JpaUserRepository extends JpaRepository<UserEntity, UUID> {

    Optional<UserEntity> findByEmail(String email);

    /**
     * {@code SELECT ... FOR UPDATE} on the user row — see
     * {@link cc.agentcook.domain.user.UserRepository#findByIdForUpdate}.
     */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select u from UserEntity u where u.id = :id")
    Optional<UserEntity> findByIdForUpdate(@Param("id") UUID id);

    List<UserEntity> findByStatus(UserStatus status);

    boolean existsByEmail(String email);
}
