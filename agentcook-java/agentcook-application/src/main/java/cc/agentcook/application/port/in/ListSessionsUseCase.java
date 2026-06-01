package cc.agentcook.application.port.in;

import cc.agentcook.domain.session.Session;

import java.util.List;

public interface ListSessionsUseCase {

    List<Session> execute(ListSessionsQuery query);
}
