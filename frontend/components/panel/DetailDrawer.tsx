'use client'

import { useEffect, useRef } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import DetailPanel from './DetailPanel'

export default function DetailDrawer() {
  const { selectedBarrierId, setSelectedBarrierId } = useBowtieContext()
  const drawerRef = useRef<HTMLDivElement>(null)
  const isOpen = !!selectedBarrierId

  // Close on Escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedBarrierId(null)
    }
    if (isOpen) document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [isOpen, setSelectedBarrierId])

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 transition-opacity"
          onClick={() => setSelectedBarrierId(null)}
        />
      )}

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`fixed top-0 right-0 z-40 h-full w-[560px] bg-[#1C2430] border-l border-[#2A3442]
          transform transition-transform duration-200 ease-out overflow-y-auto
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Close button */}
        <button
          onClick={() => setSelectedBarrierId(null)}
          className="absolute top-3 right-3 z-50 text-[#6B7280] hover:text-[#E8E8E8] transition-colors"
          aria-label="Close detail panel"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M15 5L5 15M5 5l10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>

        {isOpen && (
          <div className="p-5 pt-10">
            <DetailPanel />
          </div>
        )}
      </div>
    </>
  )
}
