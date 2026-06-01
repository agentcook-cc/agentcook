/**
 * Hand-written Domain ↔ JPA Entity mappers.
 *
 * <p>{@code toDomain} uses {@code reconstitute()} to rebuild aggregates
 * <em>without</em> raising domain events (the entity is from persistence,
 * the event was raised at original creation time and already published).</p>
 */
package cc.agentcook.infrastructure.persistence.mapper;
