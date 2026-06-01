interface PdfBlockProps {
  url: string;
  title?: string;
}

export default function PdfBlock({ url, title }: PdfBlockProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      {title && (
        <div className="flex items-center justify-between p-3 bg-gray-50 border-b">
          <span className="font-medium text-gray-900">{title}</span>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
          >
            Open in new tab
          </a>
        </div>
      )}
      <iframe
        src={url}
        width="100%"
        height="500px"
        className="border-none"
        title={title || 'PDF Viewer'}
      />
    </div>
  );
}
