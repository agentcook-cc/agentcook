import { useCallback, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <button
      onClick={handleCopy}
      className="absolute right-2 top-2 rounded border border-gray-300 bg-white/80 px-2 py-0.5 text-xs text-gray-600 transition hover:bg-gray-100"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`markdown-body prose prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ children, ...props }) {
            // Extract code text for the copy button
            const codeElement = Array.isArray(children)
              ? children.find(
                  (child) => typeof child === "object" && child !== null && "type" in child && child.type === "code",
                )
              : typeof children === "object" && children !== null && "type" in children && children.type === "code"
                ? children
                : null;

            const codeText =
              codeElement && typeof codeElement === "object" && "props" in codeElement
                ? String(codeElement.props.children || "")
                : "";

            return (
              <div className="group relative">
                <CopyButton code={codeText} />
                <pre {...props} className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-sm">
                  {children}
                </pre>
              </div>
            );
          },
          code({ className: codeClassName, children, ...props }) {
            const isInline = !codeClassName;
            if (isInline) {
              return (
                <code
                  className="rounded bg-gray-100 px-1.5 py-0.5 text-sm text-pink-600"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={codeClassName} {...props}>
                {children}
              </code>
            );
          },
          a({ href, children, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline hover:text-blue-800"
                {...props}
              >
                {children}
              </a>
            );
          },
          table({ children, ...props }) {
            return (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse border border-gray-200" {...props}>
                  {children}
                </table>
              </div>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
