package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserStatus;
import cc.agentcook.infrastructure.persistence.jpa.JpaUserRepository;
import cc.agentcook.infrastructure.persistence.mapper.UserEntityMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class UserRepositoryAdapter implements UserRepository {

    private final JpaUserRepository jpa;
    private final UserEntityMapper mapper;

    public UserRepositoryAdapter(JpaUserRepository jpa, UserEntityMapper mapper) {
        this.jpa = jpa;
        this.mapper = mapper;
    }

    @Override
    @Cacheable(value = "users", key = "#id.value()")
    public Optional<User> findById(UserId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override
    public Optional<User> findByEmail(String email) {
        return jpa.findByEmail(email).map(mapper::toDomain);
    }

    @Override
    public List<User> findAll() {
        return jpa.findAll().stream().map(mapper::toDomain).toList();
    }

    @Override
    public List<User> findByStatus(UserStatus status) {
        return jpa.findByStatus(status).stream().map(mapper::toDomain).toList();
    }

    @Override
    @CacheEvict(value = "users", key = "#user.id.value()")
    public User save(User user) {
        return mapper.toDomain(jpa.save(mapper.toEntity(user)));
    }

    @Override
    @CacheEvict(value = "users", key = "#id.value()")
    public void delete(UserId id) {
        jpa.deleteById(id.value());
    }

    @Override
    public boolean existsByEmail(String email) {
        return jpa.existsByEmail(email);
    }
}
