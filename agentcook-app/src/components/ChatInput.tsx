import { useState, useRef, useCallback, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  maxLength?: number;
  placeholder?: string;
}

const MAX_CHAR_DEFAULT = 4000;

export default function ChatInput({
  onSend,
  disabled = false,
  maxLength = MAX_CHAR_DEFAULT,
  placeholder = "Type a message...",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const trimmedValue = value.trim();
  const canSend = trimmedValue.length > 0 && !disabled;
  const charCount = value.length;

  const handleSend = useCallback(() => {
    if (!canSend) return;
    onSend(trimmedValue);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [canSend, trimmedValue, onSend]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = event.target.value;
      if (newValue.length <= maxLength) {
        setValue(newValue);
      }
      // Auto-resize textarea
      const textarea = event.target;
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
    },
    [maxLength],
  );

  return (
    <footer className="border-t border-gray-200 px-4 py-3">
      <div className="mx-auto flex max-w-2xl items-end gap-2">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="w-full resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm leading-relaxed outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
          />
          {charCount > maxLength * 0.8 && (
            <span className="absolute bottom-1 right-2 text-xs text-gray-400">
              {charCount}/{maxLength}
            </span>
          )}
        </div>
        <button
          onClick={handleSend}
          disabled={!canSend}
          className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </footer>
  );
}
