import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect } from 'vitest';
import ImageBlock from '../ImageBlock';

describe('ImageBlock', () => {
  it('renders image with correct src and alt', () => {
    render(
      <ImageBlock
        url="https://example.com/test-image.jpg"
        alt="Test image description"
      />
    );

    const img = screen.getByRole('img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'https://example.com/test-image.jpg');
    expect(img).toHaveAttribute('alt', 'Test image description');
  });

  it('opens lightbox dialog when image is clicked', () => {
    render(
      <ImageBlock
        url="https://example.com/test-image.jpg"
        alt="Test image"
      />
    );

    const img = screen.getByRole('img');
    fireEvent.click(img);

    const dialog = document.querySelector('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('open');

    const dialogImg = dialog?.querySelector('img');
    expect(dialogImg).toBeInTheDocument();
    expect(dialogImg).toHaveAttribute('src', 'https://example.com/test-image.jpg');
  });

  it('closes lightbox dialog when clicking on it', () => {
    render(
      <ImageBlock
        url="https://example.com/test-image.jpg"
        alt="Test image"
      />
    )

    const img = screen.getByRole('img')
    fireEvent.click(img)

    // Dialog should be open
    const dialog = document.querySelector('dialog')
    expect(dialog).toHaveAttribute('open')

    // Click on dialog to close
    fireEvent.click(dialog!)

    // Dialog should be removed from DOM after closing
    const closedDialog = document.querySelector('dialog')
    expect(closedDialog).toBeNull()
  })

  it('displays fallback when image fails to load', () => {
    render(
      <ImageBlock
        url="https://example.com/nonexistent-image.jpg"
        alt="Failed image"
      />
    );

    const img = screen.getByRole('img');
    fireEvent.error(img);

    expect(screen.getByText('Image failed to load')).toBeInTheDocument();
    expect(img).toHaveClass('hidden');
  });

  it('displays file size when provided', () => {
    render(
      <ImageBlock
        url="https://example.com/large-image.jpg"
        alt="Large image"
        sizeBytes={2097152}
      />
    );

    expect(screen.getByText('2.0 MB')).toBeInTheDocument();
  });

  it('does not display file size when not provided', () => {
    render(
      <ImageBlock
        url="https://example.com/image.jpg"
        alt="Image without size"
      />
    );

    const sizeElements = screen.queryAllByText(/\d+\s*[BKMGT]?B?/);
    expect(sizeElements.length).toBe(0);
  });

  it('does not open lightbox when image has error', () => {
    render(
      <ImageBlock
        url="https://example.com/broken-image.jpg"
        alt="Broken image"
      />
    )

    const img = screen.getByRole('img')
    fireEvent.error(img)

    // Click on the error state (fallback div)
    const fallbackDiv = screen.getByText('Image failed to load').parentElement
    if (fallbackDiv) {
      fireEvent.click(fallbackDiv)
    }

    // Dialog should not exist for failed images
    const dialog = document.querySelector('dialog')
    expect(dialog).toBeNull()
  })

  it('formats small file sizes correctly', () => {
    render(
      <ImageBlock
        url="https://example.com/small-image.png"
        alt="Small image"
        sizeBytes={512}
      />
    );

    expect(screen.getByText('512 B')).toBeInTheDocument();
  });

  it('formats KB file sizes correctly', () => {
    render(
      <ImageBlock
        url="https://example.com/medium-image.png"
        alt="Medium image"
        sizeBytes={1536}
      />
    );

    expect(screen.getByText('1.5 KB')).toBeInTheDocument();
  });
});
