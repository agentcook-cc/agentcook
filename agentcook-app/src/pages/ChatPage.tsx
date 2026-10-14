import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { newSessionId, runtimeApi, type ConversationSummary } from "@/api/runtime";
import AgentPicker from "@/components/AgentPicker";
import ChatInput from "@/components/ChatInput";
import ChatPluginPicker from "@/components/ChatPluginPicker";
import SessionSidebar from "@/components/SessionSidebar";
import VirtualMessageList from "@/components/VirtualMessageList";
import { transcriptToMessages, useAgentChat } from "@/hooks/useAgentChat";
import { useQuota } from "@/hooks/useQuota";
import { useAgents, useConversations, useRuntimeInfo } from "@/hooks/useRuntimeData";
import { useTurnstile } from "@/hooks/useTurnstile";
import { useAuthStore } from "@/stores/auth";

export default function ChatPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const runtime = useRuntimeInfo();
  const authMode = runtime.data?.auth_mode;
  const canUseApi = authMode !== undefined && (authMode !== "required" || isAuthenticated);

  const agents = useAgents(canUseApi);
  const conversations = useConversations(canUseApi);
  const quota = useQuota(isAuthenticated && canUseApi);
  const turnstile = useTurnstile();

  const [agent, setAgent] = useState<string | undefined>(undefined);
  const [pluginIds, setPluginIds] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Session id we created client-side for an in-flight first turn; its
  // route change must not trigger a transcript reload mid-stream.
  const localSessionRef = useRef<string | null>(null);

  const chat = useAgentChat({ onTurnFinished: conversations.refresh });
  const { reset } = chat;

  useEffect(() => {
    if (authMode === "required" && !isAuthenticated) navigate("/login", { replace: true });
  }, [authMode, isAuthenticated, navigate]);

  const agentList = useMemo(() => agents.data?.items ?? [], [agents.data]);
  const currentAgent = agentList.find((a) => a.name === agent) ?? agentList.find((a) => a.default);

  useEffect(() => {
    if (!canUseApi) return;
    setLoadError(null);
    if (!sessionId) {
      localSessionRef.current = null;
      reset([]);
      return;
    }
    if (localSessionRef.current === sessionId) return;
    let cancelled = false;
    runtimeApi
      .getConversation(sessionId)
      .then((data) => {
        if (cancelled) return;
        reset(transcriptToMessages(data.messages));
        setAgent(data.session.agent);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          // Fresh id (e.g. a bookmarked new chat) — start empty.
          reset([]);
        } else {
          setLoadError(t("chat.loadFailed"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, canUseApi, reset, t]);

  const handleSend = useCallback(
    (text: string) => {
      if (chat.streaming) return;
      let sid = sessionId;
      if (!sid) {
        sid = newSessionId();
        localSessionRef.current = sid;
        navigate(`/chat/${sid}`, { replace: true });
      }
      const headers: Record<string, string> = {};
      if (turnstile.token) headers["X-Turnstile-Token"] = turnstile.token;
      void chat
        .send({
          sessionId: sid,
          text,
          agent: currentAgent?.name,
          pluginIds,
          headers,
        })
        .then(() => quota.refetch());
    },
    [chat, sessionId, navigate, turnstile.token, currentAgent?.name, pluginIds, quota],
  );

  const handleNewChat = useCallback(() => {
    localSessionRef.current = null;
    navigate("/chat");
  }, [navigate]);

  const handleDelete = useCallback(
    async (session: ConversationSummary) => {
      if (!window.confirm(t("session.deleteConfirm", { title: session.title }))) return;
      await conversations.remove(session.id);
      if (session.id === sessionId) handleNewChat();
    },
    [conversations, sessionId, handleNewChat, t],
  );

  const handleSignOut = useCallback(() => {
    void chat.stop();
    clearAuth();
    navigate(authMode === "required" ? "/login" : "/chat", { replace: true });
  }, [chat, clearAuth, navigate, authMode]);

  const examples = useMemo(() => (t("chat.examples", { returnObjects: true }) as string[]) ?? [], [t]);

  return (
    <div className="flex h-screen bg-white">
      <SessionSidebar
        sessions={conversations.conversations}
        activeSessionId={sessionId}
        loading={conversations.loading}
        onSelect={(id) => navigate(`/chat/${id}`)}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-gray-200 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="text-lg font-semibold">AgentCook</h1>
            <AgentPicker
              agents={agentList}
              value={currentAgent?.name}
              onChange={setAgent}
              disabled={chat.streaming || chat.messages.length > 0}
            />
            {runtime.data?.mock_model && (
              <span
                className="hidden rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 sm:inline"
                title={t("runtime.mockHint")}
                data-testid="mock-badge"
              >
                {t("runtime.mock")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            {isAuthenticated ? (
              <>
                <span className="hidden text-gray-500 sm:inline">{user?.displayName}</span>
                <button onClick={handleSignOut} className="text-gray-400 transition hover:text-gray-600">
                  {t("auth.signOut")}
                </button>
              </>
            ) : (
              <button onClick={() => navigate("/login")} className="text-blue-600 hover:underline">
                {t("auth.signIn")}
              </button>
            )}
          </div>
        </header>

        {runtime.isError && (
          <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700" role="alert">
            {t("runtime.unreachable")}
          </div>
        )}
        {loadError && (
          <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700" role="alert">
            {loadError}
          </div>
        )}

        <VirtualMessageList
          messages={chat.messages}
          examples={examples}
          onExample={handleSend}
          agentTitle={currentAgent?.title}
        />

        {!quota.loading &&
          !quota.error &&
          isAuthenticated &&
          (quota.isExhausted ? (
            <div
              role="status"
              data-testid="quota-banner-exhausted"
              className="border-t border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800"
            >
              {t("quota.exhausted", { used: quota.used, quota: quota.quota })}
            </div>
          ) : quota.remaining === 1 ? (
            <div
              role="status"
              data-testid="quota-banner-warning"
              className="border-t border-blue-100 bg-blue-50 px-4 py-2 text-xs text-blue-800"
            >
              {t("quota.lastOne", { used: quota.used, quota: quota.quota })}
            </div>
          ) : null)}

        <div className="flex items-center gap-2 border-t border-gray-100 px-4 py-1.5">
          <ChatPluginPicker selectedIds={pluginIds} onChange={setPluginIds} builtIn={currentAgent?.toolkits} />
          {currentAgent && (
            <span className="truncate text-[11px] text-gray-400" title={currentAgent.description}>
              {currentAgent.description}
            </span>
          )}
        </div>
        <ChatInput
          onSend={handleSend}
          streaming={chat.streaming}
          onStop={() => void chat.stop()}
          disabled={!canUseApi}
        />
      </div>
    </div>
  );
}
