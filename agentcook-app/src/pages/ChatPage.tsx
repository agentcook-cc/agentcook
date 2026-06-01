import { useState, useRef, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { useSseChat } from "@/hooks/useSseChat";
import { useSession } from "@/hooks/useSession";
import VirtualMessageList from "@/components/VirtualMessageList";
import ChatInput from "@/components/ChatInput";
import ChatPluginPicker from "@/components/ChatPluginPicker";
import SessionSidebar from "@/components/SessionSidebar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isError?: boolean;
}

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const logout = useAuthStore((state) => state.clearAuth);

  const { sessions, createSession, loadSessionMessages } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>([]);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const activeAssistantIdRef = useRef<string>("");
  const lastMessageRef = useRef<string>("");

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Load session messages when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    loadSessionMessages(sessionId).then((history) => {
      if (history.length > 0) {
        setMessages(history);
      }
    });
  }, [sessionId, loadSessionMessages]);

  const updateAssistantMessage = useCallback(
    (content: string, isError = false) => {
      const targetId = activeAssistantIdRef.current;
      if (!targetId) return;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === targetId ? { ...msg, content, isError } : msg,
        ),
      );
    },
    [],
  );

  const { send, cancel } = useSseChat({
    onChunk: (accumulated) => {
      setConnectionError(null);
      updateAssistantMessage(accumulated);
    },
    onDone: (finalContent) => {
      updateAssistantMessage(finalContent);
      setIsStreaming(false);
    },
    onError: (errorMessage) => {
      updateAssistantMessage(`Error: ${errorMessage}`, true);
      setIsStreaming(false);
      setConnectionError(errorMessage);
    },
    maxRetries: 3,
    extraBody: {
      session_id: sessionId,
      plugins: selectedPlugins.length > 0 ? selectedPlugins : undefined,
    },
  });

  const handleLogout = useCallback(() => {
    cancel();
    logout();
    navigate("/login", { replace: true });
  }, [cancel, logout, navigate]);

  const handleSend = useCallback(
    async (text: string) => {
      if (isStreaming) return;
      setConnectionError(null);
      lastMessageRef.current = text;

      // Auto-create session if none active
      if (!sessionId) {
        const newId = await createSession(text.slice(0, 50));
        if (newId) {
          navigate(`/chat/${newId}`, { replace: true });
        }
      }

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      const assistantId = crypto.randomUUID();
      activeAssistantIdRef.current = assistantId;

      const assistantMessage: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);

      await send(text);
    },
    [isStreaming, send, sessionId, createSession, navigate],
  );

  const handleRetry = useCallback(async () => {
    if (!lastMessageRef.current || isStreaming) return;
    setConnectionError(null);

    // Remove the last failed assistant message
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      return last?.isError ? prev.slice(0, -1) : prev;
    });

    const assistantId = crypto.randomUUID();
    activeAssistantIdRef.current = assistantId;

    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", timestamp: Date.now() },
    ]);
    setIsStreaming(true);
    await send(lastMessageRef.current);
  }, [isStreaming, send]);

  const handleSelectSession = useCallback(
    (id: string) => {
      navigate(`/chat/${id}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(async () => {
    setMessages([]);
    navigate("/chat");
  }, [navigate]);

  return (
    <div className="flex h-screen bg-white">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
      />

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
          <h1 className="text-lg font-semibold">AgentCook</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">{user?.displayName}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 transition hover:text-gray-600"
            >
              Sign out
            </button>
          </div>
        </header>

        <VirtualMessageList messages={messages} />

        {connectionError && !isStreaming && (
          <div className="flex items-center justify-between border-t border-red-100 bg-red-50 px-4 py-2">
            <span className="text-xs text-red-600">
              Connection lost: {connectionError}
            </span>
            <button
              onClick={handleRetry}
              className="rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        )}

        <div className="flex items-center gap-2 border-t border-gray-100 px-4 py-1.5">
          <ChatPluginPicker selectedIds={selectedPlugins} onChange={setSelectedPlugins} />
        </div>
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
}
