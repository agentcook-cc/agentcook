package cc.agentcook.infrastructure.persistence.jpa;

import cc.agentcook.domain.user.UserStatus;
import cc.agentcook.infrastructure.persistence.entity.UserEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface JpaUserRepository extends JpaRepository<UserEntity, UUID> {

    Optional<UserEntity> findByEmail(String email);

    List<UserEntity> findByStatus(UserStatus status);

    boolean existsByEmail(String email);
}
