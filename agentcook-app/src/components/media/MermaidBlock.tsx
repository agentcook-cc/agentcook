import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import DOMPurify from 'dompurify';

// Day 51 (Phase 5 合规检查): mermaid securityLevel='strict' 禁 inline JS;
// SVG 进 DOM 前再过 DOMPurify svg profile,defense-in-depth。
mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });

const SVG_SANITIZE_CONFIG = {
  USE_PROFILES: { svg: true, svgFilters: true },
};

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
          containerRef.current.innerHTML = DOMPurify.sanitize(svg, SVG_SANITIZE_CONFIG);
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
