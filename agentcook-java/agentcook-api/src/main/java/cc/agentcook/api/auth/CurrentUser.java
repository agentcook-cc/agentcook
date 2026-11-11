package cc.agentcook.api.auth;

import cc.agentcook.api.exception.UnknownSubjectException;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;

import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * The caller of a request, as far as data-level authorization cares:
 * their user id (the JWT {@code sub}) and the roles their access token
 * carries. Controllers use {@link #canAccess(UUID)} to hide other users'
 * resources — answering 404 rather than 403 so ids cannot be probed for
 * existence.
 *
 * @param id    caller's user id, or {@code null} for anonymous callers and
 *              subjects that are not user ids (they own nothing)
 * @param roles lower-cased role names from the {@code ROLE_*} authorities,
 *              e.g. {@code ["user", "admin"]}
 */
public record CurrentUser(UUID id, List<String> roles) {

    private static final String ROLE_PREFIX = "ROLE_";

    public CurrentUser {
        roles = List.copyOf(roles);
    }

    public static CurrentUser from(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()
                || authentication instanceof AnonymousAuthenticationToken) {
            return new CurrentUser(null, List.of());
        }
        List<String> roles = authentication.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .filter(authority -> authority.startsWith(ROLE_PREFIX))
                .map(authority -> authority.substring(ROLE_PREFIX.length()).toLowerCase(Locale.ROOT))
                .distinct()
                .toList();
        return new CurrentUser(parseUuid(authentication.getName()), roles);
    }

    /**
     * The caller's user id.
     *
     * @throws UnknownSubjectException when the token subject is not a user id
     */
    public UUID requireId() {
        if (id == null) {
            throw new UnknownSubjectException();
        }
        return id;
    }

    /** Whether the caller may act on any user's resources. */
    public boolean admin() {
        return roles.contains(JwtTokenIssuer.ROLE_ADMIN);
    }

    /** Admins may access anything; everyone else only what they own. */
    public boolean canAccess(UUID ownerId) {
        return admin() || (id != null && id.equals(ownerId));
    }

    private static UUID parseUuid(String subject) {
        if (subject == null) {
            return null;
        }
        try {
            return UUID.fromString(subject);
        } catch (IllegalArgumentException notAUserId) {
            return null;
        }
    }
}
