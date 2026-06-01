package cc.agentcook.application.exception;

/**
 * Raised when an uploaded plugin .zip does not contain a valid
 * {@code plugin.json} or fails the minimum-shape check (name /
 * version / kind).
 */
public class InvalidPluginPackageException extends RuntimeException {

    public InvalidPluginPackageException(String detail) {
        super("Invalid plugin package: " + detail);
    }
}
