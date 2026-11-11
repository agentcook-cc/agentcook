package cc.agentcook.api.controller;

import cc.agentcook.api.auth.CurrentUser;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.ConsumeQuotaResponse;
import cc.agentcook.api.dto.QuotaResponse;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.ConsumeQuotaCommand;
import cc.agentcook.application.port.in.ConsumeQuotaUseCase;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Chat quota for the calling user (ADR-018). The Python runtime reads
 * {@code GET} on every chat request to decide whether to route to the
 * default model or downgrade to the cheaper one, and calls
 * {@code POST /consume} — fire-and-forget, with the user's own bearer
 * token — after each completed chat turn.
 *
 * <p>The caller is always the JWT subject (the user's UUID, set when
 * {@code AuthController} issued the token); there is no way to read or
 * spend another user's quota here.</p>
 */
@RestController
@RequestMapping("/api/v1/quota")
@Tag(name = "Quota", description = "Chat quota state (ADR-018).")
public class QuotaController {

    private final UserRepository userRepository;
    private final ConsumeQuotaUseCase consumeQuotaUseCase;

    public QuotaController(UserRepository userRepository, ConsumeQuotaUseCase consumeQuotaUseCase) {
        this.userRepository = userRepository;
        this.consumeQuotaUseCase = consumeQuotaUseCase;
    }

    @GetMapping
    @Operation(summary = "Get the calling user's chat quota state.")
    @ApiResponse(responseCode = "200", description = "Current quota snapshot.",
            content = @Content(schema = @Schema(implementation = QuotaResponse.class)))
    @ApiResponse(responseCode = "401", description = "Missing or invalid Bearer token.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "404", description = "USER_NOT_FOUND — JWT subject does not resolve to a known user.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public QuotaResponse getQuota(Authentication authentication) {
        UserId userId = UserId.from(CurrentUser.from(authentication).requireId());
        return userRepository.findById(userId)
                .map(QuotaResponse::from)
                .orElseThrow(() -> new UserNotFoundException(userId));
    }

    @PostMapping("/consume")
    @Operation(summary = "Record one completed chat turn against the caller's free-tier quota.",
            description = "Atomic per user: concurrent calls are serialised on the user row, so none is lost. "
                    + "An exhausted quota is not an error — the response says `exhausted: true` and the "
                    + "counters are unchanged (ADR-018: the runtime downgrades to the cheaper model).")
    @ApiResponse(responseCode = "200", description = "Quota state after this call.",
            content = @Content(schema = @Schema(implementation = ConsumeQuotaResponse.class)))
    @ApiResponse(responseCode = "401", description = "Missing or invalid Bearer token.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "403", description = "AUTH_ACCOUNT_DISABLED — the account is suspended.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "404", description = "USER_NOT_FOUND — JWT subject does not resolve to a known user.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ConsumeQuotaResponse consume(Authentication authentication) {
        String userId = CurrentUser.from(authentication).requireId().toString();
        return ConsumeQuotaResponse.from(consumeQuotaUseCase.execute(new ConsumeQuotaCommand(userId)));
    }
}
