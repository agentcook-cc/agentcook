package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.DuplicatePluginException;
import cc.agentcook.application.exception.InvalidPluginPackageException;
import cc.agentcook.application.port.in.RegisterPluginCommand;
import cc.agentcook.application.port.in.RegisterPluginUseCase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Phase 3 plugin registration: extract {@code plugin.json} from the
 * uploaded zip, validate the minimum shape, create the {@link Plugin}
 * aggregate. Sandbox loading + execution lives in the Python runtime
 * (per ADR-013) — this use case only registers metadata.
 *
 * <p>File-system persistence of the zip itself lands Day 28+ once we
 * pick a backend (local fs / minio / s3). Today we just validate +
 * register the metadata so B's Plugin CRUD UI can demo end-to-end.</p>
 */
@Service
@Transactional
public class RegisterPluginUseCaseImpl implements RegisterPluginUseCase {

    private static final ObjectMapper JSON = new ObjectMapper();

    private final PluginRepository pluginRepository;

    public RegisterPluginUseCaseImpl(PluginRepository pluginRepository) {
        this.pluginRepository = pluginRepository;
    }

    @Override
    public Plugin execute(RegisterPluginCommand command) {
        JsonNode manifest = readManifestFromZip(command.zipBytes());

        String name = requireText(manifest, "name");
        String version = requireText(manifest, "version");
        PluginKind kind = parseKind(manifest);
        String description = manifest.path("description").asText(null);

        if (pluginRepository.findByNameAndVersion(name, version).isPresent()) {
            throw new DuplicatePluginException(name, version);
        }

        Plugin plugin = Plugin.create(name, version, kind, description);
        return pluginRepository.save(plugin);
    }

    private static JsonNode readManifestFromZip(byte[] zipBytes) {
        try (ZipInputStream zin = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry entry;
            while ((entry = zin.getNextEntry()) != null) {
                if (!entry.isDirectory() && entry.getName().endsWith("plugin.json")) {
                    return JSON.readTree(zin.readAllBytes());
                }
            }
        } catch (IOException e) {
            throw new InvalidPluginPackageException("zip is corrupt: " + e.getMessage());
        }
        throw new InvalidPluginPackageException("plugin.json not found in zip");
    }

    private static String requireText(JsonNode manifest, String field) {
        JsonNode node = manifest.path(field);
        if (node.isMissingNode() || node.isNull() || node.asText().isBlank()) {
            throw new InvalidPluginPackageException("plugin.json missing required field: " + field);
        }
        return node.asText();
    }

    private static PluginKind parseKind(JsonNode manifest) {
        String raw = requireText(manifest, "kind");
        try {
            return PluginKind.valueOf(raw.toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new InvalidPluginPackageException(
                    "kind must be one of MCP/HTTP/OAUTH/WEBHOOK, got: " + raw);
        }
    }
}
