import { useState, useMemo } from 'react'
import type { PhotoMeta, Era } from '@/types'
import { ERA_CONFIGS } from '@/types'
import FloatingPhotoPanel from './FloatingPhotoPanel'
import EraSection from './EraSection'
import MemoryOrb from './MemoryOrb'

// ============================================================
// FallbackRoom — CSS 3D Memory Room (no Apple Silicon required)
//
// Renders when window.__WEBSPATIAL_ENV__ is falsy / when the
// <html> element does not carry the is-spatial class.
//
// Layout:
//   - perspective: 1200px on the outer container
//   - transformStyle: preserve-3d on the scene
//   - Photos arranged in an arc: translateZ(-era * 80px) rotateY(i * 15deg)
//   - Era sections interleaved as depth-positioned labels
//
// Panel overlap prevention:
//   - Per-era spacing: each panel is 15deg apart in Y rotation
//   - Maximum 12 panels visible (paginated above that)
//   - Minimum 80px Z-separation between eras guarantees < 20% overlap
// ============================================================

const ERA_Z_OFFSETS: Record<Era, number> = {
  childhood:    -3 * 80,  // -240px
  'young-adult':-2 * 80,  // -160px
  family:       -1 * 80,  // -80px
  recent:        0,        // 0px (closest)
}

const MAX_VISIBLE = 12
const PANELS_PER_PAGE = MAX_VISIBLE

interface FallbackRoomProps {
  photos: PhotoMeta[]
  personName: string
  isSpeaking: boolean
  onPhotoSelect: (photo: PhotoMeta) => void
}

interface PanelPosition {
  x: number
  y: number
  z: number
  rotateY: number
}

/**
 * Compute arc layout positions for a set of photos.
 * Photos within an era are spread in a Y-rotation arc.
 * Z-depth is determined by era.
 * No two panels within the same era overlap more than 20%.
 */
function computeArcPositions(photos: PhotoMeta[]): Map<string, PanelPosition> {
  const positions = new Map<string, PanelPosition>()

  // Group by era to handle intra-era arc spread
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

    const zBase = ERA_Z_OFFSETS[era]

    // Spread photos in a Y-rotation arc centered at 0°
    // Each panel is 15° apart — a 200px-wide card at 800px radius
    // only overlaps ~0% with 15° spacing (arc length >> card width).
    const arcStep = 15  // degrees
    const startAngle = -((count - 1) * arcStep) / 2

    eraPhotos.forEach((photo, i) => {
      const rotateY = startAngle + i * arcStep

      // Y position: slight vertical offset to create depth variation
      const yOffset = Math.sin((i / Math.max(count - 1, 1)) * Math.PI) * -30

      positions.set(photo.id, {
        x: 0,        // rotateY handles horizontal spread
        y: yOffset,
        z: zBase,
        rotateY,
      })
    })
  })

  return positions
}

/** Pagination state — tracks which page of photos to show */
function usePagination(photos: PhotoMeta[], pageSize: number) {
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(photos.length / pageSize)
  const visible = photos.slice(page * pageSize, (page + 1) * pageSize)

  return { visible, page, totalPages, setPage }
}

