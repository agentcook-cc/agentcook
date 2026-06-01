import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect } from 'vitest';
import FileBlock from '../FileBlock';

describe('FileBlock', () => {
  it('renders file name and download link', () => {
    render(
      <FileBlock
        fileName="document.pdf"
        url="https://example.com/document.pdf"
      />
    );

    expect(screen.getByText('document.pdf')).toBeInTheDocument();
    const downloadLink = screen.getByRole('link', { name: /download/i });
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink).toHaveAttribute('href', 'https://example.com/document.pdf');
    expect(downloadLink).toHaveAttribute('download', 'document.pdf');
  });

  it('displays file size when provided', () => {
    render(
      <FileBlock
        fileName="large-file.zip"
        url="https://example.com/large-file.zip"
        sizeBytes={1048576}
      />
    );

    expect(screen.getByText('1.0 MB')).toBeInTheDocument();
  });

  it('displays mime type when provided', () => {
    render(
      <FileBlock
        fileName="spreadsheet.xlsx"
        url="https://example.com/spreadsheet.xlsx"
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      />
    );

    expect(
      screen.getByText('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    ).toBeInTheDocument();
  });

  it('shows document icon', () => {
    render(
      <FileBlock
        fileName="document.pdf"
        url="https://example.com/document.pdf"
        mimeType="application/pdf"
      />
    );

    expect(screen.getByText('📄')).toBeInTheDocument();
  });

  it('formats small file sizes correctly', () => {
    render(
      <FileBlock
        fileName="small.txt"
        url="https://example.com/small.txt"
        sizeBytes={512}
      />
    );

    expect(screen.getByText('512 B')).toBeInTheDocument();
  });

  it('formats KB file sizes correctly', () => {
    render(
      <FileBlock
        fileName="medium.docx"
        url="https://example.com/medium.docx"
        sizeBytes={2048}
      />
    );

    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
  });

  it('does not display size when sizeBytes is not provided', () => {
    render(
      <FileBlock
        fileName="no-size.pdf"
        url="https://example.com/no-size.pdf"
      />
    );

    const fileSizeElements = screen.queryAllByText(/\d+\s*[BKMGT]?B?/);
    expect(fileSizeElements.length).toBe(0);
  });
});
