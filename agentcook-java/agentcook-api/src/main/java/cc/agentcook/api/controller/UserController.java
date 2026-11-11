package cc.agentcook.api.controller;

import cc.agentcook.api.auth.CurrentUser;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.CreateUserRequest;
import cc.agentcook.api.dto.CurrentUserResponse;
import cc.agentcook.api.dto.UpdateUserRequest;
import cc.agentcook.api.dto.UserResponse;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.ActivateUserCommand;
import cc.agentcook.application.port.in.ActivateUserUseCase;
import cc.agentcook.application.port.in.CreateUserCommand;
import cc.agentcook.application.port.in.CreateUserUseCase;
import cc.agentcook.application.port.in.ListUsersQuery;
import cc.agentcook.application.port.in.ListUsersUseCase;
import cc.agentcook.application.port.in.SuspendUserCommand;
import cc.agentcook.application.port.in.SuspendUserUseCase;
import cc.agentcook.application.port.in.UpdateUserCommand;
import cc.agentcook.application.port.in.UpdateUserUseCase;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserStatus;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;
import java.util.UUID;

/**
 * User aggregate endpoints. {@code GET /me} is open to every authenticated
 * caller; everything else is user management and requires
 * {@code ROLE_ADMIN} (see {@link cc.agentcook.api.config.SecurityConfig}).
 */
@RestController
@RequestMapping("/api/v1/users")
@Tag(name = "Users", description = "User aggregate lifecycle.")
public class UserController {

    private final CreateUserUseCase createUserUseCase;
    private final UpdateUserUseCase updateUserUseCase;
    private final SuspendUserUseCase suspendUserUseCase;
    private final ActivateUserUseCase activateUserUseCase;
    private final ListUsersUseCase listUsersUseCase;
    private final UserRepository userRepository;

    public UserController(CreateUserUseCase createUserUseCase,
                          UpdateUserUseCase updateUserUseCase,
                          SuspendUserUseCase suspendUserUseCase,
                          ActivateUserUseCase activateUserUseCase,
                          ListUsersUseCase listUsersUseCase,
                          UserRepository userRepository) {
        this.createUserUseCase = createUserUseCase;
        this.updateUserUseCase = updateUserUseCase;
        this.suspendUserUseCase = suspendUserUseCase;
        this.activateUserUseCase = activateUserUseCase;
        this.listUsersUseCase = listUsersUseCase;
        this.userRepository = userRepository;
    }

    @GetMapping
    @Operation(summary = "List users, optionally filtered by status.")
    public List<UserResponse> listUsers(
            @Parameter(description = "Optional status filter (ACTIVE/SUSPENDED/DELETED).")
            @RequestParam(value = "status", required = false) UserStatus status) {
        return listUsersUseCase.execute(new ListUsersQuery(status)).stream()
                .map(UserResponse::from)
                .toList();
    }

    @PostMapping
    @Operation(summary = "Register a new user.")
    @ApiResponse(responseCode = "201", description = "User created.",
            content = @Content(schema = @Schema(implementation = UserResponse.class)))
    @ApiResponse(responseCode = "409", description = "Email already exists.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest body) {
        UserId id = createUserUseCase.execute(new CreateUserCommand(body.email(), body.nickname()));
        UserResponse response = userRepository.findById(id).map(UserResponse::from).orElseThrow();
        return ResponseEntity.created(URI.create("/api/v1/users/" + id.value())).body(response);
    }

    @GetMapping("/me")
    @Operation(summary = "Fetch the currently-authenticated user and the roles of the presented token. "
            + "JWT subject is the user UUID.")
    @ApiResponse(responseCode = "200", description = "User found.",
            content = @Content(schema = @Schema(implementation = CurrentUserResponse.class)))
    @ApiResponse(responseCode = "404", description = "USER_NOT_FOUND — JWT subject does not resolve to a known user.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public CurrentUserResponse getCurrentUser(Authentication authentication) {
        CurrentUser caller = CurrentUser.from(authentication);
        UserId id = UserId.from(caller.requireId());
        return userRepository.findById(id)
                .map(user -> CurrentUserResponse.from(user, caller.roles()))
                .orElseThrow(() -> new UserNotFoundException(id));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Fetch a user by id.")
    @ApiResponse(responseCode = "200", description = "User found.",
            content = @Content(schema = @Schema(implementation = UserResponse.class)))
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public UserResponse getUser(@PathVariable("id") UUID id) {
        UserId userId = UserId.from(id);
        return userRepository.findById(userId)
                .map(UserResponse::from)
                .orElseThrow(() -> new UserNotFoundException(userId));
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update a user's profile (nickname).")
    @ApiResponse(responseCode = "200", description = "User updated.",
            content = @Content(schema = @Schema(implementation = UserResponse.class)))
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<UserResponse> updateUser(
            @PathVariable("id") UUID id,
            @Valid @RequestBody UpdateUserRequest body) {
        var updated = updateUserUseCase.execute(new UpdateUserCommand(id.toString(), body.nickname()));
        return ResponseEntity.ok(UserResponse.from(updated));
    }

    @PutMapping("/{id}/suspend")
    @Operation(summary = "Suspend a user: login, refresh and quota consumption are refused until re-activated.")
    @ApiResponse(responseCode = "200", description = "User suspended.",
            content = @Content(schema = @Schema(implementation = UserResponse.class)))
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public UserResponse suspendUser(@PathVariable("id") UUID id) {
        return UserResponse.from(suspendUserUseCase.execute(new SuspendUserCommand(id.toString())));
    }

    @PutMapping("/{id}/activate")
    @Operation(summary = "Re-activate a suspended user.")
    @ApiResponse(responseCode = "200", description = "User active.",
            content = @Content(schema = @Schema(implementation = UserResponse.class)))
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public UserResponse activateUser(@PathVariable("id") UUID id) {
        return UserResponse.from(activateUserUseCase.execute(new ActivateUserCommand(id.toString())));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Soft-delete (suspend) a user.")
    @ApiResponse(responseCode = "204", description = "User suspended.")
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<Void> deleteUser(@PathVariable("id") UUID id) {
        suspendUserUseCase.execute(new SuspendUserCommand(id.toString()));
        return ResponseEntity.noContent().build();
    }
}
