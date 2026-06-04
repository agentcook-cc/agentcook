package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.CreateSessionRequest;
import cc.agentcook.api.dto.SessionResponse;
import cc.agentcook.application.port.in.CreateSessionCommand;
import cc.agentcook.application.port.in.CreateSessionUseCase;
import cc.agentcook.application.port.in.ListSessionsQuery;
import cc.agentcook.application.port.in.ListSessionsUseCase;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
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

@RestController
@RequestMapping("/api/v1/sessions")
@Tag(name = "Sessions", description = "Conversation session lifecycle.")
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
    @Operation(summary = "List sessions for a given user.")
    public List<SessionResponse> listSessions(
            @Parameter(description = "User id (uuid).", required = true)
            @RequestParam("userId") String userId) {
        return listSessionsUseCase.execute(new ListSessionsQuery(userId)).stream()
                .map(SessionResponse::from)
                .toList();
    }

    @PostMapping
    @Operation(summary = "Open a new conversation session. Owner defaults to the JWT subject when body.userId is omitted.")
    @ApiResponse(responseCode = "201", description = "Session created.",
            content = @Content(schema = @Schema(implementation = SessionResponse.class)))
    @ApiResponse(responseCode = "404", description = "User not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<SessionResponse> createSession(@Valid @RequestBody CreateSessionRequest body,
                                                         Authentication authentication) {
        String userId = (body.userId() == null || body.userId().isBlank())
                ? authentication.getName()
                : body.userId();
        SessionId id = createSessionUseCase.execute(new CreateSessionCommand(userId, body.title()));
        SessionResponse response = sessionRepository.findById(id).map(SessionResponse::from).orElseThrow();
        return ResponseEntity.created(URI.create("/api/v1/sessions/" + id.value())).body(response);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Fetch a session by id.")
    public ResponseEntity<SessionResponse> getSession(@PathVariable("id") UUID id) {
        return sessionRepository.findById(SessionId.from(id))
                .map(SessionResponse::from)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).build());
    }
}
