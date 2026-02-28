import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { MemoryTimeline } from '@/components/timeline/MemoryTimeline'
import { VoiceWidget } from '@/components/chat/VoiceWidget'
import { useMemories } from '@/hooks/useMemories'
import type { PhotoMeta, Memory } from '@/types'

// ============================================================
// TimelinePage — Full memory timeline with voice companion
// ============================================================

interface NavBarProps {
  personName: string
  memoryId: string
  photoCount: number
}

const NavBar: React.FC<NavBarProps> = ({ personName, memoryId, photoCount }) => (
  <nav
    className="sticky top-0 z-40 backdrop-blur-md bg-memory-bg/80 border-b border-white/10"
    aria-label="Memory timeline navigation"
  >
    <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
      {/* Brand */}
      <Link to="/" className="flex items-center gap-2 flex-shrink-0" aria-label="MemoryBridge home">
        <div className="w-7 h-7 rounded-lg bg-memory-accent/15 border border-memory-accent/30
                        flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f4c430" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
          </svg>
        </div>
        <span className="text-sm font-semibold text-gradient-gold hidden sm:inline">
          MemoryBridge
        </span>
      </Link>

      {/* Person name */}
      <div className="flex-1 text-center">
        <h1 className="text-sm font-semibold text-memory-text truncate">
          {personName ? `${personName}'s Memories` : 'Memory Timeline'}
        </h1>
        {photoCount > 0 && (
          <p className="text-xs text-memory-text-muted hidden sm:block">
            {photoCount} {photoCount === 1 ? 'memory' : 'memories'}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Link
          to={`/room/${memoryId}`}
          className="btn-gold text-xs px-3 py-1.5 hidden sm:flex items-center gap-1.5"
          aria-label="Open immersive memory room"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>
          </svg>
          Spatial Room
        </Link>
        <Link
          to="/"
          className="btn-ghost text-xs px-3 py-1.5"
          aria-label="Upload more memories"
        >
          + Upload
        </Link>
      </div>
    </div>
  </nav>
)

// ============================================================
// Missing ID fallback
// ============================================================

const MissingIdFallback: React.FC = () => (
  <div className="min-h-screen bg-memory-bg flex items-center justify-center">
    <div className="glass-card p-10 text-center space-y-4 max-w-sm">
      <p className="text-3xl font-bold text-gradient-gold">Oops</p>
      <p className="text-memory-text-muted">No memory ID found in the URL.</p>
      <Link to="/" className="btn-gold inline-block">
        Start fresh
      </Link>
    </div>
  </div>
)

// ============================================================
// Main TimelinePage
// ============================================================

export const TimelinePage: React.FC = () => {
  const { id: memoryId } = useParams<{ id: string }>()
  const [activeMemory, setActiveMemory] = useState<Memory | null>(null)

  const { photos, photoCount, personName, agentId } = useMemories(memoryId ?? null)

  if (!memoryId) {
    return <MissingIdFallback />
  }

  const handlePhotoSelect = (photo: PhotoMeta): void => {
    setActiveMemory({
      id: photo.id,
      photoUrl: photo.url,
      caption: photo.caption,
      date: photo.date,
      era: photo.era,
    })
  }

  return (
    <div className="min-h-screen bg-memory-bg">
      {/* Sticky nav */}
      <NavBar
        personName={personName}
        memoryId={memoryId}
        photoCount={photoCount}
      />

      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-96
                        bg-radial-purple opacity-60" />
      </div>

      {/* Main content */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-8 lg:px-8">
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Timeline — takes full width on mobile, most width on desktop */}
          <motion.main
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="flex-1 min-w-0"
            role="main"
            aria-label="Memory timeline"
          >
            <MemoryTimeline
              memoryId={memoryId}
              personName={personName}
              onPhotoSelect={handlePhotoSelect}
            />
          </motion.main>

          {/* Sidebar: Voice companion */}
          <motion.aside
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="lg:w-72 xl:w-80 flex-shrink-0"
            aria-label="Voice companion"
          >
            <div className="lg:sticky lg:top-20 space-y-4">
              <VoiceWidget
                agentId={agentId}
                memoryId={memoryId}
                personName={personName}
                photos={photos}
                activeMemory={activeMemory}
                className=""
              />

              {/* Quick links */}
              <div className="glass-card p-4 space-y-2">
                <p className="text-xs font-medium text-memory-text-muted uppercase tracking-widest">
                  Quick actions
                </p>
                <Link
                  to={`/room/${memoryId}`}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5
                             transition-colors duration-200 text-sm text-memory-text-muted hover:text-memory-text group"
                >
                  <span className="text-memory-accent group-hover:scale-110 transition-transform duration-200 inline-block">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>
                    </svg>
                  </span>
                  Open Spatial Room
                </Link>
                <Link
                  to="/"
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5
                             transition-colors duration-200 text-sm text-memory-text-muted hover:text-memory-text group"
                >
                  <span className="text-memory-accent group-hover:scale-110 transition-transform duration-200 inline-block">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="17 8 12 3 7 8"/>
                      <line x1="12" x2="12" y1="3" y2="15"/>
                    </svg>
                  </span>
                  Upload More Photos
                </Link>
              </div>
            </div>
          </motion.aside>
        </div>
      </div>
    </div>
  )
}

export default TimelinePage
