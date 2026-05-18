import { useState, useRef, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { useSseChat } from "@/hooks/useSseChat";
import MessageBubble from "@/components/MessageBubble";
import ChatInput from "@/components/ChatInput";
import SessionSidebar, { type SessionItem } from "@/components/SessionSidebar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isError?: boolean;
}

// Mock sessions for now — will be replaced with API call after Day 24
const MOCK_SESSIONS: SessionItem[] = [
  { id: "s1", title: "Help me write a Python script", updatedAt: Date.now() - 3_600_000 },
  { id: "s2", title: "Explain DDD aggregates", updatedAt: Date.now() - 86_400_000 },
  { id: "s3", title: "Review my PR", updatedAt: Date.now() - 172_800_000 },
];

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const logout = useAuthStore((state) => state.clearAuth);

  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeAssistantIdRef = useRef<string>("");

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    onChunk: (accumulated) => updateAssistantMessage(accumulated),
    onDone: (finalContent) => {
      updateAssistantMessage(finalContent);
      setIsStreaming(false);
    },
    onError: (errorMessage) => {
      updateAssistantMessage(`Error: ${errorMessage}`, true);
      setIsStreaming(false);
    },
    maxRetries: 3,
  });

  const handleLogout = useCallback(() => {
    cancel();
    logout();
    navigate("/login", { replace: true });
  }, [cancel, logout, navigate]);

  const handleSend = useCallback(
    async (text: string) => {
      if (isStreaming) return;

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
    [isStreaming, send],
  );

  const handleSelectSession = useCallback(
    (id: string) => {
      navigate(`/chat/${id}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    navigate("/chat");
  }, [navigate]);

  return (
    <div className="flex h-screen bg-white">
      <SessionSidebar
        sessions={MOCK_SESSIONS}
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

        <main className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-2xl space-y-1">
            {messages.length === 0 && (
              <div className="py-20 text-center text-gray-400">
                <p className="text-2xl font-medium">Hello!</p>
                <p className="mt-2">How can I help you today?</p>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                variant={msg.role === "user" ? "user" : msg.content === "" ? "loading" : "assistant"}
                content={msg.isError ? `⚠️ ${msg.content}` : msg.content}
                timestamp={msg.timestamp}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </main>

        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
}
