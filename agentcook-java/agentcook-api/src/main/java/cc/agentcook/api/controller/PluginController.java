package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ActivatePluginRequest;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.ConnectorResponse;
import cc.agentcook.api.dto.PluginResponse;
import cc.agentcook.application.port.in.ActivatePluginCommand;
import cc.agentcook.application.port.in.ActivatePluginUseCase;
import cc.agentcook.application.port.in.RegisterPluginCommand;
import cc.agentcook.application.port.in.RegisterPluginUseCase;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.net.URI;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/plugins")
@Tag(name = "Plugins", description = "Plugin registry and activation.")
public class PluginController {

    private final ActivatePluginUseCase activatePluginUseCase;
    private final RegisterPluginUseCase registerPluginUseCase;
    private final PluginRepository pluginRepository;

    public PluginController(ActivatePluginUseCase activatePluginUseCase,
                            RegisterPluginUseCase registerPluginUseCase,
                            PluginRepository pluginRepository) {
        this.activatePluginUseCase = activatePluginUseCase;
        this.registerPluginUseCase = registerPluginUseCase;
        this.pluginRepository = pluginRepository;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "Upload a plugin .zip package and register the plugin metadata.",
            description = "The zip must contain a plugin.json with name / version / kind / description. " +
                    "Sandbox loading + execution lives in the Python runtime per ADR-013 — this " +
                    "endpoint only registers metadata.")
    @ApiResponse(responseCode = "201", description = "Plugin registered.",
            content = @Content(schema = @Schema(implementation = PluginResponse.class)))
    @ApiResponse(responseCode = "400", description = "Zip is missing plugin.json or has invalid manifest.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "409", description = "Plugin name + version already registered.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<PluginResponse> uploadPlugin(@RequestParam("file") MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) {
            return ResponseEntity.badRequest().build();
        }
        Plugin plugin = registerPluginUseCase.execute(
                new RegisterPluginCommand(
                        file.getOriginalFilename() == null ? "plugin.zip" : file.getOriginalFilename(),
                        file.getBytes()));
        return ResponseEntity
                .created(URI.create("/api/v1/plugins/" + plugin.getId().value()))
                .body(PluginResponse.from(plugin));
    }

    @GetMapping
    @Operation(summary = "List plugins, optionally filtered by status.")
    public List<PluginResponse> listPlugins(
            @Parameter(description = "Optional status filter (DRAFT/PUBLISHED/DEPRECATED).")
            @RequestParam(value = "status", required = false) PluginStatus status) {
        var plugins = (status == null)
                ? pluginRepository.findByStatus(PluginStatus.PUBLISHED)
                : pluginRepository.findByStatus(status);
        return plugins.stream().map(PluginResponse::from).toList();
    }

    @PutMapping("/{id}/publish")
    @Operation(summary = "Publish a DRAFT plugin (transitions status to PUBLISHED).")
    @ApiResponse(responseCode = "200", description = "Plugin published.",
            content = @Content(schema = @Schema(implementation = PluginResponse.class)))
    @ApiResponse(responseCode = "404", description = "Plugin not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "409", description = "Plugin cannot be published (already deprecated).",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<PluginResponse> publishPlugin(@PathVariable("id") UUID pluginId) {
        return pluginRepository.findById(PluginId.from(pluginId))
                .map(plugin -> {
                    plugin.publish();
                    Plugin saved = pluginRepository.save(plugin);
                    return ResponseEntity.ok(PluginResponse.from(saved));
                })
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).build());
    }

    @PostMapping("/{id}/activate")
    @Operation(summary = "Activate a plugin for a user — establishes a Connector.")
    @ApiResponse(responseCode = "200", description = "Connector established.",
            content = @Content(schema = @Schema(implementation = ConnectorResponse.class)))
    @ApiResponse(responseCode = "403", description = "User lacks activate permission.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "404", description = "Plugin not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<ConnectorResponse> activate(
            @PathVariable("id") UUID pluginId,
            @Valid @RequestBody ActivatePluginRequest body) {
        ConnectorId connectorId = activatePluginUseCase.execute(new ActivatePluginCommand(
                body.userId(), pluginId.toString(), body.connectorConfig()));
        return ResponseEntity.ok(new ConnectorResponse(connectorId.value(), pluginId, "CONNECTED"));
    }
}
