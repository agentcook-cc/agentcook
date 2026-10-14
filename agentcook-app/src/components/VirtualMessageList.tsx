import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import type { ChatMessage } from "@/hooks/useAgentChat";
import MessageBubble from "./MessageBubble";

interface VirtualMessageListProps {
  messages: ChatMessage[];
  /** Example prompts shown on the empty state; clicking one sends it. */
  examples?: string[];
  onExample?: (prompt: string) => void;
  agentTitle?: string;
}

const FOLLOW_OUTPUT_THRESHOLD = 80;

export default function VirtualMessageList({
  messages,
  examples = [],
  onExample,
  agentTitle,
}: VirtualMessageListProps) {
  const { t } = useTranslation();
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [showNewMessage, setShowNewMessage] = useState(false);

  const handleAtBottomChange = useCallback((atBottom: boolean) => {
    setIsAtBottom(atBottom);
    if (atBottom) setShowNewMessage(false);
  }, []);

  const handleFollowOutput = useCallback((atBottom: boolean) => {
    if (atBottom) return "smooth" as const;
    setShowNewMessage(true);
    return false as const;
  }, []);

  const scrollToBottom = useCallback(() => {
    virtuosoRef.current?.scrollToIndex({
      index: messages.length - 1,
      behavior: "smooth",
      align: "end",
    });
    setShowNewMessage(false);
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-4" data-testid="empty-state">
        <div className="mx-auto max-w-lg text-center">
          <div className="mb-4 text-5xl">🍳</div>
          <p className="text-2xl font-medium text-gray-700">
            {agentTitle ? t("chat.emptyTitleAgent", { agent: agentTitle }) : t("chat.emptyTitle")}
          </p>
          <p className="mt-2 text-sm text-gray-400">{t("chat.emptyHint")}</p>
          {examples.length > 0 && (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {examples.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onExample?.(prompt)}
                  className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-blue-300 hover:text-blue-600"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1" data-testid="message-list">
      <Virtuoso
        ref={virtuosoRef}
        data={messages}
        atBottomStateChange={handleAtBottomChange}
        atBottomThreshold={FOLLOW_OUTPUT_THRESHOLD}
        followOutput={handleFollowOutput}
        initialTopMostItemIndex={messages.length - 1}
        className="h-full px-4 py-6"
        computeItemKey={(_, msg) => msg.id}
        itemContent={(_, msg) => (
          <div className="mx-auto max-w-3xl">
            <MessageBubble
              variant={msg.role}
              content={msg.content}
              timestamp={msg.createdAt}
              toolCalls={msg.toolCalls}
              status={msg.status}
              error={msg.error}
              meta={msg.meta}
            />
          </div>
        )}
      />
      {showNewMessage && !isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-4 py-1.5 text-xs font-medium text-white shadow-lg transition hover:bg-blue-700"
        >
          ↓ {t("chat.newMessages")}
        </button>
      )}
    </div>
  );
}
