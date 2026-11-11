package cc.agentcook.domain.user;

import java.util.Locale;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * Value Object: the account identity behind a login handle.
 *
 * <p>Users sign in with either an e-mail address or a bare username. Both
 * resolve to the {@link User#getEmail() email} the aggregate is keyed on:</p>
 * <ul>
 *   <li>a handle containing {@code '@'} is an e-mail address and is
 *       lower-cased ({@code Alice@Example.com → alice@example.com});</li>
 *   <li>anything else is a bare username matching
 *       {@code ^[A-Za-z0-9_.-]{3,32}$} and maps to the synthetic address
 *       {@code <username>@dev.local} — the convention the original dev
 *       login used, kept so rows it created stay reachable.</li>
 * </ul>
 *
 * @param email    canonical account e-mail (the {@code users.email} value)
 * @param username display handle: the bare username, or the e-mail's local part
 */
public record LoginIdentity(String email, String username) {

    /** Domain appended to bare usernames. */
    public static final String SYNTHETIC_EMAIL_DOMAIN = "dev.local";

    private static final Pattern USERNAME = Pattern.compile("^[A-Za-z0-9_.-]{3,32}$");
    private static final Pattern EMAIL = Pattern.compile("^[^@\\s]+@[^@\\s]+$");
    private static final int MAX_EMAIL_LENGTH = 255;

    public LoginIdentity {
        Objects.requireNonNull(email, "email must not be null");
        Objects.requireNonNull(username, "username must not be null");
    }

    /**
     * Normalise a login handle.
     *
     * @throws IllegalArgumentException when the handle is blank, not a
     *         plausible e-mail address, or not a valid bare username
     */
    public static LoginIdentity parse(String handle) {
        if (handle == null || handle.isBlank()) {
            throw new IllegalArgumentException("username must not be blank");
        }
        String trimmed = handle.trim();
        if (trimmed.indexOf('@') >= 0) {
            String email = trimmed.toLowerCase(Locale.ROOT);
            if (email.length() > MAX_EMAIL_LENGTH || !EMAIL.matcher(email).matches()) {
                throw new IllegalArgumentException("username is not a valid e-mail address");
            }
            return new LoginIdentity(email, localPart(email));
        }
        if (!USERNAME.matcher(trimmed).matches()) {
            throw new IllegalArgumentException(
                    "username must be 3-32 characters of letters, digits, '_', '.' or '-'");
        }
        return new LoginIdentity(trimmed + "@" + SYNTHETIC_EMAIL_DOMAIN, trimmed);
    }

    /** The part of an e-mail address before the last {@code '@'} (whole value if none). */
    public static String localPart(String email) {
        int at = email.lastIndexOf('@');
        return at < 0 ? email : email.substring(0, at);
    }

    /**
     * The handle a user signs in with for a stored account e-mail: the bare
     * username for synthetic {@code <username>@dev.local} addresses, the
     * e-mail address itself otherwise. {@code parse(handleOf(email))}
     * resolves back to the same account.
     */
    public static String handleOf(String email) {
        return email.endsWith("@" + SYNTHETIC_EMAIL_DOMAIN) ? localPart(email) : email;
    }
}
