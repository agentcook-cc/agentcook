import React, { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import type { RunMetadata, ToolCallView } from "@/api/runtime";
import MarkdownRenderer from "./MarkdownRenderer";
import ToolCallCard from "./ToolCallCard";
import ImageBlock from "./media/ImageBlock";
import FileBlock from "./media/FileBlock";
import PdfBlock from "./media/PdfBlock";

const MermaidBlock = lazy(() => import("./media/MermaidBlock"));

/** Matches Agent A's MediaType enum */
export type MediaType = "text" | "image" | "pdf" | "markdown" | "mermaid" | "file";

export interface MediaAttachment {
  type: MediaType;
  url: string;
  mime_type?: string;
  size_bytes?: number;
  metadata?: Record<string, unknown>;
}

export type BubbleStatus = "streaming" | "done" | "error" | "cancelled";

interface MessageBubbleProps {
  variant: "user" | "assistant" | "tool" | "loading";
  content?: string;
  toolName?: string;
  timestamp?: number;
  attachments?: MediaAttachment[];
  /** Agent-loop tool calls made while producing this reply. */
  toolCalls?: ToolCallView[];
  status?: BubbleStatus;
  error?: string;
  meta?: RunMetadata;
}

function TypingDots() {
  return (
    <div className="flex space-x-1 py-1" aria-label="typing">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
    </div>
  );
}

function RunFooter({ meta, status }: { meta?: RunMetadata; status?: BubbleStatus }) {
  const { t } = useTranslation();
  if (!meta || status === "streaming") return null;
  const parts: string[] = [];
  if (meta.agent_title || meta.agent) parts.push(String(meta.agent_title ?? meta.agent));
  if (meta.model) parts.push(String(meta.model));
  if (meta.usage) parts.push(t("chat.tokens", { count: meta.usage.total_tokens }));
  if (meta.duration_ms) parts.push(`${(Number(meta.duration_ms) / 1000).toFixed(1)}s`);
  if (parts.length === 0) return null;
  return (
    <div className="mt-1.5 text-[11px] text-gray-400" data-testid="run-footer">
      {parts.join(" · ")}
    </div>
  );
}

function formatTime(ts?: number): string {
  if (!ts) return "";
  const date = new Date(ts);
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function RenderAttachment({ attachment }: { attachment: MediaAttachment }) {
  const { type, url, mime_type, size_bytes, metadata } = attachment;
  const fileName = (metadata?.fileName as string) || url.split("/").pop() || "file";

  switch (type) {
    case "image":
      return <ImageBlock url={url} alt={fileName} sizeBytes={size_bytes} />;
    case "pdf":
      return <PdfBlock url={url} title={fileName} />;
    case "mermaid":
      return (
        <Suspense fallback={<div className="text-xs text-gray-400 p-2">Loading diagram…</div>}>
          <MermaidBlock code={(metadata?.code as string) || ""} />
        </Suspense>
      );
    case "file":
      return <FileBlock fileName={fileName} url={url} mimeType={mime_type} sizeBytes={size_bytes} />;
    case "markdown":
      return <MarkdownRenderer content={(metadata?.content as string) || ""} className="text-sm" />;
    default:
      return null;
  }
}

function AttachmentList({ attachments }: { attachments: MediaAttachment[] }) {
  if (attachments.length === 0) return null;
  return (
    <div className="mt-2 space-y-2">
      {attachments.map((attachment, index) => (
        <RenderAttachment key={`${attachment.type}-${index}`} attachment={attachment} />
      ))}
    </div>
  );
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  variant,
  content,
  toolName,
  timestamp,
  attachments,
  toolCalls,
  status,
  error,
  meta,
}) => {
  const { t } = useTranslation();
  const cancelledLabel = t("chat.stopped");
  if (variant === "user") {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] bg-blue-500 text-white rounded-2xl px-4 py-2">
          <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
          {attachments && <AttachmentList attachments={attachments} />}
          {timestamp && <span className="text-xs text-blue-100 mt-1 block text-right">{formatTime(timestamp)}</span>}
        </div>
      </div>
    );
  }

  if (variant === "assistant") {
    const hasTools = Boolean(toolCalls && toolCalls.length);
    const waiting = status === "streaming" && !content && !hasTools;
    return (
      <div className="flex justify-start mb-4" data-testid="assistant-message" data-status={status ?? "done"}>
        <div className="max-w-[85%] min-w-[6rem] bg-gray-100 text-gray-900 rounded-2xl px-4 py-2">
          {hasTools && (
            <div className="mb-1">
              {toolCalls!.map((call) => (
                <ToolCallCard key={call.id} call={call} />
              ))}
            </div>
          )}
          {content ? (
            <MarkdownRenderer content={content} className="text-sm" />
          ) : waiting || (status === "streaming" && hasTools) ? (
            <TypingDots />
          ) : !hasTools && status !== "error" ? (
            <p className="text-sm text-gray-400">…</p>
          ) : null}
          {status === "error" && (
            <div className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
              ⚠️ {error}
            </div>
          )}
          {status === "cancelled" && (
            <div className="mt-1 text-[11px] font-medium text-amber-600">⏹ {cancelledLabel}</div>
          )}
          {attachments && <AttachmentList attachments={attachments} />}
          <RunFooter meta={meta} status={status} />
          {timestamp && <span className="text-xs text-gray-500 mt-1 block text-left">{formatTime(timestamp)}</span>}
        </div>
      </div>
    );
  }

  if (variant === "tool") {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[70%] border border-gray-300 rounded-lg px-4 py-3 bg-white">
          {toolName && <div className="text-xs font-semibold text-gray-600 mb-2">🔧 {toolName}</div>}
          <pre className="text-sm text-gray-800 whitespace-pre-wrap">{content}</pre>
          {attachments && <AttachmentList attachments={attachments} />}
          {timestamp && <span className="text-xs text-gray-400 mt-2 block text-left">{formatTime(timestamp)}</span>}
        </div>
      </div>
    );
  }

  if (variant === "loading") {
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-gray-100 rounded-2xl px-4 py-3">
          <TypingDots />
        </div>
      </div>
    );
  }

  return null;
};

export default MessageBubble;
