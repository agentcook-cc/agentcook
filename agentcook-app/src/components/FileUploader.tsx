import React, { useState, useRef, useCallback } from 'react';

interface FileUploaderProps {
  onUpload: (file: File) => void;
  accept?: string;
  maxSizeMb?: number;
  disabled?: boolean;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onUpload,
  accept = '*',
  maxSizeMb = 10,
  disabled = false,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): boolean => {
    const maxSizeBytes = maxSizeMb * 1024 * 1024;
    
    if (file.size > maxSizeBytes) {
      setError(`File size exceeds ${maxSizeMb}MB limit`);
      return false;
    }
    
    if (accept !== '*') {
      const acceptedTypes = accept.split(',').map(type => type.trim());
      const fileType = file.type;
      const fileName = file.name.toLowerCase();
      
      const isAccepted = acceptedTypes.some(type => {
        if (type.startsWith('.')) {
          return fileName.endsWith(type.toLowerCase());
        }
        if (type.endsWith('/*')) {
          const baseType = type.split('/')[0];
          return fileType.startsWith(baseType + '/');
        }
        return fileType === type || fileName.endsWith(type);
      });
      
      if (!isAccepted) {
        setError(`File type not supported. Accepted: ${accept}`);
        return false;
      }
    }
    
    setError(null);
    return true;
  }, [accept, maxSizeMb]);

  const handleFile = useCallback((file: File) => {
    if (!validateFile(file)) {
      return;
    }

    setUploadedFile(file);
    setUploadProgress(0);
    
    // Simulate upload progress
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          onUpload(file);
          return 100;
        }
        return prev + 10;
      });
    }, 100);
  }, [validateFile, onUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragOver(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    
    if (disabled) return;
    
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, [disabled, handleFile]);

  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
    // Reset input value to allow selecting the same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleFile]);

  const handleClear = useCallback(() => {
    setUploadedFile(null);
    setUploadProgress(0);
    setError(null);
  }, []);

  const getAcceptedFormatsText = () => {
    if (accept === '*') return 'All formats supported';
    return `Accepted formats: ${accept}`;
  };

  if (uploadedFile && uploadProgress === 100) {
    return (
      <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
        <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
        <span className="flex-1 text-sm text-green-800 truncate">{uploadedFile.name}</span>
        <button
          onClick={handleClear}
          className="p-1 hover:bg-green-100 rounded transition-colors"
          aria-label="Clear file"
        >
          <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`
          relative border-2 border-dashed rounded-lg p-6 cursor-pointer transition-all
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
          ${isDragOver 
            ? 'border-blue-500 bg-blue-50' 
            : error 
              ? 'border-red-300 hover:border-red-400' 
              : 'border-gray-300 hover:border-gray-400'
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          onChange={handleFileInputChange}
          className="hidden"
          disabled={disabled}
        />
        
        <div className="flex flex-col items-center justify-center space-y-2">
          <svg 
            className={`w-10 h-10 ${isDragOver ? 'text-blue-500' : 'text-gray-400'}`} 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" 
            />
          </svg>
          
          <p className="text-sm text-gray-600 text-center">
            Drag & drop or click to upload
          </p>
          
          <p className="text-xs text-gray-400">
            {getAcceptedFormatsText()}
          </p>
        </div>

        {uploadProgress > 0 && uploadProgress < 100 && (
          <div className="mt-4">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-200 ease-out"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1 text-center">{uploadProgress}%</p>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

export default FileUploader;
