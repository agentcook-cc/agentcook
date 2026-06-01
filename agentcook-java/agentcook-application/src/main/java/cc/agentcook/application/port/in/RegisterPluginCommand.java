package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Input Port command: register a plugin from an uploaded zip package.
 * The bytes are the raw zip (Controller transforms multipart → byte[]).
 */
public record RegisterPluginCommand(String filename, byte[] zipBytes) {

    public RegisterPluginCommand {
        Objects.requireNonNull(filename, "filename must not be null");
        Objects.requireNonNull(zipBytes, "zipBytes must not be null");
    }
}
