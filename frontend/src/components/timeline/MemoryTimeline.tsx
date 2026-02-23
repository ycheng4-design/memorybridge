import React, { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MemoryCard } from './MemoryCard'
import { useMemories } from '@/hooks/useMemories'
import type { Era, PhotoMeta } from '@/types'
import { ERA_CONFIGS } from '@/types'

// ============================================================
// Skeleton Grid
// ============================================================

const SkeletonCard: React.FC<{ index: number }> = ({ index }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ delay: index * 0.05 }}
    className="rounded-2xl overflow-hidden"
  >
    <div className="aspect-square skeleton" />
    <div className="p-3 space-y-2 bg-white/[0.04] rounded-b-2xl">
      <div className="skeleton h-4 rounded-full w-3/4" />
      <div className="skeleton h-3 rounded-full w-1/2" />
    </div>
  </motion.div>
)

const SkeletonGrid: React.FC = () => (
  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
    {Array.from({ length: 8 }, (_, i) => (
      <SkeletonCard key={i} index={i} />
    ))}
  </div>
)

// ============================================================
// Empty State
// ============================================================

const EmptyState: React.FC<{ era?: Era }> = ({ era }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    className="text-center py-16"
  >
    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/5 border border-white/10
                    flex items-center justify-center">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-memory-text-muted/50"
      >
        <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
        <circle cx="9" cy="9" r="2"/>
        <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
      </svg>
    </div>
    <p className="text-memory-text-muted text-sm">
      {era
        ? `No memories from ${ERA_CONFIGS[era].label} yet`
        : 'No memories found'}
    </p>
  </motion.div>
)

// ============================================================
// Era Section
// ============================================================

interface EraSectionProps {
  era: Era
  photos: PhotoMeta[]
  onPhotoSelect: (photo: PhotoMeta) => void
}