export default function FallbackRoom({
  photos,
  personName,
  isSpeaking,
  onPhotoSelect,
}: FallbackRoomProps) {
  const { visible, page, totalPages, setPage } = usePagination(
    photos,
    PANELS_PER_PAGE,
  )

  const positions = useMemo(
    () => computeArcPositions(visible),
    [visible],
  )

  // Group visible photos by era for section dividers
  const eraGroups = useMemo(() => {
    const groups: { era: Era; photos: PhotoMeta[] }[] = []
    const seen = new Set<Era>()
    const order: Era[] = ['childhood', 'young-adult', 'family', 'recent']

    order.forEach((era) => {
      const eraPhotos = visible.filter((p) => p.era === era)
      if (eraPhotos.length > 0 && !seen.has(era)) {
        groups.push({ era, photos: eraPhotos })
        seen.add(era)
      }
    })

    return groups
  }, [visible])

  return (
    <div className="relative min-h-screen bg-memory-bg overflow-hidden flex flex-col animate-page-enter">
      {/* Ambient radial glow behind the 3D scene */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at 50% 45%, rgba(109,40,217,0.12) 0%, transparent 65%)',
        }}
        aria-hidden="true"
      />

      {/* Browser mode label */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20">
        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-memory-bg-secondary border border-white/10 text-memory-text-muted">
          3D Memory Room (Browser Mode)
        </span>
      </div>

      {/* 3D scene wrapper — perspective applied here */}
      <div
        className="flex-1 flex items-center justify-center py-20"
        style={{ perspective: '1200px' }}
        aria-label={`${personName}'s memory room — ${photos.length} memories`}
      >
        <div
          className="relative"
          style={{
            transformStyle: 'preserve-3d',
            width: 900,
            height: 600,
          }}
        >
          {/* Central MemoryOrb at origin */}
          <div
            className="absolute top-1/2 left-1/2"
            style={{
              transform: 'translate(-50%, -50%) translateZ(0px)',
              transformStyle: 'preserve-3d',
              zIndex: 10,
            }}
          >
            <MemoryOrb
              personName={personName}
              isSpeaking={isSpeaking}
              isSpatialMode={false}
            />
          </div>

          {/* Era section dividers */}
          {eraGroups.map(({ era, photos: eraPhotos }) => {
            const zDepth = ERA_Z_OFFSETS[era]
            return (
              <div
                key={`era-label-${era}`}
                className="absolute"
                style={{
                  top: '10%',
                  left: '50%',
                  transform: `translate(-50%, 0) translateZ(${zDepth}px)`,
                  transformStyle: 'preserve-3d',
                  width: 320,
                  zIndex: 5,
                }}
                aria-hidden="true"
              >
                <EraSection era={era} photoCount={eraPhotos.length} />
              </div>
            )
          })}

          {/* Photo panels arranged in 3D arc */}
          {visible.map((photo, i) => {
            const pos = positions.get(photo.id) ?? { x: 0, y: 0, z: 0, rotateY: 0 }
            const config = ERA_CONFIGS[photo.era as Era]

            return (
              <div
                key={photo.id}
                className="absolute"
                style={{
                  top: '50%',
                  left: '50%',
                  // Arc positioning: rotate around Y axis then push back on Z.
                  // The 280px translateX offsets the card from center before rotating
                  // so cards spread along an arc rather than spinning in place.
                  transform: [
                    `rotateY(${pos.rotateY}deg)`,
                    `translateX(${pos.rotateY !== 0 ? (pos.rotateY > 0 ? 280 : -280) * Math.abs(Math.sin(pos.rotateY * Math.PI / 180)) : 0}px)`,
                    `translateY(calc(-50% + ${pos.y}px))`,
                    `translateZ(${pos.z}px)`,
                    `translateX(-50%)`,
                  ].join(' '),
                  transformStyle: 'preserve-3d',
                  zIndex: Math.round(pos.z + 300),  // closer = higher z-index
                }}
                aria-label={`${config.label} memory: ${photo.caption}`}
              >
                <FloatingPhotoPanel
                  photo={photo}
                  index={i}
                  position={pos}
                  onSelect={onPhotoSelect}
                  isSpatialMode={false}
                  entranceDelay={i * 50}
                />
              </div>
            )
          })}
        </div>
      </div>

      {/* Era legend at bottom */}
      <div className="flex justify-center gap-4 pb-4 px-4 flex-wrap" aria-label="Era legend">
        {eraGroups.map(({ era, photos: eraPhotos }) => {
          const config = ERA_CONFIGS[era]
          return (
            <div key={era} className="flex items-center gap-1.5">
              <span className={`text-base ${config.textColor}`} aria-hidden="true">
                {config.icon}
              </span>
              <span className={`text-xs font-medium ${config.textColor}`}>
                {config.label}
              </span>
              <span className="text-xs text-memory-text-muted">
                ({eraPhotos.length})
              </span>
            </div>
          )
        })}
      </div>

      {/* Pagination controls — shown only if more than PANELS_PER_PAGE photos */}
      {totalPages > 1 && (
        <div
          className="flex items-center justify-center gap-4 pb-6"
          role="navigation"
          aria-label="Memory pagination"
        >
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="btn-ghost text-sm px-4 py-2 disabled:opacity-30"
            aria-label="Previous page of memories"
          >
            Older
          </button>

          <span className="text-memory-text-muted text-xs">
            {page + 1} / {totalPages}
          </span>

          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
            className="btn-ghost text-sm px-4 py-2 disabled:opacity-30"
            aria-label="Next page of memories"
          >
            More Recent
          </button>
        </div>
      )}
    </div>
  )
}
