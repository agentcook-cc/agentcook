import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FileUploader from '@/components/FileUploader';

describe('FileUploader', () => {
  const mockOnUpload = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders drag and drop area', () => {
    render(<FileUploader onUpload={mockOnUpload} />);
    
    expect(screen.getByText(/Drag & drop or click to upload/i)).toBeInTheDocument();
    expect(screen.getByText(/All formats supported/i)).toBeInTheDocument();
  });

  it('triggers file selection on click', async () => {
    render(<FileUploader onUpload={mockOnUpload} />);
    
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeInTheDocument();
    
    const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    
    // onUpload is called after progress simulation completes
    await vi.waitFor(() => {
      expect(mockOnUpload).toHaveBeenCalledWith(file);
    }, { timeout: 2000 });
  });

  it('shows error when file size exceeds limit', () => {
    const maxSizeMb = 1; // 1MB limit
    render(<FileUploader onUpload={mockOnUpload} maxSizeMb={maxSizeMb} />);
    
    const largeFile = new File([new Array(2 * 1024 * 1024).fill('a').join('')], 'large.txt', {
      type: 'text/plain',
    });
    
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [largeFile] } });
    
    expect(screen.getByText(/File size exceeds 1MB limit/i)).toBeInTheDocument();
    expect(mockOnUpload).not.toHaveBeenCalled();
  });

  it('shows error for unsupported file type', () => {
    render(<FileUploader onUpload={mockOnUpload} accept=".pdf" />);
    
    const txtFile = new File(['test'], 'test.txt', { type: 'text/plain' });
    
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [txtFile] } });
    
    expect(screen.getByText(/File type not supported/i)).toBeInTheDocument();
    expect(mockOnUpload).not.toHaveBeenCalled();
  });

  it('displays filename and clear button after successful upload', async () => {
    render(<FileUploader onUpload={mockOnUpload} />);
    
    const file = new File(['test content'], 'document.pdf', { type: 'application/pdf' });
    
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    
    // Wait for upload simulation to complete (100ms intervals * 10 steps = 1000ms)
    await vi.waitFor(() => {
      expect(screen.getByText('document.pdf')).toBeInTheDocument();
    }, { timeout: 2000 });
    
    const clearButton = screen.getByRole('button', { name: /Clear file/i });
    expect(clearButton).toBeInTheDocument();
    
    fireEvent.click(clearButton);
    
    expect(screen.queryByText('document.pdf')).not.toBeInTheDocument();
    expect(screen.getByText(/Drag & drop or click to upload/i)).toBeInTheDocument();
  });

  it('is not operable when disabled', () => {
    render(<FileUploader onUpload={mockOnUpload} disabled={true} />);
    
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeDisabled();
    
    // Verify disabled styling exists somewhere in the tree
    const dropZone = screen.getByText(/Drag & drop or click to upload/i).closest('[class*="opacity-50"]');
    expect(dropZone).toBeInTheDocument();
    
    expect(mockOnUpload).not.toHaveBeenCalled();
  });
});
