package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.GrantPermissionRequest;
import cc.agentcook.api.dto.PermissionResponse;
import cc.agentcook.application.port.in.GrantPermissionCommand;
import cc.agentcook.application.port.in.GrantPermissionUseCase;
import cc.agentcook.application.port.in.ListPermissionsByUserQuery;
import cc.agentcook.application.port.in.ListPermissionsByUserUseCase;
import cc.agentcook.application.port.in.RevokePermissionCommand;
import cc.agentcook.application.port.in.RevokePermissionUseCase;
import cc.agentcook.domain.permission.Permission;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;
import java.util.UUID;

/**
 * Permission CRUD. Note the path split:
 * <ul>
 *   <li>{@code /api/v1/users/{userId}/permissions} — list / grant
 *       under a user (admin scope is the user)</li>
 *   <li>{@code /api/v1/permissions/{id}} — revoke a single permission
 *       by its own id (not user-scoped because the user-id is implied
 *       by the permission record)</li>
 * </ul>
 *
 * <p>Per ADR-013 the Java domain has no Role aggregate; admin "role
 * management" is rendered by the frontend as a Permission view (a
 * matrix of resource × action grouped by user). The single-permission
 * grant endpoint is what B's PermissionGroupView calls per change.</p>
 */
@RestController
@Tag(name = "Permissions", description = "Permission CRUD (RBAC building blocks).")
public class PermissionController {

    private final ListPermissionsByUserUseCase listPermissionsByUserUseCase;
    private final GrantPermissionUseCase grantPermissionUseCase;
    private final RevokePermissionUseCase revokePermissionUseCase;

    public PermissionController(ListPermissionsByUserUseCase listPermissionsByUserUseCase,
                                GrantPermissionUseCase grantPermissionUseCase,
                                RevokePermissionUseCase revokePermissionUseCase) {
        this.listPermissionsByUserUseCase = listPermissionsByUserUseCase;
        this.grantPermissionUseCase = grantPermissionUseCase;
        this.revokePermissionUseCase = revokePermissionUseCase;
    }

    @GetMapping("/api/v1/users/{userId}/permissions")
    @Operation(summary = "List a user's permissions.")
    public List<PermissionResponse> listForUser(@PathVariable("userId") UUID userId) {
        return listPermissionsByUserUseCase.execute(new ListPermissionsByUserQuery(userId.toString())).stream()
                .map(PermissionResponse::from)
                .toList();
    }

    @PostMapping("/api/v1/users/{userId}/permissions")
    @Operation(summary = "Grant or deny a permission to the user.")
    @ApiResponse(responseCode = "201", description = "Permission created.",
            content = @Content(schema = @Schema(implementation = PermissionResponse.class)))
    public ResponseEntity<PermissionResponse> grantForUser(
            @PathVariable("userId") UUID userId,
            @Valid @RequestBody GrantPermissionRequest body) {
        Permission permission = grantPermissionUseCase.execute(new GrantPermissionCommand(
                userId.toString(), body.resource(), body.action(), body.effect()));
        return ResponseEntity
                .created(URI.create("/api/v1/permissions/" + permission.getId().value()))
                .body(PermissionResponse.from(permission));
    }

    @DeleteMapping("/api/v1/permissions/{permissionId}")
    @Operation(summary = "Revoke (delete) a permission by id.")
    @ApiResponse(responseCode = "204", description = "Permission revoked.")
    @ApiResponse(responseCode = "404", description = "Permission not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<Void> revoke(@PathVariable("permissionId") UUID permissionId) {
        revokePermissionUseCase.execute(new RevokePermissionCommand(permissionId.toString()));
        return ResponseEntity.noContent().build();
    }
}
