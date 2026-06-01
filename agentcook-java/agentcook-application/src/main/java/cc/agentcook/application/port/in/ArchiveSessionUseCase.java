package cc.agentcook.application.port.in;

import cc.agentcook.domain.session.Session;

/**
 * Input Port: archive a session (move from ACTIVE → ARCHIVED).
 * Only non-deleted sessions may be archived; the domain enforces it.
 */
public interface ArchiveSessionUseCase {

    Session execute(ArchiveSessionCommand command);
}
