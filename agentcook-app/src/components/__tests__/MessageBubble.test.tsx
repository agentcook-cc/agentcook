import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import MessageBubble, { MediaAttachment } from '../MessageBubble';

// Mock complex dependencies
vi.mock('../MarkdownRenderer', () => ({
  default: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));

vi.mock('../media/ImageBlock', () => ({
  default: ({ url, alt }: { url: string; alt?: string }) => (
    <img data-testid="image-block" src={url} alt={alt} />
  ),
}));

vi.mock('../media/FileBlock', () => ({
  default: ({ fileName }: { fileName: string }) => (
    <div data-testid="file-block">{fileName}</div>
  ),
}));

vi.mock('../media/PdfBlock', () => ({
  default: ({ title }: { title: string }) => <div data-testid="pdf-block">{title}</div>,
}));

vi.mock('../media/MermaidBlock', () => ({
  default: ({ code }: { code: string }) => <div data-testid="mermaid-block">{code}</div>,
}));

describe('MessageBubble', () => {
  describe('variant rendering', () => {
    it('renders user variant correctly', () => {
      render(
        <MessageBubble
          variant="user"
          content="Hello, this is a user message"
          timestamp={1234567890000}
        />
      );

      expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument();
      // Timestamp rendered in local timezone — verify time pattern exists
      const wrapper = screen.getByText('Hello, this is a user message').closest('.flex')
      expect(wrapper?.textContent).toMatch(/\d{2}:\d{2}/)
    });

    it('renders assistant variant with MarkdownRenderer', () => {
  render(
    <MessageBubble
      variant="assistant"
      content="# Assistant Response"
      timestamp={1234567890000}
    />
  )

  expect(screen.getByTestId('markdown')).toBeInTheDocument()
  expect(screen.getByText('# Assistant Response')).toBeInTheDocument()
})

    it('renders tool variant with toolName', () => {
      render(
        <MessageBubble
          variant="tool"
          content="Tool output content"
          toolName="search_database"
          timestamp={1234567890000}
        />
      );

      expect(screen.getByText('🔧 search_database')).toBeInTheDocument();
      expect(screen.getByText('Tool output content')).toBeInTheDocument();
    });

    it('renders loading variant with animated dots', () => {
      render(<MessageBubble variant="loading" />);

      const loadingDots = document.querySelectorAll('.animate-bounce');
      expect(loadingDots).toHaveLength(3);
    });
  });

  describe('user variant details', () => {
    it('displays content and timestamp for user messages', () => {
      render(
        <MessageBubble
          variant="user"
          content="User message content"
          timestamp={1234567890000}
        />
      )

      expect(screen.getByText('User message content')).toBeInTheDocument()
      const bubble = screen.getByText('User message content').closest('div')
      expect(bubble?.parentElement?.textContent).toMatch(/\d{2}:\d{2}/)
    })
  });

  describe('assistant variant', () => {
    it('uses MarkdownRenderer to render content', () => {
      render(
        <MessageBubble
          variant="assistant"
          content="Assistant markdown content"
        />
      );

      expect(screen.getByTestId('markdown')).toBeInTheDocument();
    });

    it('renders without content', () => {
      render(<MessageBubble variant="tool" toolName="test_tool" />)

      expect(screen.getByText('🔧 test_tool')).toBeInTheDocument()
    })
  });

  describe('tool variant', () => {
    it('displays toolName when provided', () => {
      render(
        <MessageBubble
          variant="tool"
          toolName="calculate_sum"
          content="Result: 42"
        />
      );

      expect(screen.getByText('🔧 calculate_sum')).toBeInTheDocument();
    });
  });

  describe('attachments rendering', () => {
    const mockAttachments: MediaAttachment[] = [
      {
        type: 'image',
        url: 'https://example.com/image.png',
        mime_type: 'image/png',
        size_bytes: 1024,
      },
      {
        type: 'file',
        url: 'https://example.com/document.pdf',
        mime_type: 'application/pdf',
        size_bytes: 2048,
        metadata: { fileName: 'document.pdf' },
      },
    ];

    it('renders attachments when provided', () => {
      render(
        <MessageBubble
          variant="assistant"
          content="Message with attachments"
          attachments={mockAttachments}
        />
      );

      expect(screen.getByTestId('image-block')).toBeInTheDocument();
      expect(screen.getByTestId('file-block')).toBeInTheDocument();
    });

    it('does not render attachments section when no attachments', () => {
      render(
        <MessageBubble
          variant="assistant"
          content="Message without attachments"
        />
      );

      expect(screen.queryByTestId('image-block')).not.toBeInTheDocument();
    });
  });

  describe('placeholder display', () => {
    it('shows placeholder when no content in assistant variant', () => {
      render(<MessageBubble variant="assistant" />);

      expect(screen.getByText('…')).toBeInTheDocument();
    });
  });
});
