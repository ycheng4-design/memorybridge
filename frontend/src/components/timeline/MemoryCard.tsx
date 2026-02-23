import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { PhotoMeta } from '@/types'
import { ERA_CONFIGS } from '@/types'

// ============================================================
// Era Badge
// ============================================================

interface EraBadgeProps {
  era: PhotoMeta['era']
  size?: 'sm' | 'md'
}

const EraBadge: React.FC<EraBadgeProps> = ({ era, size = 'sm' }) => {
  const config = ERA_CONFIGS[era]
  return (
    <span
      className={`era-badge ${config.textColor} ${config.bgColor} ${config.borderColor}
        ${size === 'md' ? 'text-sm px-4 py-1.5' : ''}`}
    >
      {config.icon} {config.label}
    </span>
  )
}

// ============================================================
// Photo Expand Modal
// ============================================================

interface PhotoModalProps {
  photo: PhotoMeta
  onClose: () => void
}

const PhotoModal: React.FC<PhotoModalProps> = ({ photo, onClose }) => {
  const config = ERA_CONFIGS[photo.era]

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 16 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className="relative max-w-3xl w-full glass-card overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-8 h-8 rounded-full bg-black/50 hover:bg-black/80
                     flex items-center justify-center text-white/70 hover:text-white transition-colors duration-200"
          aria-label="Close photo"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>

        {/* Image */}
        <div className="relative max-h-[60vh] overflow-hidden">
          <img
            src={photo.url}
            alt={photo.caption}
            className="w-full h-full object-contain bg-black/40"
          />
          {/* Era color overlay strip */}
          <div
            className="absolute bottom-0 left-0 right-0 h-1"
            style={{ backgroundColor: config.color }}
          />
        </div>

        {/* Details */}
        <div className="p-6 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1 flex-1">
              <p className="text-lg font-medium text-memory-text leading-snug">
                {photo.caption || 'A precious memory'}
              </p>
              <p className="text-sm text-memory-text-muted">{photo.date}</p>
            </div>
            <EraBadge era={photo.era} size="md" />
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ============================================================
// Memory Card
// ============================================================

interface MemoryCardProps {
  photo: PhotoMeta
  index: number
  onSelect?: (photo: PhotoMeta) => void
}

export const MemoryCard: React.FC<MemoryCardProps> = ({
  photo,
  index,
  onSelect,
}) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)

  const config = ERA_CONFIGS[photo.era]

  const handleCardClick = (): void => {
    setIsExpanded(true)
    onSelect?.(photo)
  }

  return (
    <>
      <motion.article
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{
          duration: 0.4,
          delay: Math.min(index * 0.06, 0.5),
          ease: 'easeOut',
        }}
        whileHover={{ y: -4, transition: { duration: 0.2 } }}
        className="group relative glass-card overflow-hidden cursor-pointer
                   hover:border-memory-accent/30 hover:shadow-card-hover
                   transition-shadow duration-300"
        onClick={handleCardClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleCardClick()
          }
        }}
        tabIndex={0}
        role="button"
        aria-label={`View memory: ${photo.caption || 'Photo from ' + photo.date}`}
      >
        {/* Era accent bar */}
        <div
          className="absolute top-0 left-0 right-0 h-0.5 opacity-60 transition-opacity duration-300 group-hover:opacity-100"
          style={{ backgroundColor: config.color }}
        />

        {/* Photo */}
        <div className="relative aspect-square overflow-hidden">
          {/* Skeleton while loading */}
          {!imageLoaded && !imageError && (
            <div className="absolute inset-0 skeleton" />
          )}

          {/* Error state */}
          {imageError && (
            <div className="absolute inset-0 bg-white/5 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-memory-text-muted/40"
              >
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
                <circle cx="9" cy="9" r="2"/>
                <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
              </svg>
            </div>
          )}

          <img
            src={photo.url}
            alt={photo.caption}
            loading="lazy"
            className={`w-full h-full object-cover transition-all duration-300
              group-hover:scale-105
              ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />

          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent
                          opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

          {/* Era badge on hover */}
          <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <EraBadge era={photo.era} />
          </div>

          {/* Expand icon on hover */}
          <div className="absolute inset-0 flex items-center justify-center
                          opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <div className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm
                            flex items-center justify-center border border-white/20">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
              </svg>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-3 space-y-2">
          {/* Caption */}
          <p className="text-sm text-memory-text font-medium line-clamp-2 leading-snug">
            {photo.caption || (
              <span className="text-memory-text-muted italic">No caption</span>
            )}
          </p>

          {/* Footer: date + era */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-memory-text-muted">{photo.date}</span>
            <EraBadge era={photo.era} />
          </div>
        </div>
      </motion.article>

      {/* Expanded modal */}
      <AnimatePresence>
        {isExpanded && (
          <PhotoModal photo={photo} onClose={() => setIsExpanded(false)} />
        )}
      </AnimatePresence>
    </>
  )
}

export default MemoryCard
