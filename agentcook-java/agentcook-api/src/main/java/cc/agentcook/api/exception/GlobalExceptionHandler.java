package cc.agentcook.api.exception;

import cc.agentcook.api.auth.TurnstileRejectedException;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.application.exception.AccountDisabledException;
import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.exception.DuplicateEmailException;
import cc.agentcook.application.exception.DuplicatePluginException;
import cc.agentcook.application.exception.InvalidCredentialsException;
import cc.agentcook.application.exception.InvalidPluginPackageException;
import cc.agentcook.application.exception.InvalidRefreshTokenException;
import cc.agentcook.application.exception.InvalidRegistrationException;
import cc.agentcook.application.exception.PermissionNotFoundException;
import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.exception.UserAlreadyExistsException;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.domain.service.PluginActivationService.PluginActivationDeniedException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.NestedExceptionUtils;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** Unique constraint on {@code users.email} (V1 migration). */
    private static final String USERS_EMAIL_CONSTRAINT = "uk_users_email";

    @ExceptionHandler(DuplicateEmailException.class)
    public ResponseEntity<ApiError> handleDuplicateEmail(DuplicateEmailException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiError("DUPLICATE_EMAIL", ex.getMessage()));
    }

    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<ApiError> handleUserNotFound(UserNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("USER_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(UnknownSubjectException.class)
    public ResponseEntity<ApiError> handleUnknownSubject(UnknownSubjectException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("USER_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(SessionNotFoundException.class)
    public ResponseEntity<ApiError> handleSessionNotFound(SessionNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("SESSION_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(PluginNotFoundException.class)
    public ResponseEntity<ApiError> handlePluginNotFound(PluginNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("PLUGIN_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(PluginActivationDeniedException.class)
    public ResponseEntity<ApiError> handleActivationDenied(PluginActivationDeniedException ex) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(new ApiError("PLUGIN_ACTIVATION_DENIED", ex.getMessage()));
    }

    @ExceptionHandler(InvalidPluginPackageException.class)
    public ResponseEntity<ApiError> handleInvalidPackage(InvalidPluginPackageException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("INVALID_PLUGIN_PACKAGE", ex.getMessage()));
    }

    @ExceptionHandler(DuplicatePluginException.class)
    public ResponseEntity<ApiError> handleDuplicatePlugin(DuplicatePluginException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiError("DUPLICATE_PLUGIN", ex.getMessage()));
    }

    @ExceptionHandler(ConnectorNotFoundException.class)
    public ResponseEntity<ApiError> handleConnectorNotFound(ConnectorNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("CONNECTOR_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(PermissionNotFoundException.class)
    public ResponseEntity<ApiError> handlePermissionNotFound(PermissionNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ApiError("PERMISSION_NOT_FOUND", ex.getMessage()));
    }

    // --- Authentication -------------------------------------------------

    /** Unknown user, wrong password and password-less account all look the same. */
    @ExceptionHandler(InvalidCredentialsException.class)
    public ResponseEntity<ApiError> handleInvalidCredentials(InvalidCredentialsException ex) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new ApiError("AUTH_INVALID_CREDENTIALS", "Invalid username or password."));
    }

    @ExceptionHandler(AccountDisabledException.class)
    public ResponseEntity<ApiError> handleAccountDisabled(AccountDisabledException ex) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(new ApiError("AUTH_ACCOUNT_DISABLED", ex.getMessage()));
    }

    @ExceptionHandler(UserAlreadyExistsException.class)
    public ResponseEntity<ApiError> handleUserExists(UserAlreadyExistsException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiError("AUTH_USER_EXISTS", ex.getMessage()));
    }

    /** The reason (bad signature, wrong type, user suspended ...) is logged, not returned. */
    @ExceptionHandler(InvalidRefreshTokenException.class)
    public ResponseEntity<ApiError> handleInvalidRefreshToken(InvalidRefreshTokenException ex) {
        log.debug("Refresh rejected: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new ApiError("AUTH_INVALID_REFRESH_TOKEN", "Invalid or expired refresh token."));
    }

    @ExceptionHandler(TurnstileRejectedException.class)
    public ResponseEntity<ApiError> handleTurnstileRejected(TurnstileRejectedException ex) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new ApiError("TURNSTILE_REJECTED", ex.getMessage()));
    }

    /**
     * A write lost a race on a unique constraint (two registrations of the
     * same identity both passing the existence check). The constraint that
     * fired decides the code; anything else is a generic conflict.
     */
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ApiError> handleDataIntegrityViolation(DataIntegrityViolationException ex) {
        String detail = String.valueOf(NestedExceptionUtils.getMostSpecificCause(ex).getMessage());
        if (detail.contains(USERS_EMAIL_CONSTRAINT)) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(new ApiError("AUTH_USER_EXISTS", "An account already exists for this identity."));
        }
        log.warn("Data integrity violation: {}", detail);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiError("DATA_CONFLICT", "The request conflicts with existing data."));
    }

    /**
     * Aggregates reject illegal lifecycle transitions with
     * {@link IllegalStateException} (activating a deleted user, publishing a
     * deprecated plugin): the request conflicts with the resource's state.
     */
    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ApiError> handleIllegalState(IllegalStateException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiError("INVALID_STATE", ex.getMessage()));
    }

    // --- Validation -----------------------------------------------------

    /** Registration rule violations share the bean-validation code. */
    @ExceptionHandler(InvalidRegistrationException.class)
    public ResponseEntity<ApiError> handleInvalidRegistration(InvalidRegistrationException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("VALIDATION_FAILED", ex.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiError> handleIllegalArgument(IllegalArgumentException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("INVALID_ARGUMENT", ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleValidation(MethodArgumentNotValidException ex) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
                .orElse("validation failed");
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("VALIDATION_FAILED", detail));
    }

    /** A path or query parameter that does not convert, e.g. a malformed UUID. */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiError> handleTypeMismatch(MethodArgumentTypeMismatchException ex) {
        String expected = ex.getRequiredType() == null ? "value" : ex.getRequiredType().getSimpleName();
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("INVALID_ARGUMENT", ex.getName() + ": not a valid " + expected));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiError> handleUnreadableBody(HttpMessageNotReadableException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("VALIDATION_FAILED", "Request body is missing or is not valid JSON."));
    }
}
