package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionId;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.infrastructure.persistence.jpa.JpaPermissionRepository;
import cc.agentcook.infrastructure.persistence.mapper.PermissionEntityMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class PermissionRepositoryAdapter implements PermissionRepository {

    private final JpaPermissionRepository jpa;
    private final PermissionEntityMapper mapper;

    public PermissionRepositoryAdapter(JpaPermissionRepository jpa, PermissionEntityMapper mapper) {
        this.jpa = jpa;
        this.mapper = mapper;
    }

    @Override
    public Optional<Permission> findById(PermissionId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override
    public List<Permission> findByUserId(UserId userId) {
        return jpa.findAll().stream()
                .filter(p -> p.getUserId().equals(userId.value()))
                .map(mapper::toDomain)
                .toList();
    }

    @Override
    public List<Permission> findByUserIdAndResource(UserId userId, String resource) {
        return jpa.findByUserIdAndResource(userId.value(), resource).stream()
                .map(mapper::toDomain)
                .toList();
    }

    @Override
    public Permission save(Permission permission) {
        return mapper.toDomain(jpa.save(mapper.toEntity(permission)));
    }

    @Override
    public void delete(PermissionId id) {
        jpa.deleteById(id.value());
    }
}
