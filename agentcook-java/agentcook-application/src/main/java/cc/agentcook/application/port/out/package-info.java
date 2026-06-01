/**
 * Output Ports (secondary / driven): the application's outbound contracts.
 *
 * <p>By DDD convention the domain Repository interfaces under
 * {@code cc.agentcook.domain.{user,session,plugin,connector,permission}}
 * <em>are</em> the outbound ports. We do not redeclare them here to avoid
 * over-abstraction; infrastructure adapters implement those domain
 * interfaces directly.</p>
 *
 * <p>This package will host non-repository outbound ports as they emerge
 * (e.g. external gateways, message publishers).</p>
 */
package cc.agentcook.application.port.out;
