package cc.agentcook.api.exception;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.exception.DuplicateEmailException;
import cc.agentcook.application.exception.DuplicatePluginException;
import cc.agentcook.application.exception.InvalidPluginPackageException;
import cc.agentcook.application.exception.PermissionNotFoundException;
import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.domain.service.PluginActivationService.PluginActivationDeniedException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

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
}
