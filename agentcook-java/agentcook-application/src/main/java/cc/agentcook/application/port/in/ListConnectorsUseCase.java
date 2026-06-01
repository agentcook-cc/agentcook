package cc.agentcook.application.port.in;

import cc.agentcook.domain.connector.Connector;

import java.util.List;

public interface ListConnectorsUseCase {

    List<Connector> execute(ListConnectorsQuery query);
}