const EraSection: React.FC<EraSectionProps> = ({ era, photos, onPhotoSelect }) => {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const config = ERA_CONFIGS[era]

  if (photos.length === 0) return null

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      aria-label={`${config.label} memories`}
    >
      {/* Era header */}
      <button
        type="button"
        onClick={() => setIsCollapsed((c) => !c)}
        className="w-full flex items-center gap-4 mb-6 group focus-visible:ring-0"
        aria-expanded={!isCollapsed}
        aria-controls={`era-${era}-grid`}
      >
        {/* Era icon + label */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0
                       border border-current/20 transition-transform duration-200 group-hover:scale-110"
            style={{ backgroundColor: `${config.color}20`, color: config.color }}
          >
            {config.icon}
          </div>
          <div className="text-left min-w-0">
            <h2 className="text-xl font-bold text-memory-text">{config.label}</h2>
            <p className="text-xs text-memory-text-muted">
              {config.years} years &middot; {photos.length} {photos.length === 1 ? 'memory' : 'memories'}
            </p>
          </div>
        </div>

        {/* Divider line */}
        <div
          className="flex-1 h-px opacity-30"
          style={{ backgroundColor: config.color }}
        />

        {/* Collapse toggle */}
        <motion.div
          animate={{ rotate: isCollapsed ? -90 : 0 }}
          transition={{ duration: 0.2 }}
          className="flex-shrink-0 text-memory-text-muted group-hover:text-memory-text transition-colors duration-200"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </motion.div>
      </button>

      {/* Photo grid */}
      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div
            id={`era-${era}-grid`}
            key="grid"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            {photos.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 pb-2">
                {photos.map((photo, i) => (
                  <MemoryCard
                    key={photo.id}
                    photo={photo}
                    index={i}
                    onSelect={onPhotoSelect}
                  />
                ))}
              </div>
            ) : (
              <EmptyState era={era} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  )
}

// ============================================================
// Filter Bar
// ============================================================

type FilterEra = Era | 'all'

interface FilterBarProps {
  activeFilter: FilterEra
  onFilterChange: (filter: FilterEra) => void
  photoCounts: Record<Era, number>
}

const FilterBar: React.FC<FilterBarProps> = ({
  activeFilter,
  onFilterChange,
  photoCounts,
}) => {
  const eras: Era[] = ['childhood', 'young-adult', 'family', 'recent']

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {/* All filter */}
      <button
        type="button"
        onClick={() => onFilterChange('all')}
        className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200
          ${activeFilter === 'all'
            ? 'bg-memory-accent text-memory-bg'
            : 'bg-white/5 text-memory-text-muted hover:bg-white/10 hover:text-memory-text'
          }`}
      >
        All eras
      </button>

      {eras.map((era) => {
        const config = ERA_CONFIGS[era]
        const count = photoCounts[era]
        if (count === 0) return null

        return (
          <button
            key={era}
            type="button"
            onClick={() => onFilterChange(era)}
            className={`flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                        transition-all duration-200 border
              ${activeFilter === era
                ? `${config.bgColor} ${config.textColor} ${config.borderColor}`
                : 'bg-white/5 text-memory-text-muted border-transparent hover:bg-white/10 hover:text-memory-text'
              }`}
          >
            <span>{config.icon}</span>
            <span>{config.label}</span>
            <span className="opacity-60 text-xs">({count})</span>
          </button>
        )
      })}
    </div>
  )
}

// ============================================================
// Error State
// ============================================================

interface ErrorStateProps {
  error: string
  onRetry: () => void
}

const ErrorState: React.FC<ErrorStateProps> = ({ error, onRetry }) => (
  <div className="glass-card p-8 text-center space-y-4">
    <div className="w-12 h-12 mx-auto rounded-full bg-red-500/20 flex items-center justify-center">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" x2="12" y1="8" y2="12"/>
        <line x1="12" x2="12.01" y1="16" y2="16"/>
      </svg>
    </div>
    <div>
      <p className="text-memory-text font-medium mb-1">Unable to load memories</p>
      <p className="text-sm text-memory-text-muted">{error}</p>
    </div>
    <button
      type="button"
      onClick={onRetry}
      className="btn-ghost text-sm"
    >
      Try again
    </button>
  </div>
)

// ============================================================
// Main MemoryTimeline Component
// ============================================================

interface MemoryTimelineProps {
  memoryId: string
  personName?: string
  onPhotoSelect?: (photo: PhotoMeta) => void
}

const ERA_ORDER: Era[] = ['childhood', 'young-adult', 'family', 'recent']

export const MemoryTimeline: React.FC<MemoryTimelineProps> = ({
  memoryId,
  personName = 'Your loved one',
  onPhotoSelect,
}) => {
  const [activeFilter, setActiveFilter] = useState<FilterEra>('all')

  const {
    grouped,
    isLoading,
    error,
    photoCount,
    memoryStatus,
    embeddingReady,
    refresh,
  } = useMemories(memoryId)

  // Photo counts per era
  const photoCounts = useMemo<Record<Era, number>>(
    () => ({
      childhood: grouped.childhood.length,
      'young-adult': grouped['young-adult'].length,
      family: grouped.family.length,
      recent: grouped.recent.length,
    }),
    [grouped]
  )

  // Eras that have photos (respects filter)
  const visibleEras = useMemo<Era[]>(() => {
    if (activeFilter !== 'all') {
      return [activeFilter as Era]
    }
    return ERA_ORDER.filter((era) => grouped[era].length > 0)
  }, [activeFilter, grouped])

  const handlePhotoSelect = (photo: PhotoMeta): void => {
    onPhotoSelect?.(photo)
  }

  if (error) {
    return <ErrorState error={error} onRetry={refresh} />
  }

  return (
    <div className="space-y-8">
      {/* Timeline header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-3xl font-bold font-heading text-gradient-gold"
          >
            {personName}'s Memories
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-memory-text-muted text-sm mt-1"
          >
            {isLoading ? (
              'Loading memories...'
            ) : (
              <>
                {photoCount} {photoCount === 1 ? 'memory' : 'memories'} across {visibleEras.length} era{visibleEras.length !== 1 ? 's' : ''}
              </>
            )}
          </motion.p>
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-3">
          {memoryStatus === 'processing' && (
            <div className="flex items-center gap-2 text-xs text-memory-text-muted">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                className="w-3.5 h-3.5 rounded-full border-2 border-memory-text-muted/30 border-t-memory-text-muted"
              />
              Processing...
            </div>
          )}
          {embeddingReady && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-400">
              <div className="status-dot-active" />
              Voice-ready
            </div>
          )}
        </div>
      </div>

      {/* Filter bar */}
      {!isLoading && photoCount > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <FilterBar
            activeFilter={activeFilter}
            onFilterChange={setActiveFilter}
            photoCounts={photoCounts}
          />
        </motion.div>
      )}

      {/* Content */}
      {isLoading ? (
        <SkeletonGrid />
      ) : photoCount === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-12">
          <AnimatePresence>
            {visibleEras.map((era) => (
              <EraSection
                key={era}
                era={era}
                photos={grouped[era]}
                onPhotoSelect={handlePhotoSelect}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Still processing notice */}
      {memoryStatus === 'processing' && !isLoading && photoCount === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass-card p-6 text-center"
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            className="w-8 h-8 mx-auto mb-3 rounded-full border-2 border-memory-accent/30 border-t-memory-accent"
          />
          <p className="text-memory-text-muted text-sm">
            Memories are being processed... they'll appear here shortly.
          </p>
        </motion.div>
      )}
    </div>
  )
}

export default MemoryTimeline
