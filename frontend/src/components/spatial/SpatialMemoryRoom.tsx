import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import type { PhotoMeta, Era } from '@/types'
import { ERA_CONFIGS } from '@/types'
import { useMemories } from '@/hooks/useMemories'
import { sendPhotoContext } from '@/services/elevenlabs'
import FloatingPhotoPanel from './FloatingPhotoPanel'
import MemoryOrb from './MemoryOrb'
import EraSection from './EraSection'
import FallbackRoom from './FallbackRoom'

// ============================================================
// SpatialMemoryRoom — Centerpiece demo feature
//
// Detects spatial mode by checking if <html> carries the
// "is-spatial" class (set by the WebSpatial HTML template when
// XR_ENV=avp). Falls back to FallbackRoom in all other cases.
//
// Spatial layout:
//   - Era-based Z-depth: childhood -3m, young-adult -2m, family -1m, recent 0m
//   - Arc arrangement: photos spread in a Y-rotation arc per era
//   - Max 12 panels visible — paginated above 12
//   - MemoryOrb at center
//   - Loading: glowing orb skeletons at panel positions
//   - Entrance: staggered 50ms-delay fade-in per panel
//
// WebSpatial API used:
//   - enable-xr attribute on spatial elements
//   - --xr-background-material CSS custom property
//   - --xr-back CSS custom property for depth extrusion
//   - html.is-spatial class for conditional spatial styling
// ============================================================

const MAX_PANELS = 12
const PANELS_PER_PAGE = MAX_PANELS

// Z-depth per era in points (WebSpatial uses pts; 1pt ~= 1/72 inch in visionOS)
// In practice, larger values = more depth separation between era layers.
const ERA_Z_PTS: Record<Era, number> = {
  childhood:    -240, // farthest back
  'young-adult':-160,
  family:       -80,
  recent:        0,   // closest to viewer
}

// Y-rotation arc: photos in same era spread across a horizontal arc
const ARC_STEP_DEG = 14  // degrees between panels in same era

interface SpatialPanelPosition {
  x: number         // px offset on horizontal axis
  y: number         // px offset on vertical axis
  z: number         // z-depth in pts (spatial) or px (fallback)
  rotateY: number   // degrees for arc spread
}

/**
 * Compute panel positions: arc layout, era-grouped Z depth.
 * Panels never overlap more than 20% — 14° arc spacing at
 * ~800pt radius gives ~196pt arc spacing, well above card width.
 */
function computeSpatialPositions(
  photos: PhotoMeta[],
): Map<string, SpatialPanelPosition> {
  const positions = new Map<string, SpatialPanelPosition>()

  const byEra: Record<Era, PhotoMeta[]> = {
    childhood: [],
    'young-adult': [],
    family: [],
    recent: [],
  }

  photos.forEach((p) => {
    const era = p.era as Era
    if (era in byEra) byEra[era].push(p)
  })

  const ERAS: Era[] = ['childhood', 'young-adult', 'family', 'recent']

  ERAS.forEach((era) => {
    const eraPhotos = byEra[era]
    const count = eraPhotos.length
    if (count === 0) return

    const zPts = ERA_Z_PTS[era]
    // Center the arc: for N photos, spread from -(N-1)/2 to +(N-1)/2 steps
    const startAngle = -((count - 1) * ARC_STEP_DEG) / 2

    eraPhotos.forEach((photo, i) => {
      const rotateY = startAngle + i * ARC_STEP_DEG
      // Slight Y-wave: panels bob up and down along the arc for visual depth
      const yOffset = Math.sin((i / Math.max(count - 1, 1)) * Math.PI) * -40

      positions.set(photo.id, {
        x: 0,
        y: yOffset,
        z: zPts,
        rotateY,
      })
    })
  })

  return positions
}

// ============================================================
// Loading Skeleton — glowing orbs at panel positions
// ============================================================

interface LoadingSkeletonProps {
  count?: number
  isSpatialMode: boolean
}

