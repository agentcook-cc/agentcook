/**
 * Repository Adapters: bridge Domain Repository ports to Spring Data JPA.
 *
 * <p>Each adapter implements a {@code domain.*.XxxRepository} interface
 * and delegates to {@code JpaXxxRepository} via an {@code XxxEntityMapper}.
 * Domain code never sees JPA Entity types.</p>
 */
package cc.agentcook.infrastructure.persistence.adapter;
