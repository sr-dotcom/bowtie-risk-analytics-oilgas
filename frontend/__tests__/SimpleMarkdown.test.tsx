import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SimpleMarkdown from '@/components/ui/SimpleMarkdown'

describe('SimpleMarkdown', () => {
  it('renders plain text as a single <p> with exact text content', () => {
    render(<SimpleMarkdown content="Hello world" />)
    const p = screen.getByText('Hello world')
    expect(p.tagName).toBe('P')
  })

  it('splits on \\n\\n into two <p> elements', () => {
    // Use template literal so \n is a real newline, matching production API data
    render(<SimpleMarkdown content={`First paragraph\n\nSecond paragraph`} />)
    expect(screen.getByText('First paragraph').tagName).toBe('P')
    expect(screen.getByText('Second paragraph').tagName).toBe('P')
  })

  it('renders **bold** text as <strong> element', () => {
    render(<SimpleMarkdown content="Some **bold** text" />)
    const strong = screen.getByText('bold')
    expect(strong.tagName).toBe('STRONG')
  })

  it('renders "- item" lines as <ul><li> elements', () => {
    render(<SimpleMarkdown content={`- Alpha\n- Beta\n- Gamma`} />)
    expect(screen.getByText('Alpha').tagName).toBe('LI')
    expect(screen.getByText('Beta').tagName).toBe('LI')
    expect(screen.getByText('Gamma').tagName).toBe('LI')
    // Verify list container
    const lis = document.querySelectorAll('li')
    expect(lis).toHaveLength(3)
    expect(lis[0].closest('ul')).toBeTruthy()
  })

  it('renders "* item" lines as <ul><li> elements', () => {
    render(<SimpleMarkdown content={`* One\n* Two`} />)
    expect(screen.getByText('One').tagName).toBe('LI')
    expect(screen.getByText('Two').tagName).toBe('LI')
  })

  it('renders bold text inside bullet list items', () => {
    render(<SimpleMarkdown content={`- Normal item\n- Item with **bold** word`} />)
    const strong = screen.getByText('bold')
    expect(strong.tagName).toBe('STRONG')
    expect(strong.closest('li')).toBeTruthy()
  })

  it('renders nothing for empty string', () => {
    const { container } = render(<SimpleMarkdown content="" />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing for undefined content', () => {
    const { container } = render(<SimpleMarkdown content={undefined} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing for null content', () => {
    const { container } = render(<SimpleMarkdown content={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('applies className to the wrapper div', () => {
    const { container } = render(<SimpleMarkdown content="Some text" className="my-class" />)
    const div = container.firstChild as HTMLElement
    expect(div.tagName).toBe('DIV')
    expect(div.classList.contains('my-class')).toBe(true)
  })

  it('treats single \\n within a paragraph as a space (not <br>)', () => {
    render(<SimpleMarkdown content={`Line one\nLine two`} />)
    // Should render as a single <p> with both lines joined by space
    const p = screen.getByText('Line one Line two')
    expect(p.tagName).toBe('P')
  })

  it('renders "### heading" as <h4>', () => {
    render(<SimpleMarkdown content="### Section Title" />)
    const h4 = screen.getByText('Section Title')
    expect(h4.tagName).toBe('H4')
  })

  it('renders "---" as <hr>', () => {
    const { container } = render(<SimpleMarkdown content="---" />)
    const hr = container.querySelector('hr')
    expect(hr).not.toBeNull()
  })

  it('handles mixed paragraphs and bullet lists separated by \\n\\n', () => {
    render(
      <SimpleMarkdown content={`Intro paragraph\n\n- Bullet A\n- Bullet B\n\nClosing paragraph`} />
    )
    expect(screen.getByText('Intro paragraph').tagName).toBe('P')
    expect(screen.getByText('Bullet A').tagName).toBe('LI')
    expect(screen.getByText('Bullet B').tagName).toBe('LI')
    expect(screen.getByText('Closing paragraph').tagName).toBe('P')
  })
})
