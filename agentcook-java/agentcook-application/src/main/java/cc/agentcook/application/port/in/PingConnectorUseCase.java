package cc.agentcook.application.port.in;

public interface PingConnectorUseCase {

    PingConnectorResult execute(PingConnectorCommand command);
}
