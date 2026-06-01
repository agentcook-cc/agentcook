import { useState, useCallback, useEffect } from "react";
import { javaClient } from "@/api/client";
import type { SessionItem } from "@/components/SessionSidebar";

interface SessionMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

interface SessionResponse {
  id: string;
  title: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

interface SessionDetailResponse extends SessionResponse {
  messages?: SessionMessage[];
}

const MOCK_SESSIONS: SessionItem[] = [
  { id: "s1", title: "Help me write a Python script", updatedAt: Date.now() - 3_600_000 },
  { id: "s2", title: "Explain DDD aggregates", updatedAt: Date.now() - 86_400_000 },
  { id: "s3", title: "Review my PR", updatedAt: Date.now() - 172_800_000 },
];

export function useSession() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [useMock, setUseMock] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await javaClient.get<SessionResponse[]>("/api/v1/sessions");
      setSessions(
        data.map((session) => ({
          id: session.id,
          title: session.title || "Untitled",
          updatedAt: new Date(session.updatedAt || session.createdAt).getTime(),
        })),
      );
      setUseMock(false);
    } catch {
      setSessions(MOCK_SESSIONS);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const createSession = useCallback(async (title?: string): Promise<string | null> => {
    try {
      const data = await javaClient.post<SessionResponse>("/api/v1/sessions", {
        title: title || "New conversation",
      });
      const newSession: SessionItem = {
        id: data.id,
        title: data.title || "New conversation",
        updatedAt: Date.now(),
      };
      setSessions((prev) => [newSession, ...prev]);
      return data.id;
    } catch {
      // Fallback: generate a local session ID
      const localId = `local-${crypto.randomUUID().slice(0, 8)}`;
      const newSession: SessionItem = {
        id: localId,
        title: title || "New conversation",
        updatedAt: Date.now(),
      };
      setSessions((prev) => [newSession, ...prev]);
      return localId;
    }
  }, []);

  const loadSessionMessages = useCallback(async (sessionId: string): Promise<SessionMessage[]> => {
    try {
      const data = await javaClient.get<SessionDetailResponse>(`/api/v1/sessions/${sessionId}`);
      return data.messages ?? [];
    } catch {
      return [];
    }
  }, []);

  return {
    sessions,
    loading,
    useMock,
    createSession,
    loadSessionMessages,
    refreshSessions: fetchSessions,
  };
}
