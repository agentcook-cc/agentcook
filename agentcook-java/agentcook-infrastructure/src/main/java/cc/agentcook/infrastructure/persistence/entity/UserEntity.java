package cc.agentcook.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @Column(name = "id", columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "email", nullable = false, unique = true, length = 255)
    private String email;

    @Column(name = "nickname", length = 255)
    private String nickname;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private cc.agentcook.domain.user.UserStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    // Day 56 / ADR-018 — chat quota counters. DB defaults come from V4
    // migration; the in-memory defaults (0 / 2) keep test fixtures that
    // construct UserEntity directly from going negative or unset.
    @Column(name = "free_questions_used", nullable = false)
    private int freeQuestionsUsed;

    @Column(name = "free_questions_quota", nullable = false)
    private int freeQuestionsQuota;

    protected UserEntity() {
    }

    public UserEntity(UUID id, String email, String nickname,
                      cc.agentcook.domain.user.UserStatus status,
                      Instant createdAt, Instant updatedAt,
                      int freeQuestionsUsed, int freeQuestionsQuota) {
        this.id = id;
        this.email = email;
        this.nickname = nickname;
        this.status = status;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.freeQuestionsUsed = freeQuestionsUsed;
        this.freeQuestionsQuota = freeQuestionsQuota;
    }

    public UUID getId() { return id; }
    public String getEmail() { return email; }
    public String getNickname() { return nickname; }
    public cc.agentcook.domain.user.UserStatus getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public int getFreeQuestionsUsed() { return freeQuestionsUsed; }
    public int getFreeQuestionsQuota() { return freeQuestionsQuota; }

    public void setEmail(String email) { this.email = email; }
    public void setNickname(String nickname) { this.nickname = nickname; }
    public void setStatus(cc.agentcook.domain.user.UserStatus status) { this.status = status; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
    public void setFreeQuestionsUsed(int freeQuestionsUsed) { this.freeQuestionsUsed = freeQuestionsUsed; }
    public void setFreeQuestionsQuota(int freeQuestionsQuota) { this.freeQuestionsQuota = freeQuestionsQuota; }
}
