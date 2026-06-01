import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

interface MermaidBlockProps {
  code: string;
}

export default function MermaidBlock({ code }: MermaidBlockProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const hasRendered = useRef(false);

  useEffect(() => {
    if (!containerRef.current || hasRendered.current) return;

    const renderDiagram = async () => {
      try {
        const { svg } = await mermaid.render(`mermaid-${Date.now()}`, code);
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
        hasRendered.current = true;
      } catch (error) {
        console.error('Mermaid render error:', error);
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
          const fallback = document.createElement('pre');
          fallback.textContent = code;
          containerRef.current.appendChild(fallback);
        }
      }
    };

    renderDiagram();
  }, [code]);

  return (
    <div
      ref={containerRef}
      className="overflow-x-auto bg-gray-50 rounded-lg p-4"
    />
  );
}
