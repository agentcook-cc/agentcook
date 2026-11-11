package cc.agentcook.application.port.out;

/**
 * Output Port: one-way password hashing.
 *
 * <p>The application layer only ever hands raw passwords to this port
 * and stores what it returns on the {@code User} aggregate; the algorithm
 * (BCrypt today) is an adapter detail. Implementations must produce
 * salted, slow hashes and compare in constant time.</p>
 */
public interface PasswordHasher {

    /** Hash a raw password for storage. */
    String hash(String rawPassword);

    /**
     * Check a raw password against a stored hash. Returns {@code false}
     * (never throws) for a null, blank or malformed hash.
     */
    boolean matches(String rawPassword, String passwordHash);
}
