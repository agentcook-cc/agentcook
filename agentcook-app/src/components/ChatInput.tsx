import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

interface ChatInputProps {
  onSend: (message: string) => void;
  /** While a reply streams, the send button becomes a Stop button. */
  streaming?: boolean;
  onStop?: () => void;
  disabled?: boolean;
  maxLength?: number;
  placeholder?: string;
}

// Matches the runtime's ChatStreamRequest.message max_length.
const MAX_CHAR_DEFAULT = 32_000;

export default function ChatInput({
  onSend,
  streaming = false,
  onStop,
  disabled = false,
  maxLength = MAX_CHAR_DEFAULT,
  placeholder,
}: ChatInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const canSend = trimmed.length > 0 && !disabled && !streaming;

  const handleSend = useCallback(() => {
    if (!canSend) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [canSend, trimmed, onSend]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter sends; Shift+Enter inserts a newline; IME composition (CJK
      // input) must not send on the Enter that confirms a candidate.
      if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
        event.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const next = event.target.value;
      if (next.length <= maxLength) setValue(next);
      const textarea = event.target;
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    },
    [maxLength],
  );

  return (
    <footer className="border-t border-gray-200 px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder ?? t("chat.placeholder")}
            disabled={disabled}
            rows={1}
            aria-label={t("chat.placeholder")}
            className="w-full resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm leading-relaxed outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
          />
          {value.length > maxLength * 0.8 && (
            <span className="absolute bottom-1 right-2 text-xs text-gray-400">
              {value.length}/{maxLength}
            </span>
          )}
        </div>
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            data-testid="stop-button"
            className="rounded-xl border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            ⏹ {t("chat.stop")}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            data-testid="send-button"
            className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {t("common.send")}
          </button>
        )}
      </div>
    </footer>
  );
}
