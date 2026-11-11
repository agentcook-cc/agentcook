package cc.agentcook.api.auth;

/**
 * Cloudflare Turnstile did not confirm the caller is human (only raised
 * when {@code agentcook.turnstile.secret} is configured). Surfaced as
 * 401 {@code TURNSTILE_REJECTED}, the code the Python runtime uses for
 * the same check on chat requests.
 */
public class TurnstileRejectedException extends RuntimeException {

    public TurnstileRejectedException() {
        super("Turnstile verification failed");
    }
}
