import { useId, useEffect, useRef } from 'react'
import { useVoiceAgent } from '@/hooks/useVoiceAgent'
import { sendPhotoContext, getConfiguredAgentId } from '@/services/elevenlabs'
import type { Memory, PhotoMeta, VoiceAgentStatus } from '@/types'

// ============================================================
// VoiceWidget — ElevenLabs Conversational AI embed
// ============================================================

interface VoiceWidgetProps {
  /** ElevenLabs agent_id. Falls back to VITE_ELEVENLABS_AGENT_ID if omitted. */
  agentId?: string
  /** Firestore memory document ID — used to scope the conversation context. */
  memoryId?: string
  /** Person name shown in the widget header and passed to the agent. */
  personName?: string
  /** All photos in the session — used to prime the agent at start. */
  photos?: PhotoMeta[]
  /** Currently selected / focused photo memory. When set, context is sent. */
  activeMemory?: Memory | null
  /** Additional Tailwind classes for the outer container. */
  className?: string
}

// ---------------------------------------------------------------------------
// VoiceOrb — animated microphone indicator
// ---------------------------------------------------------------------------

interface VoiceOrbProps {
  status: VoiceAgentStatus
  isSpeaking: boolean
  isListening: boolean
  onClick: () => void
}

function VoiceOrb({ status, isSpeaking, isListening, onClick }: VoiceOrbProps) {
  const isPulsing = isSpeaking || isListening
  const isConnecting = status === 'connecting'
  const isError = status === 'error'

  // Pick ring colour by status
  const ringClass = isError
    ? 'ring-red-500/60'
    : isSpeaking
    ? 'ring-violet-400/80'
    : isListening
    ? 'ring-emerald-400/80'
    : isConnecting
    ? 'ring-amber-400/60'
    : 'ring-white/20'

  // Pick orb fill colour by status
  const orbClass = isError
    ? 'bg-red-900/60'
    : isSpeaking
    ? 'bg-violet-800/70'
    : isListening
    ? 'bg-emerald-800/70'
    : 'bg-white/10'

  // Accessible label
  const ariaLabel =
    status === 'connected'
      ? 'Voice agent ready — click to speak'
      : status === 'speaking'
      ? 'Agent is speaking'
      : status === 'listening'
      ? 'Listening to you'
      : status === 'connecting'
      ? 'Connecting to voice agent…'
      : status === 'error'
      ? 'Voice agent error — click to retry'
      : 'Activate voice companion'

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={[
        'relative flex items-center justify-center',
        'w-20 h-20 rounded-full',
        'ring-2 transition-all duration-300',
        orbClass,
        ringClass,
        isSpeaking ? 'animate-pulse-glow-purple' : '',
        'hover:scale-105 active:scale-95',
        'focus:outline-none focus-visible:ring-4 focus-visible:ring-white/40',
        'cursor-pointer select-none',
      ].join(' ')}
    >
      {/* Ping animation — visible when agent is active */}
      {isPulsing && (
        <span
          aria-hidden="true"
          className={[
            'absolute inset-0 rounded-full animate-ping opacity-30',
            isSpeaking ? 'bg-violet-400' : 'bg-emerald-400',
          ].join(' ')}
        />
      )}

      {/* Connecting spinner */}
      {isConnecting && (
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-full border-2 border-t-amber-400 border-white/10 animate-spin"
        />
      )}

      {/* Microphone icon */}
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={[
          'w-8 h-8 transition-colors duration-200',
          isError
            ? 'text-red-300'
            : isSpeaking
            ? 'text-violet-200'
            : isListening
            ? 'text-emerald-200'
            : 'text-white/70',
        ].join(' ')}
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    </button>
  )
}

// ---------------------------------------------------------------------------
// StatusBadge — small pill showing current agent state
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: VoiceAgentStatus }) {
  const config: Record<VoiceAgentStatus, { label: string; classes: string }> = {
    disconnected: {
      label: 'Tap orb to connect',
      classes: 'bg-white/10 text-white/50',
    },
    connecting: {
      label: 'Connecting…',
      classes: 'bg-amber-500/20 text-amber-300',
    },
    connected: {
      label: 'Ready to listen',
      classes: 'bg-emerald-500/20 text-emerald-300',
    },
    speaking: {
      label: 'Speaking…',
      classes: 'bg-violet-500/20 text-violet-300',
    },
    listening: {
      label: 'Listening…',
      classes: 'bg-emerald-500/20 text-emerald-200',
    },
    error: {
      label: 'Connection error',
      classes: 'bg-red-500/20 text-red-300',
    },
  }

  const { label, classes } = config[status]

  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium',
        classes,
      ].join(' ')}
    >
      {/* Pulsing dot for active states */}
      {(status === 'speaking' || status === 'listening') && (
        <span
          aria-hidden="true"
          className={[
            'w-1.5 h-1.5 rounded-full animate-pulse',
            status === 'speaking' ? 'bg-violet-400' : 'bg-emerald-400',
          ].join(' ')}
        />
      )}
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// PhotoContextBanner — shows which photo is active
// ---------------------------------------------------------------------------

