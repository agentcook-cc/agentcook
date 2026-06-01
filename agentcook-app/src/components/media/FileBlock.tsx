interface FileBlockProps {
  fileName: string;
  url: string;
  mimeType?: string;
  sizeBytes?: number;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileBlock({ fileName, url, mimeType, sizeBytes }: FileBlockProps) {
  return (
    <div className="border rounded-lg p-4 flex items-center justify-between bg-white">
      <div className="flex items-center gap-3">
        <span className="text-2xl">📄</span>
        <div>
          <p className="font-medium text-gray-900">{fileName}</p>
          <p className="text-sm text-gray-500">
            {mimeType && <span>{mimeType}</span>}
            {sizeBytes && <span className="ml-2">{formatFileSize(sizeBytes)}</span>}
          </p>
        </div>
      </div>
      <a
        href={url}
        download={fileName}
        className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
      >
        Download
      </a>
    </div>
  );
}
