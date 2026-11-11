package cc.agentcook.api.auth;

import cc.agentcook.application.port.out.PasswordHasher;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/**
 * {@link PasswordHasher} adapter backed by Spring Security's
 * {@link BCryptPasswordEncoder} (cost 10, random salt per hash, constant-time
 * comparison). Lives in the api module because that is where Spring
 * Security is on the classpath.
 *
 * <p>BCrypt only reads the first 72 bytes of its input, and newer Spring
 * Security releases refuse longer inputs outright. The API accepts up to
 * 128 characters (up to 512 UTF-8 bytes), so a password longer than 72
 * bytes is first reduced to its Base64 SHA-256 digest (44 bytes): every
 * character still counts, and the same reduction is applied when
 * verifying. Passwords of 72 bytes or less are hashed unchanged.</p>
 */
@Component
public class BCryptPasswordHasher implements PasswordHasher {

    static final int BCRYPT_MAX_BYTES = 72;

    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();

    @Override
    public String hash(String rawPassword) {
        return encoder.encode(bcryptInput(rawPassword));
    }

    @Override
    public boolean matches(String rawPassword, String passwordHash) {
        if (rawPassword == null || passwordHash == null || passwordHash.isBlank()) {
            return false;
        }
        try {
            return encoder.matches(bcryptInput(rawPassword), passwordHash);
        } catch (IllegalArgumentException malformed) {
            return false;
        }
    }

    static String bcryptInput(String rawPassword) {
        byte[] bytes = rawPassword.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= BCRYPT_MAX_BYTES) {
            return rawPassword;
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            return Base64.getEncoder().encodeToString(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is required by every Java runtime", e);
        }
    }
}
