package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.ConnectorPingResponse;
import cc.agentcook.api.dto.ConnectorResponse;
import cc.agentcook.api.dto.CreateConnectorRequest;
import cc.agentcook.api.dto.UpdateConnectorConfigRequest;
import cc.agentcook.application.port.in.CreateConnectorCommand;
import cc.agentcook.application.port.in.CreateConnectorUseCase;
import cc.agentcook.application.port.in.DeleteConnectorCommand;
import cc.agentcook.application.port.in.DeleteConnectorUseCase;
import cc.agentcook.application.port.in.ListConnectorsQuery;
import cc.agentcook.application.port.in.ListConnectorsUseCase;
import cc.agentcook.application.port.in.PingConnectorCommand;
import cc.agentcook.application.port.in.PingConnectorResult;
import cc.agentcook.application.port.in.PingConnectorUseCase;
import cc.agentcook.application.port.in.UpdateConnectorConfigCommand;
import cc.agentcook.application.port.in.UpdateConnectorConfigUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
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

@RestController
@RequestMapping("/api/v1/connectors")
@Tag(name = "Connectors", description = "Connector lifecycle (admin path).")
public class ConnectorController {

    private final ListConnectorsUseCase listConnectorsUseCase;
    private final CreateConnectorUseCase createConnectorUseCase;
    private final UpdateConnectorConfigUseCase updateConnectorConfigUseCase;
    private final DeleteConnectorUseCase deleteConnectorUseCase;
    private final PingConnectorUseCase pingConnectorUseCase;
    private final ConnectorRepository connectorRepository;

    public ConnectorController(ListConnectorsUseCase listConnectorsUseCase,
                               CreateConnectorUseCase createConnectorUseCase,
                               UpdateConnectorConfigUseCase updateConnectorConfigUseCase,
                               DeleteConnectorUseCase deleteConnectorUseCase,
                               PingConnectorUseCase pingConnectorUseCase,
                               ConnectorRepository connectorRepository) {
        this.listConnectorsUseCase = listConnectorsUseCase;
        this.createConnectorUseCase = createConnectorUseCase;
        this.updateConnectorConfigUseCase = updateConnectorConfigUseCase;
        this.deleteConnectorUseCase = deleteConnectorUseCase;
        this.pingConnectorUseCase = pingConnectorUseCase;
        this.connectorRepository = connectorRepository;
    }

    @GetMapping
    @Operation(summary = "List connectors for a given plugin.")
    public List<ConnectorResponse> listConnectors(
            @Parameter(description = "Plugin id (uuid).")
            @RequestParam("pluginId") String pluginId) {
        return listConnectorsUseCase.execute(new ListConnectorsQuery(pluginId)).stream()
                .map(ConnectorResponse::from)
                .toList();
    }

    @PostMapping
    @Operation(summary = "Create (establish) a Connector for an existing Plugin.")
    @ApiResponse(responseCode = "201", description = "Connector established.",
            content = @Content(schema = @Schema(implementation = ConnectorResponse.class)))
    @ApiResponse(responseCode = "404", description = "Plugin not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<ConnectorResponse> createConnector(@Valid @RequestBody CreateConnectorRequest body) {
        Connector connector = createConnectorUseCase.execute(
                new CreateConnectorCommand(body.pluginId(), body.connectorConfig()));
        return ResponseEntity
                .created(URI.create("/api/v1/connectors/" + connector.getId().value()))
                .body(ConnectorResponse.from(connector));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Fetch a connector by id.")
    public ResponseEntity<ConnectorResponse> getConnector(@PathVariable("id") UUID id) {
        return connectorRepository.findById(ConnectorId.from(id))
                .map(ConnectorResponse::from)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).build());
    }

    @PutMapping("/{id}/config")
    @Operation(summary = "Update a Connector's configuration JSON.")
    @ApiResponse(responseCode = "200", description = "Config updated.",
            content = @Content(schema = @Schema(implementation = ConnectorResponse.class)))
    @ApiResponse(responseCode = "404", description = "Connector not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<ConnectorResponse> updateConfig(
            @PathVariable("id") UUID id,
            @Valid @RequestBody UpdateConnectorConfigRequest body) {
        Connector updated = updateConnectorConfigUseCase.execute(
                new UpdateConnectorConfigCommand(id.toString(), body.config()));
        return ResponseEntity.ok(ConnectorResponse.from(updated));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete a Connector.")
    @ApiResponse(responseCode = "204", description = "Connector deleted.")
    @ApiResponse(responseCode = "404", description = "Connector not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<Void> deleteConnector(@PathVariable("id") UUID id) {
        deleteConnectorUseCase.execute(new DeleteConnectorCommand(id.toString()));
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/ping")
    @Operation(summary = "Ping the Connector and record a health check.",
            description = "Phase 3 returns mock latency; Phase 4 swaps in real upstream IM SDK probes.")
    @ApiResponse(responseCode = "200", description = "Ping completed.",
            content = @Content(schema = @Schema(implementation = ConnectorPingResponse.class)))
    @ApiResponse(responseCode = "404", description = "Connector not found.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<ConnectorPingResponse> pingConnector(@PathVariable("id") UUID id) {
        PingConnectorResult result = pingConnectorUseCase.execute(new PingConnectorCommand(id.toString()));
        return ResponseEntity.ok(ConnectorPingResponse.from(result));
    }
}
