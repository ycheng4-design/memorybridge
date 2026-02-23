import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ProcessingStage } from '@/types'

// ============================================================
// Stage Configuration
// ============================================================

interface StageConfig {
  id: ProcessingStage
  label: string
  description: string
  icon: React.ReactNode
  color: string
  durationEstimate: string
}

const UploadIcon: React.FC<{ isActive: boolean }> = ({ isActive }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`transition-colors duration-300 ${isActive ? 'text-memory-accent' : 'text-current'}`}
  >
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" x2="12" y1="3" y2="15" />
  </svg>
)

const VoiceIcon: React.FC<{ isActive: boolean }> = ({ isActive }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`transition-colors duration-300 ${isActive ? 'text-memory-accent' : 'text-current'}`}
  >
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" x2="12" y1="19" y2="22" />
  </svg>
)

const BrainIcon: React.FC<{ isActive: boolean }> = ({ isActive }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`transition-colors duration-300 ${isActive ? 'text-memory-accent' : 'text-current'}`}
  >
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.8 3 3 0 0 1 .34-5.58 2.5 2.5 0 0 1 1.32-4.24A2.5 2.5 0 0 1 9.5 2Z" />
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.8 3 3 0 0 0-.34-5.58 2.5 2.5 0 0 0-1.32-4.24A2.5 2.5 0 0 0 14.5 2Z" />
  </svg>
)

const CheckIcon: React.FC = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

const STAGE_ORDER: ProcessingStage[] = ['uploading', 'cloning', 'embedding', 'ready']

const STAGES: StageConfig[] = [
  {
    id: 'uploading',
    label: 'Uploading memories',
    description: 'Securely transferring your photos and voice recording to our servers',
    icon: <UploadIcon isActive={false} />,
    color: 'text-blue-400',
    durationEstimate: '~10s',
  },
  {
    id: 'cloning',
    label: 'Cloning their voice',
    description: 'Creating a personalized voice clone that speaks with their unique warmth',
    icon: <VoiceIcon isActive={false} />,
    color: 'text-violet-400',
    durationEstimate: '~30s',
  },
  {
    id: 'embedding',
    label: 'Building memory map',
    description: 'Generating AI embeddings so they can find and discuss each memory by voice',
    icon: <BrainIcon isActive={false} />,
    color: 'text-memory-accent',
    durationEstimate: '~20s',
  },
  {
    id: 'ready',
    label: 'Ready to remember',
    description: 'Everything is set — time to share memories together',
    icon: <CheckIcon />,
    color: 'text-emerald-400',
    durationEstimate: 'Done!',
  },
]

// ============================================================
// Floating Particles
// ============================================================

interface Particle {
  id: number
  x: number
  y: number
  size: number
  duration: number
  delay: number
}

const FloatingParticles: React.FC = () => {
  const particles: Particle[] = Array.from({ length: 12 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: 2 + Math.random() * 4,
    duration: 4 + Math.random() * 4,
    delay: Math.random() * 4,
  }))

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-3xl">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full bg-memory-accent/30"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
          }}
          animate={{
            y: [-20, 20, -20],
            opacity: [0.1, 0.6, 0.1],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}

// ============================================================
// Stage Indicator
// ============================================================

interface StageIndicatorProps {
  stage: StageConfig
  status: 'pending' | 'active' | 'complete'
  index: number
}

const StageIndicator: React.FC<StageIndicatorProps> = ({ stage, status, index }) => {
  const isActive = status === 'active'
  const isComplete = status === 'complete'
  const isPending = status === 'pending'

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
      className={`flex items-center gap-4 p-4 rounded-xl transition-all duration-300
        ${isActive ? 'bg-memory-accent/10 border border-memory-accent/30' : ''}
        ${isComplete ? 'opacity-70' : ''}
        ${isPending ? 'opacity-40' : ''}
      `}
    >
      {/* Icon container */}
      <div
        className={`
          w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0
          transition-all duration-300
          ${isActive ? 'bg-memory-accent/20 animate-pulse-glow' : ''}
          ${isComplete ? 'bg-emerald-500/20' : ''}
          ${isPending ? 'bg-white/5' : ''}
        `}
      >
        {isComplete ? (
          <span className="text-emerald-400">
            <CheckIcon />
          </span>
        ) : (
          <span className={isActive ? stage.color : 'text-memory-text-muted'}>
            {stage.icon}
          </span>
        )}
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p
            className={`font-semibold text-sm transition-colors duration-300
            ${isActive ? 'text-memory-text' : isComplete ? 'text-memory-text/70' : 'text-memory-text-muted'}`}
          >
            {stage.label}
          </p>
          {isActive && (
            <span className="text-xs text-memory-accent/70">{stage.durationEstimate}</span>
          )}
        </div>
        <p className={`text-xs transition-colors duration-300
          ${isActive ? 'text-memory-text-muted' : 'text-memory-text-muted/60'}`}
        >
          {stage.description}
        </p>
      </div>

      {/* Active spinner */}
      {isActive && (
        <div className="flex-shrink-0">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
            className="w-5 h-5 rounded-full border-2 border-memory-accent/30 border-t-memory-accent"
          />
        </div>
      )}
    </motion.div>
  )
}

