import React, { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { RecordingStatus } from '@/types'

// ============================================================
// Constants
// ============================================================

const MIN_DURATION_S = 60
const MAX_DURATION_S = 120
const WAVEFORM_BARS = 32
const TICK_INTERVAL_MS = 100

// ============================================================
// Helpers
// ============================================================

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = Math.floor(totalSeconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function getMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  return types.find((t) => MediaRecorder.isTypeSupported(t)) ?? ''
}

// ============================================================
// Waveform Visualizer
// ============================================================

interface WaveformProps {
  analyser: AnalyserNode | null
  isActive: boolean
}

const Waveform: React.FC<WaveformProps> = ({ analyser, isActive }) => {
  const [bars, setBars] = useState<number[]>(
    Array.from({ length: WAVEFORM_BARS }, () => 0.1)
  )
  const rafRef = useRef<number | null>(null)
  const dataArrayRef = useRef<Uint8Array<ArrayBuffer> | null>(null)

  useEffect(() => {
    if (!analyser || !isActive) {
      // Animate a gentle idle state
      setBars(Array.from({ length: WAVEFORM_BARS }, (_, i) => {
        return 0.05 + Math.sin(i * 0.5) * 0.04
      }))
      return
    }

    analyser.fftSize = 64
    const bufferLength = analyser.frequencyBinCount
    dataArrayRef.current = new Uint8Array(bufferLength)

    const draw = (): void => {
      if (!analyser || !dataArrayRef.current) return

      analyser.getByteFrequencyData(dataArrayRef.current)

      // Map frequency data to WAVEFORM_BARS bars
      const newBars = Array.from({ length: WAVEFORM_BARS }, (_, i) => {
        const bucketIndex = Math.floor(
          (i / WAVEFORM_BARS) * bufferLength
        )
        const value = dataArrayRef.current![bucketIndex] ?? 0
        return Math.max(0.05, value / 255)
      })

      setBars(newBars)
      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [analyser, isActive])

  return (
    <div
      className="flex items-center justify-center gap-[3px] h-16"
      aria-hidden="true"
    >
      {bars.map((height, i) => (
        <motion.div
          key={i}
          className="waveform-bar"
          style={{
            backgroundColor:
              isActive ? '#f4c430' : 'rgba(244, 196, 48, 0.3)',
          }}
          animate={{
            scaleY: isActive ? height * 10 : 0.15 + Math.sin(i * 0.3 + Date.now() / 1000) * 0.1,
            opacity: isActive ? 0.7 + height * 0.3 : 0.4,
          }}
          transition={{
            duration: 0.05,
            ease: 'easeOut',
          }}
        />
      ))}
    </div>
  )
}

// ============================================================
// Timer Ring
// ============================================================

interface TimerRingProps {
  elapsed: number
  status: RecordingStatus
}

const TimerRing: React.FC<TimerRingProps> = ({ elapsed, status }) => {
  const radius = 44
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(elapsed / MAX_DURATION_S, 1)
  const dashOffset = circumference * (1 - progress)

  const color =
    status === 'recording'
      ? elapsed >= MIN_DURATION_S
        ? '#34d399' // green — ready to stop
        : '#f4c430' // gold — still recording
      : '#6d28d9'   // purple — idle/stopped

  const warningColor = elapsed >= MAX_DURATION_S - 10 ? '#f87171' : color

  return (
    <div className="relative w-28 h-28 flex items-center justify-center">
      <svg
        width="112"
        height="112"
        viewBox="0 0 112 112"
        className="absolute inset-0 -rotate-90"
        aria-hidden="true"
      >
        {/* Track */}
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth="4"
        />
        {/* Progress */}
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke={warningColor}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: 'stroke-dashoffset 0.1s linear, stroke 0.3s ease' }}
        />
        {/* Min threshold marker */}
        {status === 'recording' && (
          <circle
            cx={56 + radius * Math.cos(2 * Math.PI * (MIN_DURATION_S / MAX_DURATION_S) - Math.PI / 2)}
            cy={56 + radius * Math.sin(2 * Math.PI * (MIN_DURATION_S / MAX_DURATION_S) - Math.PI / 2)}
            r="4"
            fill="#34d399"
            opacity="0.8"
          />
        )}
      </svg>

      {/* Time display */}
      <div className="relative z-10 text-center">
        <div className="text-2xl font-bold font-heading text-memory-text tabular-nums">
          {formatTime(elapsed)}
        </div>
        <div className="text-xs text-memory-text-muted">
          {status === 'recording'
            ? elapsed < MIN_DURATION_S
              ? `${MIN_DURATION_S - Math.floor(elapsed)}s more`
              : 'ready!'
            : 'elapsed'}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Main VoiceRecorder Component
// ============================================================

interface VoiceRecorderProps {
  onRecordingComplete: (file: File, durationSeconds: number) => void
  disabled?: boolean
}

interface RecorderState {
  status: RecordingStatus
  elapsed: number
  error: string | null
  audioBlob: Blob | null
  previewUrl: string | null
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  onRecordingComplete,
  disabled = false,
}) => {
  const [state, setState] = useState<RecorderState>({
    status: 'idle',
    elapsed: 0,
    error: null,
    audioBlob: null,
    previewUrl: null,
  })

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedRef = useRef(0)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)

  const stopTimer = useCallback((): void => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const cleanupStream = useCallback((): void => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close()
      audioContextRef.current = null
    }
    analyserRef.current = null
  }, [])

  const finalize = useCallback(
    (chunks: Blob[], mimeType: string): void => {
      const blob = new Blob(chunks, { type: mimeType })
      const durationSeconds = elapsedRef.current
      const previewUrl = URL.createObjectURL(blob)

      setState((prev) => ({
        ...prev,
        status: 'stopped',
        audioBlob: blob,
        previewUrl,
      }))

      // Validate duration
      if (durationSeconds < MIN_DURATION_S) {
        setState((prev) => ({
          ...prev,
          error: `Recording too short (${Math.floor(durationSeconds)}s). Minimum is ${MIN_DURATION_S}s.`,
        }))
        return
      }

      const file = new File([blob], `voice-memory-${Date.now()}.webm`, {
        type: mimeType,
        lastModified: Date.now(),
      })
      onRecordingComplete(file, durationSeconds)
    },
    [onRecordingComplete]
  )

  const startRecording = useCallback(async (): Promise<void> => {
    setState((prev) => ({ ...prev, error: null }))

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      })
      streamRef.current = stream

      // Set up Web Audio analyser for waveform
      const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      const audioCtx = new AudioCtx()
      audioContextRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.smoothingTimeConstant = 0.8
      source.connect(analyser)
      analyserRef.current = analyser

      const mimeType = getMimeType()
      const recorder = new MediaRecorder(stream, {
        mimeType: mimeType || undefined,
      })
      mediaRecorderRef.current = recorder
      chunksRef.current = []
      elapsedRef.current = 0

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        finalize(chunksRef.current, mimeType || 'audio/webm')
        cleanupStream()
      }

      recorder.start(100) // collect data every 100ms

      // Timer
      timerRef.current = setInterval(() => {
        elapsedRef.current += TICK_INTERVAL_MS / 1000
        setState((prev) => ({ ...prev, elapsed: elapsedRef.current }))

        // Auto-stop at max duration
        if (elapsedRef.current >= MAX_DURATION_S) {
          stopTimer()
          recorder.stop()
        }
      }, TICK_INTERVAL_MS)

      setState((prev) => ({
        ...prev,
        status: 'recording',
        elapsed: 0,
        audioBlob: null,
        previewUrl: null,
        error: null,
      }))
    } catch (err) {
      const message =
        err instanceof Error
          ? err.name === 'NotAllowedError'
            ? 'Microphone access denied. Please allow microphone in browser settings.'
            : err.message
          : 'Failed to start recording'

      setState((prev) => ({ ...prev, status: 'error', error: message }))
      cleanupStream()
    }
  }, [finalize, cleanupStream, stopTimer])

  const stopRecording = useCallback((): void => {
    stopTimer()
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== 'inactive'
    ) {
      mediaRecorderRef.current.stop()
    }
  }, [stopTimer])

  const resetRecording = useCallback((): void => {
    stopTimer()
    stopRecording()
    cleanupStream()
    elapsedRef.current = 0

    setState({
      status: 'idle',
      elapsed: 0,
      error: null,
      audioBlob: null,
      previewUrl: null,
    })
  }, [stopTimer, stopRecording, cleanupStream])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTimer()
      cleanupStream()
    }
  }, [stopTimer, cleanupStream])

  const isRecording = state.status === 'recording'
  const isStopped = state.status === 'stopped'
  const canStop = isRecording && state.elapsed >= MIN_DURATION_S
  const isReady =
    isStopped && state.elapsed >= MIN_DURATION_S && !state.error

  return (
    <div className="space-y-6">
      <div className="glass-card p-8 flex flex-col items-center gap-6">
        {/* Header */}
        <div className="text-center">
          <h3 className="text-xl font-semibold text-memory-text mb-1">
            Share Their Voice
          </h3>
          <p className="text-sm text-memory-text-muted">
            Record {MIN_DURATION_S}–{MAX_DURATION_S} seconds of your loved one speaking.
            This voice will guide their memories.
          </p>
        </div>

        {/* Waveform */}
        <Waveform analyser={analyserRef.current} isActive={isRecording} />

        {/* Timer */}
        <TimerRing elapsed={state.elapsed} status={state.status} />

        {/* Duration guidance */}
        <div className="flex items-center gap-6 text-sm">
          <div className={`flex items-center gap-2 ${state.elapsed >= MIN_DURATION_S ? 'text-emerald-400' : 'text-memory-text-muted'}`}>
            <div className={`w-2 h-2 rounded-full ${state.elapsed >= MIN_DURATION_S ? 'bg-emerald-400' : 'bg-memory-text-muted'}`} />
            Min: {formatTime(MIN_DURATION_S)}
          </div>
          <div className="text-memory-text-muted/40">|</div>
          <div className={`flex items-center gap-2 ${state.elapsed >= MAX_DURATION_S - 10 && isRecording ? 'text-red-400' : 'text-memory-text-muted'}`}>
            <div className={`w-2 h-2 rounded-full ${state.elapsed >= MAX_DURATION_S - 10 && isRecording ? 'bg-red-400' : 'bg-memory-text-muted'}`} />
            Max: {formatTime(MAX_DURATION_S)}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          <AnimatePresence mode="wait">
            {state.status === 'idle' && (
              <motion.button
                key="start"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
                type="button"
                onClick={() => void startRecording()}
                disabled={disabled}
                className="btn-gold flex items-center gap-2 px-8 py-4 rounded-full text-base font-semibold disabled:opacity-50"
                aria-label="Start recording"
              >
                {/* Mic icon */}
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" x2="12" y1="19" y2="22"/>
                </svg>
                Start Recording
              </motion.button>
            )}

            {isRecording && (
              <motion.div
                key="recording"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-3"
              >
                {/* Recording indicator */}
                <div className="flex items-center gap-2 text-red-400">
                  <div className="w-3 h-3 rounded-full bg-red-400 animate-pulse" />
                  <span className="text-sm font-medium">Recording</span>
                </div>

                <button
                  type="button"
                  onClick={stopRecording}
                  disabled={!canStop}
                  className={`
                    flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm
                    transition-all duration-200
                    ${canStop
                      ? 'bg-emerald-500 text-white hover:bg-emerald-400 active:scale-95'
                      : 'bg-white/10 text-memory-text-muted cursor-not-allowed opacity-50'
                    }
                  `}
                  aria-label="Stop recording"
                >
                  {/* Stop icon */}
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                  </svg>
                  {canStop ? 'Stop' : `${Math.ceil(MIN_DURATION_S - state.elapsed)}s left`}
                </button>

                <button
                  type="button"
                  onClick={resetRecording}
                  className="btn-ghost px-4 py-3 rounded-full text-sm"
                  aria-label="Cancel recording"
                >
                  Cancel
                </button>
              </motion.div>
            )}

            {isStopped && (
              <motion.div
                key="stopped"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-3"
              >
                <button
                  type="button"
                  onClick={resetRecording}
                  className="btn-ghost px-5 py-3 rounded-full text-sm flex items-center gap-2"
                  aria-label="Re-record"
                >
                  {/* Refresh icon */}
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                    <path d="M3 3v5h5"/>
                  </svg>
                  Re-record
                </button>

                {isReady && (
                  <div className="flex items-center gap-2 text-emerald-400 font-medium text-sm">
                    {/* Check icon */}
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="m9 12 2 2 4-4"/>
                    </svg>
                    Recording saved ({formatTime(state.elapsed)})
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Audio playback preview */}
        {state.previewUrl && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full"
          >
            <p className="text-xs text-memory-text-muted mb-2 text-center">
              Preview your recording
            </p>
            <audio
              controls
              src={state.previewUrl}
              className="w-full h-8"
              aria-label="Voice recording preview"
            />
          </motion.div>
        )}
      </div>

      {/* Error message */}
      <AnimatePresence>
        {state.error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="glass-card border border-red-400/20 p-4 flex items-start gap-3"
          >
            <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-red-400 text-xs font-bold">!</span>
            </div>
            <p className="text-sm text-red-400">{state.error}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Guidelines */}
      <div className="glass-card p-5 space-y-3">
        <p className="text-sm font-medium text-memory-text">Recording tips</p>
        <ul className="space-y-2">
          {[
            'Find a quiet room with minimal background noise',
            'Ask them to talk about their favorite memories, family, or childhood',
            `Record ${MIN_DURATION_S}–${MAX_DURATION_S} seconds for the best voice clone quality`,
            'Natural conversation is better than reading from a script',
          ].map((tip, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-memory-text-muted">
              <span className="text-memory-accent mt-0.5 flex-shrink-0">-</span>
              {tip}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default VoiceRecorder
