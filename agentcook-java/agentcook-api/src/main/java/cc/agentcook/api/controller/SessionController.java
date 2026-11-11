package cc.agentcook.api.controller;

import cc.agentcook.api.auth.CurrentUser;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.CreateSessionRequest;
import cc.agentcook.api.dto.SessionResponse;
import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.CreateSessionCommand;
import cc.agentcook.application.port.in.CreateSessionUseCase;
import cc.agentcook.application.port.in.ListSessionsQuery;
import cc.agentcook.application.port.in.ListSessionsUseCase;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.UserId;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;
import java.util.UUID;

/**
 * Conversation sessions. Every session belongs to one user: callers see
 * and create only their own, admins may act for anyone. Another user's
 * session — or another user as owner — is answered with the same 404 as
 * a missing one, so ids cannot be probed.
 */
@RestController
@RequestMapping("/api/v1/sessions")
@Tag(name = "Sessions", description = "Conversation session lifecycle (owner or admin only).")
public class SessionController {

    private final CreateSessionUseCase createSessionUseCase;
    private final ListSessionsUseCase listSessionsUseCase;
    private final SessionRepository sessionRepository;

    public SessionController(CreateSessionUseCase createSessionUseCase,
                             ListSessionsUseCase listSessionsUseCase,
                             SessionRepository sessionRepository) {
        this.createSessionUseCase = createSessionUseCase;
        this.listSessionsUseCase = listSessionsUseCase;
        this.sessionRepository = sessionRepository;
    }

    @GetMapping
    @Operation(summary = "List a user's sessions. Defaults to the caller; other users' lists are admin-only.")
    @ApiResponse(responseCode = "404", description = "USER_NOT_FOUND — another user's id requested by a non-admin.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public List<SessionResponse> listSessions(
            @Parameter(description = "User id (uuid). Optional — defaults to the JWT subject.")
            @RequestParam(value = "userId", required = false) UUID userId,
            Authentication authentication) {
        UUID owner = resolveOwner(userId, CurrentUser.from(authentication));
        return listSessionsUseCase.execute(new ListSessionsQuery(owner.toString())).stream()
                .map(SessionResponse::from)
                .toList();
    }

    @PostMapping
    @Operation(summary = "Open a new conversation session. Owner defaults to the JWT subject when body.userId "
            + "is omitted; only admins may open a session for another user.")
    @ApiResponse(responseCode = "201", description = "Session created.",
            content = @Content(schema = @Schema(implementation = SessionResponse.class)))
    @ApiResponse(responseCode = "400", description = "INVALID_ARGUMENT — body.userId is not a UUID.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "404", description = "USER_NOT_FOUND — owner missing or not the caller.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<SessionResponse> createSession(@Valid @RequestBody CreateSessionRequest body,
                                                         Authentication authentication) {
        UUID requested = (body.userId() == null || body.userId().isBlank())
                ? null
                : UUID.fromString(body.userId().trim());
        UUID owner = resolveOwner(requested, CurrentUser.from(authentication));
        SessionId id = createSessionUseCase.execute(new CreateSessionCommand(owner.toString(), body.title()));
        SessionResponse response = sessionRepository.findById(id).map(SessionResponse::from).orElseThrow();
        return ResponseEntity.created(URI.create("/api/v1/sessions/" + id.value())).body(response);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Fetch a session by id (owner or admin).")
    @ApiResponse(responseCode = "200", description = "Session found.",
            content = @Content(schema = @Schema(implementation = SessionResponse.class)))
    @ApiResponse(responseCode = "404", description = "SESSION_NOT_FOUND — missing or owned by another user.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public SessionResponse getSession(@PathVariable("id") UUID id, Authentication authentication) {
        CurrentUser caller = CurrentUser.from(authentication);
        SessionId sessionId = SessionId.from(id);
        return sessionRepository.findById(sessionId)
                .filter(session -> caller.canAccess(session.getUserId().value()))
                .map(SessionResponse::from)
                .orElseThrow(() -> new SessionNotFoundException(sessionId));
    }

    /**
     * The user a request acts for: the caller when none is named, the named
     * user when the caller is that user or an admin. Naming anyone else is
     * answered like an unknown user.
     */
    private static UUID resolveOwner(UUID requested, CurrentUser caller) {
        if (requested == null) {
            return caller.requireId();
        }
        if (!caller.canAccess(requested)) {
            throw new UserNotFoundException(UserId.from(requested));
        }
        return requested;
    }
}
