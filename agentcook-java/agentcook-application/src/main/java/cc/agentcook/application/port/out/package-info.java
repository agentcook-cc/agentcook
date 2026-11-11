/**
 * Output Ports (secondary / driven): the application's outbound contracts.
 *
 * <p>By DDD convention the domain Repository interfaces under
 * {@code cc.agentcook.domain.{user,session,plugin,connector,permission}}
 * <em>are</em> the outbound ports. We do not redeclare them here to avoid
 * over-abstraction; infrastructure adapters implement those domain
 * interfaces directly.</p>
 *
 * <p>This package hosts the non-repository outbound ports:
 * {@link cc.agentcook.application.port.out.PasswordHasher} and
 * {@link cc.agentcook.application.port.out.AuthTokenIssuer}. Their adapters
 * live next to Spring Security in {@code agentcook-api}
 * ({@code cc.agentcook.api.auth}), which already owns the JWT signing key
 * shared with the resource-server decoder.</p>
 */
package cc.agentcook.application.port.out;