// ============================================================
// Progress Bar
// ============================================================

interface ProgressBarProps {
  stage: ProcessingStage
  progress: number
}

const ProgressBar: React.FC<ProgressBarProps> = ({ stage, progress }) => {
  const stageIndex = STAGE_ORDER.indexOf(stage)
  const totalStages = STAGE_ORDER.length - 1 // 'ready' doesn't count
  const stageProgress = stageIndex / totalStages
  const withinStageProgress = progress / 100 / totalStages
  const totalProgress = Math.min(
    (stageProgress + withinStageProgress) * 100,
    100
  )

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-memory-text-muted">Building your memory...</span>
        <span className="text-memory-accent font-medium tabular-nums">
          {Math.round(totalProgress)}%
        </span>
      </div>
      <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-gradient-to-r from-memory-accent to-memory-accent-dim rounded-full"
          initial={{ width: '0%' }}
          animate={{ width: `${totalProgress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

// ============================================================
// Main ProcessingScreen Component
// ============================================================

interface ProcessingScreenProps {
  stage: ProcessingStage
  uploadProgress: number
  personName?: string
  onViewMemory?: () => void
  onRetry?: () => void
  error?: string | null
}

const MEMORY_QUOTES = [
  '"The heart never forgets the ones it loves."',
  '"Memories are the treasures that we keep locked deep within the storehouse of our souls."',
  '"In every moment you can\'t remember, someone loves you who does."',
  '"Love is not what the mind thinks, but what the heart feels."',
]

export const ProcessingScreen: React.FC<ProcessingScreenProps> = ({
  stage,
  uploadProgress,
  personName = 'your loved one',
  onViewMemory,
  onRetry,
  error,
}) => {
  const [quoteIndex, setQuoteIndex] = useState(0)

  // Cycle quotes every 8 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setQuoteIndex((i) => (i + 1) % MEMORY_QUOTES.length)
    }, 8000)
    return () => clearInterval(interval)
  }, [])

  const currentStageIndex = STAGE_ORDER.indexOf(stage)

  const getStageStatus = (stageId: ProcessingStage): 'pending' | 'active' | 'complete' => {
    const idx = STAGE_ORDER.indexOf(stageId)
    if (idx < currentStageIndex) return 'complete'
    if (idx === currentStageIndex) return 'active'
    return 'pending'
  }

  return (
    <div className="min-h-screen bg-memory-bg flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Main card */}
        <div className="relative glass-card p-8 md:p-10 overflow-hidden">
          <FloatingParticles />

          {/* Radial glow */}
          <div className="absolute inset-0 bg-radial-purple pointer-events-none rounded-3xl" />

          <div className="relative z-10 space-y-8">
            {/* Header */}
            <div className="text-center space-y-3">
              {/* Logo mark */}
              <motion.div
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                className="w-16 h-16 mx-auto rounded-2xl bg-memory-accent/15 border border-memory-accent/30
                           flex items-center justify-center"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#f4c430"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
                </svg>
              </motion.div>

              <div>
                <h1 className="text-2xl font-bold font-heading text-gradient-gold">
                  Building Memories
                </h1>
                <p className="text-memory-text-muted text-sm mt-1">
                  Creating a memory bridge for{' '}
                  <span className="text-memory-text font-medium">{personName}</span>
                </p>
              </div>
            </div>

            {/* Progress bar */}
            {stage !== 'ready' && (
              <ProgressBar stage={stage} progress={uploadProgress} />
            )}

            {/* Stage list */}
            <div className="space-y-2">
              {STAGES.map((s, i) => (
                <StageIndicator
                  key={s.id}
                  stage={s}
                  status={getStageStatus(s.id)}
                  index={i}
                />
              ))}
            </div>

            {/* Ready state CTA */}
            <AnimatePresence>
              {stage === 'ready' && !error && (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="space-y-4"
                >
                  <div className="text-center text-sm text-emerald-400 font-medium">
                    All memories have been processed and are ready to explore
                  </div>
                  {onViewMemory && (
                    <button
                      type="button"
                      onClick={onViewMemory}
                      className="btn-gold w-full text-center justify-center flex items-center gap-2 animate-pulse-glow"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
                      </svg>
                      View Memories
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error state */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-5 rounded-xl bg-red-500/10 border border-red-400/30 space-y-3 text-center"
              >
                <p className="text-sm text-red-400">{error}</p>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="inline-flex items-center gap-2 px-5 py-2 bg-red-500 text-white
                               rounded-full text-sm font-medium hover:bg-red-400 active:scale-95
                               transition-all duration-200"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                      <path d="M3 3v5h5"/>
                    </svg>
                    Try again
                  </button>
                )}
              </motion.div>
            )}
          </div>
        </div>

        {/* Rotating quote */}
        <AnimatePresence mode="wait">
          <motion.div
            key={quoteIndex}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.5 }}
            className="mt-8 text-center px-4"
          >
            <p className="text-sm text-memory-text-muted italic leading-relaxed">
              {MEMORY_QUOTES[quoteIndex]}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

export default ProcessingScreen
