package cc.agentcook.application.port.in;

import cc.agentcook.domain.session.Session;

public interface UpdateSessionUseCase {

    Session execute(UpdateSessionCommand command);
}
