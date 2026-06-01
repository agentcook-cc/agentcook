package cc.agentcook.application.port.in;

import cc.agentcook.domain.plugin.Plugin;

import java.util.List;

public interface ListPluginsUseCase {

    List<Plugin> execute(ListPluginsQuery query);
}