function PhotoContextBanner({ memory }: { memory: Memory }) {
  return (
    <div
      className={[
        'flex items-start gap-3 px-4 py-3 rounded-xl',
        'bg-white/5 border border-white/10',
        'text-sm text-white/70',
      ].join(' ')}
      role="status"
      aria-live="polite"
    >
      {/* Thumbnail */}
      {memory.photoUrl && (
        <img
          src={memory.photoUrl}
          alt=""
          aria-hidden="true"
          className="w-10 h-10 rounded-lg object-cover flex-shrink-0 opacity-80"
        />
      )}

      <div className="min-w-0">
        <p className="text-xs text-white/40 mb-0.5 uppercase tracking-wide font-medium">
          Asking about
        </p>
        <p className="truncate text-white/80 font-medium leading-snug">
          {memory.caption}
        </p>
        <p className="text-xs text-white/40 mt-0.5">{memory.date}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ConfigurationPlaceholder — shown when agent ID is not configured
// ---------------------------------------------------------------------------

function ConfigurationPlaceholder() {
  return (
    <div
      role="status"
      className={[
        'flex flex-col items-center gap-4 px-6 py-8',
        'rounded-2xl border border-dashed border-white/20',
        'bg-white/5 text-center',
      ].join(' ')}
    >
      {/* Muted orb */}
      <div className="w-16 h-16 rounded-full bg-white/5 ring-1 ring-white/15 flex items-center justify-center">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="w-7 h-7 text-white/25"
        >
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      </div>

      <div>
        <p className="text-white/50 text-sm font-medium mb-1">
          Voice agent unavailable
        </p>
        <p className="text-white/30 text-xs leading-relaxed max-w-[220px]">
          Set{' '}
          <code className="font-mono bg-white/10 px-1 rounded text-white/50">
            VITE_ELEVENLABS_AGENT_ID
          </code>{' '}
          in your{' '}
          <code className="font-mono bg-white/10 px-1 rounded text-white/50">
            .env
          </code>{' '}
          file to enable voice memories.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main VoiceWidget component
// ---------------------------------------------------------------------------

/**
 * VoiceWidget — ElevenLabs Conversational AI embed for MemoryBridge.
 *
 * Renders a voice orb that the caregiver or family member taps to start a
 * conversation with the person's cloned-voice memory companion. The widget
 * automatically primes the agent with photo context when activeMemory changes.
 *
 * Falls back gracefully when VITE_ELEVENLABS_AGENT_ID is not configured.
 *
 * @example
 * ```tsx
 * <VoiceWidget
 *   personName="Dorothy"
 *   memoryId={memoryId}
 *   photos={photos}
 *   activeMemory={selectedPhoto}
 * />
 * ```
 */
export function VoiceWidget({
  agentId: agentIdProp,
  memoryId,
  personName = 'your loved one',
  photos = [],
  activeMemory,
  className = '',
}: VoiceWidgetProps) {
  const containerId = useId()
  const sentMemoryIdRef = useRef<string | null>(null)

  // Resolve agent ID — prop takes priority, then env var
  const resolvedAgentId = agentIdProp ?? getConfiguredAgentId() ?? undefined

  const { agentState, initAgent, destroyAgent, isReady, isActive, hasError } =
    useVoiceAgent({
      agentId: resolvedAgentId,
      memoryId,
      personName,
      photos,
      autoInit: false,
    })

  // Send photo context whenever activeMemory changes (and only once per photo)
  useEffect(() => {
    if (
      activeMemory &&
      isReady &&
      activeMemory.id !== sentMemoryIdRef.current
    ) {
      sentMemoryIdRef.current = activeMemory.id
      void sendPhotoContext(activeMemory)
    }
  }, [activeMemory, isReady])

  // Cleanup widget on unmount
  useEffect(() => {
    return () => {
      destroyAgent()
    }
  }, [destroyAgent])

  // No agent ID configured — show placeholder
  if (!resolvedAgentId) {
    return (
      <div
        id={containerId}
        className={['w-full', className].filter(Boolean).join(' ')}
      >
        <ConfigurationPlaceholder />
      </div>
    )
  }

  const handleOrbClick = (): void => {
    if (hasError || agentState.status === 'disconnected') {
      void initAgent()
    }
    // When connected, speaking, or listening — the ElevenLabs widget
    // handles microphone toggling natively via its own UI overlay.
  }

  return (
    <div
      id={containerId}
      className={[
        'flex flex-col items-center gap-5 w-full select-none',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {/* Header */}
      <div className="text-center">
        <h3 className="text-sm font-semibold text-white/80 tracking-wide mb-1">
          Memory Companion
        </h3>
        <p className="text-xs text-white/40">
          {personName}&apos;s voice
        </p>
      </div>

      {/* Orb */}
      <VoiceOrb
        status={agentState.status}
        isSpeaking={agentState.isSpeaking}
        isListening={agentState.isListening}
        onClick={handleOrbClick}
      />

      {/* Status badge */}
      <StatusBadge status={agentState.status} />

      {/* Active photo context banner */}
      {activeMemory && isReady && (
        <PhotoContextBanner memory={activeMemory} />
      )}

      {/* Error message */}
      {hasError && agentState.error && (
        <p
          role="alert"
          className="text-xs text-red-400/80 text-center max-w-[240px] leading-relaxed"
        >
          {agentState.error}
        </p>
      )}

      {/* Idle prompt */}
      {!isActive && !hasError && isReady && (
        <p className="text-xs text-white/30 text-center max-w-[220px] leading-relaxed">
          Ask a question or tap to start remembering
        </p>
      )}

      {/* ElevenLabs widget renders as a fixed overlay — this div is the
          logical anchor. The <elevenlabs-convai> element is appended to
          document.body by initElevenLabsWidget. */}
      <div
        data-elevenlabs-anchor="true"
        aria-hidden="true"
        className="hidden"
      />
    </div>
  )
}

export default VoiceWidget
