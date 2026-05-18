package cc.agentcook.domain.plugin;

import cc.agentcook.domain.plugin.event.PluginPublishedEvent;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Plugin Aggregate Root.
 * Manages plugin registration, versioning, and lifecycle transitions.
 */
public class Plugin {

    private final PluginId id;
    private String name;
    private String version;
    private PluginKind kind;
    private String description;
    private PluginStatus status;
    private final Instant createdAt;
    private Instant updatedAt;

    private final List<Object> domainEvents = new ArrayList<>();

    private Plugin(PluginId id, String name, String version, PluginKind kind, String description, PluginStatus status, Instant createdAt, Instant updatedAt) {
        this.id = Objects.requireNonNull(id, "id must not be null");
        this.name = Objects.requireNonNull(name, "name must not be null");
        this.version = Objects.requireNonNull(version, "version must not be null");
        this.kind = Objects.requireNonNull(kind, "kind must not be null");
        this.description = description;
        this.status = Objects.requireNonNull(status, "status must not be null");
        this.createdAt = Objects.requireNonNull(createdAt, "createdAt must not be null");
        this.updatedAt = Objects.requireNonNull(updatedAt, "updatedAt must not be null");
    }

    /**
     * Factory: create a new Plugin in DRAFT status.
     */
    public static Plugin create(String name, String version, PluginKind kind, String description) {
        if (name == null || name.isBlank()) throw new IllegalArgumentException("name must not be blank");
        if (version == null || version.isBlank()) throw new IllegalArgumentException("version must not be blank");
        PluginId id = PluginId.generate();
        Instant now = Instant.now();
        return new Plugin(id, name, version, kind, description, PluginStatus.DRAFT, now, now);
    }

    /**
     * Reconstitute from persistence (no events raised).
     */
    public static Plugin reconstitute(PluginId id, String name, String version, PluginKind kind, String description, PluginStatus status, Instant createdAt, Instant updatedAt) {
        return new Plugin(id, name, version, kind, description, status, createdAt, updatedAt);
    }

    public void publish() {
        if (this.status == PluginStatus.DEPRECATED) {
            throw new IllegalStateException("Cannot publish a deprecated plugin");
        }
        this.status = PluginStatus.PUBLISHED;
        this.updatedAt = Instant.now();
        this.domainEvents.add(new PluginPublishedEvent(id, name, version, Instant.now()));
    }

    public void deprecate() {
        if (this.status != PluginStatus.PUBLISHED) {
            throw new IllegalStateException("Only published plugins can be deprecated");
        }
        this.status = PluginStatus.DEPRECATED;
        this.updatedAt = Instant.now();
    }

    public void updateDescription(String description) {
        this.description = description;
        this.updatedAt = Instant.now();
    }

    // --- Getters ---

    public PluginId getId() { return id; }
    public String getName() { return name; }
    public String getVersion() { return version; }
    public PluginKind getKind() { return kind; }
    public String getDescription() { return description; }
    public PluginStatus getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public List<Object> getDomainEvents() {
        return Collections.unmodifiableList(domainEvents);
    }

    public void clearDomainEvents() {
        domainEvents.clear();
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        Plugin plugin = (Plugin) other;
        return id.equals(plugin.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public String toString() {
        return "Plugin{id=" + id + ", name='" + name + "', version='" + version + "', status=" + status + "}";
    }
}
