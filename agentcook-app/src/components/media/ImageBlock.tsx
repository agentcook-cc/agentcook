import { useState } from 'react';

interface ImageBlockProps {
  url: string;
  alt?: string;
  sizeBytes?: number;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImageBlock({ url, alt, sizeBytes }: ImageBlockProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [hasError, setHasError] = useState(false);

  return (
    <>
      <img
        src={url}
        alt={alt || ''}
        loading="lazy"
        onClick={() => !hasError && setIsOpen(true)}
        onError={() => setHasError(true)}
        className={`max-w-full rounded-lg cursor-pointer ${hasError ? 'hidden' : ''}`}
      />

      {hasError && (
        <div className="flex items-center justify-center bg-gray-100 rounded-lg p-8 max-w-full">
          <span className="text-gray-400">Image failed to load</span>
        </div>
      )}

      {sizeBytes && !hasError && (
        <p className="text-xs text-gray-500 mt-1">{formatFileSize(sizeBytes)}</p>
      )}

      {isOpen && (
        <dialog
          open
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50"
        >
          <img
            src={url}
            alt={alt || ''}
            className="max-w-[90vw] max-h-[90vh] object-contain"
          />
        </dialog>
      )}
    </>
  );
}
