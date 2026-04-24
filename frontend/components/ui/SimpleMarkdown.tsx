'use client'

import React from 'react'

interface SimpleMarkdownProps {
  content?: string | null
  className?: string
}

/**
 * Lightweight inline markdown renderer. Handles 4 constructs:
 * 1. \n\n paragraph breaks → <p> elements
 * 2. **text** → <strong> inline
 * 3. Lines starting with "- " or "* " → <ul><li>
 * 4. Plain text → single <p>
 *
 * Single \n within a paragraph is treated as a space (not <br>).
 * No external markdown library required.
 */

function renderInline(text: string): React.ReactNode[] {
  // Replace single newlines with spaces first
  const normalized = text.replace(/\n/g, ' ')
  // Split on **bold** markers
  const parts = normalized.split(/\*\*(.*?)\*\*/g)
  return parts.map((part, idx) =>
    idx % 2 === 1
      ? <strong key={idx}>{part}</strong>
      : part,
  )
}

function isListBlock(lines: string[]): boolean {
  const nonEmpty = lines.filter((l) => l.trim() !== '')
  if (nonEmpty.length === 0) return false
  return nonEmpty.every((l) => /^[-*] /.test(l))
}

function renderBlock(block: string, blockIdx: number): React.ReactElement | null {
  const lines = block.split('\n')

  // Headings: ### → <h4>, ## → <h3>, # → <h2> (most-specific first)
  const firstLine = lines[0].trimEnd()
  if (/^### /.test(firstLine)) {
    return <h4 key={blockIdx}>{firstLine.replace(/^### /, '')}</h4>
  }
  if (/^## /.test(firstLine)) {
    return <h3 key={blockIdx}>{firstLine.replace(/^## /, '')}</h3>
  }
  if (/^# /.test(firstLine)) {
    return <h2 key={blockIdx}>{firstLine.replace(/^# /, '')}</h2>
  }
  // Horizontal rule
  if (/^---\s*$/.test(firstLine)) {
    return <hr key={blockIdx} className="my-3 border-t border-[#2A3442]" />
  }

  if (isListBlock(lines)) {
    const items = lines
      .filter((l) => l.trim() !== '')
      .map((l) => l.replace(/^[-*] /, ''))
    return (
      <ul key={blockIdx}>
        {items.map((item, i) => (
          <li key={i}>{renderInline(item)}</li>
        ))}
      </ul>
    )
  }
  // Paragraph: join lines with a space
  const joined = lines.join(' ').trim()
  if (joined === '') return null
  return <p key={blockIdx}>{renderInline(joined)}</p>
}

export default function SimpleMarkdown({ content, className }: SimpleMarkdownProps): React.ReactElement | null {
  if (content === undefined || content === null || content === '') {
    return null
  }

  const blocks = content.split(/\n\n/)
  const rendered = blocks
    .map((block, idx) => renderBlock(block, idx))
    .filter((el): el is React.ReactElement => el !== null)

  if (rendered.length === 0) return null

  return <div className={className}>{rendered}</div>
}
