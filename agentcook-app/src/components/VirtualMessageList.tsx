import { useRef, useCallback, useState } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import MessageBubble from "./MessageBubble";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isError?: boolean;
}

interface VirtualMessageListProps {
  messages: Message[];
}

const FOLLOW_OUTPUT_THRESHOLD = 50;

export default function VirtualMessageList({ messages }: VirtualMessageListProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [showNewMessage, setShowNewMessage] = useState(false);

  const handleAtBottomChange = useCallback((atBottom: boolean) => {
    setIsAtBottom(atBottom);
    if (atBottom) {
      setShowNewMessage(false);
    }
  }, []);

  const handleFollowOutput = useCallback(
    (isAtBottomNow: boolean) => {
      if (isAtBottomNow) return "smooth";
      setShowNewMessage(true);
      return false;
    },
    [],
  );

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
      <div className="flex flex-1 items-center justify-center">
        <div className="mx-auto max-w-md text-center">
          <div className="mb-4 text-5xl">💬</div>
          <p className="text-2xl font-medium text-gray-700">Start a conversation</p>
          <p className="mt-2 text-sm text-gray-400">
            Type a message below to begin. Your conversation will be saved automatically.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {["Write a Python script", "Explain DDD patterns", "Review my code"].map((hint) => (
              <span
                key={hint}
                className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-500 transition hover:border-blue-300 hover:text-blue-600"
              >
                {hint}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1">
      <Virtuoso
        ref={virtuosoRef}
        data={messages}
        atBottomStateChange={handleAtBottomChange}
        atBottomThreshold={FOLLOW_OUTPUT_THRESHOLD}
        followOutput={handleFollowOutput}
        initialTopMostItemIndex={messages.length - 1}
        className="h-full px-4 py-6"
        itemContent={(index, msg) => (
          <div className="mx-auto max-w-2xl">
            <MessageBubble
              key={msg.id}
              variant={msg.role === "user" ? "user" : msg.content === "" ? "loading" : "assistant"}
              content={msg.isError ? `⚠️ ${msg.content}` : msg.content}
              timestamp={msg.timestamp}
            />
          </div>
        )}
      />

      {showNewMessage && !isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-4 py-1.5 text-xs font-medium text-white shadow-lg transition hover:bg-blue-700"
        >
          ↓ New messages
        </button>
      )}
    </div>
  );
}