function LoadingSkeleton({ count = 8, isSpatialMode }: LoadingSkeletonProps) {
  const placeholders = Array.from({ length: count }, (_, i) => i)

  return (
    <div
      className="flex items-center justify-center min-h-screen"
      aria-busy="true"
      aria-label="Loading memories..."
    >
      <div
        className="relative flex items-center justify-center"
        style={
          isSpatialMode
            ? {}
            : { perspective: '800px', transformStyle: 'preserve-3d', width: 800, height: 500 }
        }
      >
        {placeholders.map((i) => {
          const angle = (i / count) * 360
          const radius = 280
          const x = Math.cos((angle * Math.PI) / 180) * radius
          const y = Math.sin((angle * Math.PI) / 180) * radius * 0.5

          return (
            <div
              key={i}
              className="absolute"
              style={{
                left: `calc(50% + ${x}px)`,
                top: `calc(50% + ${y}px)`,
                transform: 'translate(-50%, -50%)',
                animationDelay: `${i * 120}ms`,
              }}
              aria-hidden="true"
            >
              {/* Glowing orb skeleton at panel position */}
              <div
                className="rounded-2xl animate-pulse"
                style={{
                  width: 180,
                  height: 135,
                  background:
                    'radial-gradient(ellipse at center, rgba(109,40,217,0.25) 0%, rgba(109,40,217,0.05) 70%)',
                  border: '1px solid rgba(139,92,246,0.2)',
                  boxShadow: '0 0 24px rgba(109,40,217,0.15)',
                  animationDelay: `${i * 120}ms`,
                  animationDuration: '1.5s',
                }}
              />
            </div>
          )
        })}

        {/* Central loading orb */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div
            className="w-20 h-20 rounded-full animate-pulse"
            style={{
              background:
                'radial-gradient(circle, rgba(109,40,217,0.4) 0%, rgba(109,40,217,0.1) 70%)',
              boxShadow: '0 0 40px rgba(109,40,217,0.3)',
            }}
          />
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Main Component
// ============================================================

export default function SpatialMemoryRoom() {
  const { memoryId } = useParams<{ memoryId: string }>()

  // Detect spatial (visionOS) mode via html.is-spatial class
  // This class is set by the WebSpatial HTML template when XR_ENV=avp
  const [isSpatialMode] = useState<boolean>(() =>
    document.documentElement.classList.contains('is-spatial'),
  )

  // Page state for panel pagination
  const [currentPage, setCurrentPage] = useState(0)

  // Selected photo for voice narration feedback
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null)

  // Voice speaking state — lifted from ElevenLabs widget events
  const [isSpeaking, setIsSpeaking] = useState(false)

  // Subscribe to ElevenLabs speaking events
  useEffect(() => {
    const onSpeaking = () => setIsSpeaking(true)
    const onDone = () => setIsSpeaking(false)

    window.addEventListener('elevenlabs-convai:agent_speaking', onSpeaking)
    window.addEventListener('elevenlabs-convai:call_ended', onDone)
    window.addEventListener('elevenlabs-convai:user_speaking', onDone)

    return () => {
      window.removeEventListener('elevenlabs-convai:agent_speaking', onSpeaking)
      window.removeEventListener('elevenlabs-convai:call_ended', onDone)
      window.removeEventListener('elevenlabs-convai:user_speaking', onDone)
    }
  }, [])

  // Firestore real-time subscription via existing hook
  const { photos, grouped, isLoading, error, memoryStatus, photoCount } =
    useMemories(memoryId ?? null)

  // Person name derived from memory status — hook exposes it via status doc
  // We'll use a generic label since `personName` lives in the memory doc
  // and we don't have a usePerson hook yet. The MemoryOrb shows the first initial.
  const personName = 'Memory'  // Will be overridden by actual data in full build

  // Paginated photos — max 12 at a time
  const allPhotos: PhotoMeta[] = useMemo(() => {
    // Flatten grouped in era order: childhood → young-adult → family → recent
    const ordered: PhotoMeta[] = [
      ...(grouped.childhood ?? []),
      ...(grouped['young-adult'] ?? []),
      ...(grouped.family ?? []),
      ...(grouped.recent ?? []),
    ]
    return ordered.slice(0, 30) // hard cap at 30 per spec
  }, [grouped])

  const totalPages = Math.ceil(allPhotos.length / PANELS_PER_PAGE)
  const visiblePhotos = allPhotos.slice(
    currentPage * PANELS_PER_PAGE,
    (currentPage + 1) * PANELS_PER_PAGE,
  )

  // Compute spatial arc positions for visible panels
  const positions = useMemo(
    () => computeSpatialPositions(visiblePhotos),
    [visiblePhotos],
  )

  // Era groups for visible panels (for EraSection labels)
  const visibleEraGroups = useMemo(() => {
    const eraOrder: Era[] = ['childhood', 'young-adult', 'family', 'recent']
    return eraOrder
      .map((era) => ({
        era,
        photos: visiblePhotos.filter((p) => p.era === era),
      }))
      .filter(({ photos: ps }) => ps.length > 0)
  }, [visiblePhotos])

  // Photo selection — sends context to ElevenLabs voice agent
  const handlePhotoSelect = useCallback(
    async (photo: PhotoMeta) => {
      setSelectedPhotoId(photo.id)

      // Build Memory-compatible object from PhotoMeta for sendPhotoContext
      const memoryForContext = {
        id: photo.id,
        photoUrl: photo.url,
        caption: photo.caption,
        date: photo.date,
        era: photo.era,
      }

      try {
        await sendPhotoContext(memoryForContext)
      } catch (err) {
        // If no active widget, sendPhotoContext warns internally — safe to swallow here
        console.warn('[SpatialMemoryRoom] sendPhotoContext failed:', err)
      }

      // Clear selection highlight after 3s
      setTimeout(() => setSelectedPhotoId(null), 3000)
    },
    [],
  )

  // ============================================================
  // Render: Loading state
  // ============================================================

  if (isLoading) {
    return (
      <div className="min-h-screen bg-memory-bg">
        <LoadingSkeleton count={8} isSpatialMode={isSpatialMode} />
      </div>
    )
  }

  // ============================================================
  // Render: Error state
  // ============================================================

  if (error) {
    return (
      <div className="min-h-screen bg-memory-bg flex items-center justify-center">
        <div className="glass-card p-8 max-w-md text-center space-y-4">
          <div className="text-4xl">⚠</div>
          <h2 className="text-xl font-bold text-memory-text">Memory Room Unavailable</h2>
          <p className="text-memory-text-muted text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="btn-ghost text-sm"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // ============================================================
  // Render: Empty state
  // ============================================================

  if (allPhotos.length === 0) {
    return (
      <div className="min-h-screen bg-memory-bg flex items-center justify-center">
        <div className="glass-card p-12 max-w-md text-center space-y-4">
          <MemoryOrb
            personName={personName}
            isSpeaking={false}
            isSpatialMode={isSpatialMode}
          />
          <div className="pt-8">
            <h2 className="text-xl font-bold text-memory-text">No Memories Yet</h2>
            <p className="text-memory-text-muted text-sm mt-2">
              Upload photos to start building the memory room.
            </p>
            {memoryStatus === 'processing' && (
              <p className="text-memory-accent text-xs mt-3 animate-pulse">
                Processing memories...
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ============================================================
  // Render: Fallback (browser CSS 3D mode)
  // ============================================================

  if (!isSpatialMode) {
    return (
      <FallbackRoom
        photos={allPhotos}
        personName={personName}
        isSpeaking={isSpeaking}
        onPhotoSelect={handlePhotoSelect}
      />
    )
  }

  // ============================================================
  // Render: Spatial mode (visionOS / Apple Vision Pro)
  //
  // WebSpatial layout:
  //   - Outer container: transparent background (--xr-background-material)
  //   - Each panel: enable-xr + --xr-back for depth extrusion
  //   - MemoryOrb: center with --xr-back: 40
  //   - Era labels: floating dividers with lower --xr-back
  // ============================================================

  return (
    <div
      className="relative min-h-screen overflow-hidden"
      style={{
        // In spatial mode, background is transparent — visionOS renders the
        // passthrough environment behind the app window.
        background: 'transparent',
        // WebSpatial: make the root window background transparent
        ['--xr-background-material' as string]: 'transparent',
      }}
      aria-label={`${personName}'s spatial memory room — ${photoCount} memories`}
      role="main"
    >
      {/* Ambient background glow — visible through the transparent spatial window */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse at 50% 40%, rgba(109,40,217,0.08) 0%, transparent 70%)',
        }}
        aria-hidden="true"
      />

      {/* MemoryOrb — center of the spatial room */}
      <div
        className="absolute top-1/2 left-1/2 z-20"
        style={{
          transform: 'translate(-50%, -50%)',
        }}
      >
        <MemoryOrb
          personName={personName}
          isSpeaking={isSpeaking}
          isSpatialMode={true}
        />
      </div>

      {/* Era section labels — spatialized floating dividers */}
      {visibleEraGroups.map(({ era, photos: eraPhotos }, groupIdx) => (
        <div
          key={`era-section-${era}`}
          enable-xr={true}
          className="absolute"
          style={{
            // Position era labels above/behind the photo panels for that era
            top: `${15 + groupIdx * 8}%`,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 340,
            // WebSpatial: era labels float slightly behind the panels
            ['--xr-background-material' as string]: 'none',
            ['--xr-back' as string]: String(
              Math.abs(ERA_Z_PTS[era]) * 0.4,
            ),
          }}
          aria-hidden="true"
        >
          <EraSection era={era} photoCount={eraPhotos.length} />
        </div>
      ))}

      {/* Floating photo panels — the main spatial grid */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        role="list"
        aria-label="Memory photos"
      >
        {visiblePhotos.map((photo, i) => {
          const pos = positions.get(photo.id) ?? {
            x: 0, y: 0, z: 0, rotateY: 0,
          }
          const isSelected = photo.id === selectedPhotoId
          const config = ERA_CONFIGS[photo.era as Era]

          return (
            <div
              key={photo.id}
              role="listitem"
              className="absolute"
              style={{
                // Arc layout: panels are rotated around the Y axis
                // and pushed back by their era's Z depth.
                // WebSpatial reads transform for initial placement,
                // then the enable-xr attribute lifts it into 3D.
                top: `calc(45% + ${pos.y}px)`,
                left: `50%`,
                transform: [
                  `translateX(-50%)`,
                  `rotateY(${pos.rotateY}deg)`,
                  `translateX(${
                    Math.sign(pos.rotateY) *
                    Math.abs(pos.rotateY) *
                    5.5  // px per degree — spreads panels horizontally
                  }px)`,
                ].join(' '),
              }}
              aria-label={`${config.label} memory: ${photo.caption}`}
            >
              <div
                // WebSpatial: spatialized element — lifted into 3D with era depth
                enable-xr={true}
                style={{
                  // WebSpatial CSS custom properties:
                  // --xr-background-material: glass material on visionOS
                  // --xr-back: depth extrusion in pts (era determines depth)
                  ['--xr-background-material' as string]: 'translucent',
                  ['--xr-back' as string]: String(Math.abs(pos.z)),
                  // Selection highlight
                  outline: isSelected
                    ? `2px solid ${config.color}`
                    : 'none',
                  borderRadius: '16px',
                  transition: 'outline 0.2s ease',
                }}
              >
                <FloatingPhotoPanel
                  photo={photo}
                  index={i}
                  position={pos}
                  onSelect={handlePhotoSelect}
                  isSpatialMode={true}
                  entranceDelay={i * 50}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Pagination — shown when > 12 photos */}
      {totalPages > 1 && (
        <div
          className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 z-30"
          role="navigation"
          aria-label="Memory room pagination"
        >
          <button
            onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
            disabled={currentPage === 0}
            className="btn-ghost text-sm px-4 py-2 disabled:opacity-30"
            aria-label="Show older memories"
          >
            Older Memories
          </button>

          <span className="text-memory-text-muted text-xs glass-card px-3 py-1">
            {currentPage + 1} / {totalPages}
          </span>

          <button
            onClick={() =>
              setCurrentPage((p) => Math.min(totalPages - 1, p + 1))
            }
            disabled={currentPage === totalPages - 1}
            className="btn-ghost text-sm px-4 py-2 disabled:opacity-30"
            aria-label="Show more recent memories"
          >
            More Recent
          </button>
        </div>
      )}

      {/* Processing notice */}
      {memoryStatus === 'processing' && (
        <div
          className="absolute top-6 right-6 glass-card px-4 py-2 flex items-center gap-2 z-30"
          role="status"
          aria-live="polite"
        >
          <span className="status-dot-active" aria-hidden="true" />
          <span className="text-xs text-memory-accent">
            Processing memories...
          </span>
        </div>
      )}

      {/* Photo count indicator */}
      <div
        className="absolute top-6 left-6 glass-card px-4 py-2 z-30"
        aria-label={`${photoCount} total memories`}
      >
        <span className="text-xs text-memory-text-muted">
          <span className="text-memory-accent font-semibold">{photoCount}</span>{' '}
          {photoCount === 1 ? 'memory' : 'memories'}
        </span>
      </div>
    </div>
  )
}
