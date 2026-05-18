import React from 'react'

interface MessageBubbleProps {
  variant: 'user' | 'assistant' | 'tool' | 'loading'
  content?: string
  toolName?: string
  timestamp?: number
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  variant,
  content,
  toolName,
  timestamp,
}) => {
  const formatTime = (ts?: number) => {
    if (!ts) return ''
    const date = new Date(ts)
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }

  if (variant === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[70%] bg-blue-500 text-white rounded-2xl px-4 py-2">
          <p className="text-sm">{content}</p>
          {timestamp && (
            <span className="text-xs text-blue-100 mt-1 block text-right">
              {formatTime(timestamp)}
            </span>
          )}
        </div>
      </div>
    )
  }

  if (variant === 'assistant') {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[70%] bg-gray-100 text-gray-900 rounded-2xl px-4 py-2">
          <p className="text-sm">{content}</p>
          {timestamp && (
            <span className="text-xs text-gray-500 mt-1 block text-left">
              {formatTime(timestamp)}
            </span>
          )}
        </div>
      </div>
    )
  }

  if (variant === 'tool') {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[70%] border border-gray-300 rounded-lg px-4 py-3 bg-white">
          {toolName && (
            <div className="text-xs font-semibold text-gray-600 mb-2">
              🔧 {toolName}
            </div>
          )}
          <pre className="text-sm text-gray-800 whitespace-pre-wrap">{content}</pre>
          {timestamp && (
            <span className="text-xs text-gray-400 mt-2 block text-left">
              {formatTime(timestamp)}
            </span>
          )}
        </div>
      </div>
    )
  }

  if (variant === 'loading') {
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-gray-100 rounded-2xl px-4 py-3">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    )
  }

  return null
}

export default MessageBubble
