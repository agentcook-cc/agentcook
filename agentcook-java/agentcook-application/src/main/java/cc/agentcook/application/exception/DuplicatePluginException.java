package cc.agentcook.application.exception;

public class DuplicatePluginException extends RuntimeException {

    public DuplicatePluginException(String name, String version) {
        super("Plugin already registered: " + name + " v" + version);
    }
}
