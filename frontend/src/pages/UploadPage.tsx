import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { PhotoUpload } from '@/components/upload/PhotoUpload'
import { VoiceRecorder } from '@/components/upload/VoiceRecorder'
import { ProcessingScreen } from '@/components/upload/ProcessingScreen'
import { uploadMemory, pollMemoryReady } from '@/services/api'
import type { PhotoFile, UploadState, ProcessingStage } from '@/types'

// ============================================================
// Step indicators
// ============================================================

type Step = 1 | 2 | 3

interface StepConfig {
  number: Step
  label: string
  description: string
}

const STEPS: StepConfig[] = [
  { number: 1, label: 'Upload Photos', description: 'Add up to 30 cherished photos' },
  { number: 2, label: 'Record Voice', description: '60–120 seconds of their voice' },
  { number: 3, label: 'Processing', description: 'AI builds the memory bridge' },
]

interface StepIndicatorProps {
  currentStep: Step
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => (
  <div className="flex items-center justify-center gap-2 mb-10" aria-label="Upload steps">
    {STEPS.map((step, i) => {
      const isComplete = step.number < currentStep
      const isActive = step.number === currentStep
      const isPending = step.number > currentStep

      return (
        <React.Fragment key={step.number}>
          <div className="flex flex-col items-center gap-1.5">
            {/* Circle */}
            <div
              className={`
                w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold
                transition-all duration-300 border-2
                ${isComplete
                  ? 'bg-emerald-500 border-emerald-500 text-white'
                  : isActive
                  ? 'bg-memory-accent border-memory-accent text-memory-bg'
                  : 'bg-transparent border-white/20 text-memory-text-muted'
                }
              `}
              aria-current={isActive ? 'step' : undefined}
            >
              {isComplete ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6 9 17l-5-5"/>
                </svg>
              ) : (
                step.number
              )}
            </div>
            {/* Label */}
            <span
              className={`text-xs font-medium transition-colors duration-300 hidden sm:block
                ${isActive ? 'text-memory-text' : isPending ? 'text-memory-text-muted/60' : 'text-memory-text-muted'}`}
            >
              {step.label}
            </span>
          </div>

          {/* Connector */}
          {i < STEPS.length - 1 && (
            <div
              className={`h-0.5 w-12 sm:w-20 rounded-full transition-colors duration-300 mb-4
                ${step.number < currentStep ? 'bg-emerald-500' : 'bg-white/10'}`}
              aria-hidden="true"
            />
          )}
        </React.Fragment>
      )
    })}
  </div>
)

// ============================================================
// Page Header
// ============================================================

const PageHeader: React.FC = () => (
  <header className="text-center mb-10 space-y-3">
    {/* Logo */}
    <div className="flex items-center justify-center gap-3 mb-4">
      <div className="w-10 h-10 rounded-xl bg-memory-accent/15 border border-memory-accent/30
                      flex items-center justify-center animate-float">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#f4c430"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
        </svg>
      </div>
      <h1 className="text-3xl font-bold font-heading text-gradient-gold">MemoryBridge</h1>
    </div>
    <p className="text-memory-text-muted text-base max-w-md mx-auto leading-relaxed">
      Help your loved one with dementia relive their most precious memories through
      AI-powered voice conversations.
    </p>
  </header>
)

// ============================================================
// Main UploadPage
// ============================================================

const STAGE_SEQUENCE: ProcessingStage[] = ['uploading', 'cloning', 'embedding', 'ready']

export const UploadPage: React.FC = () => {
  const navigate = useNavigate()

  const [currentStep, setCurrentStep] = useState<Step>(1)
  const [photos, setPhotos] = useState<PhotoFile[]>([])
  const [voiceFile, setVoiceFile] = useState<File | null>(null)
  const [voiceDuration, setVoiceDuration] = useState<number>(0)
  const [personName, setPersonName] = useState('')
  const [uploadState, setUploadState] = useState<UploadState>({
    status: 'idle',
    progress: 0,
    stage: 'uploading',
  })

  const handleVoiceComplete = useCallback(
    (file: File, duration: number): void => {
      setVoiceFile(file)
      setVoiceDuration(duration)
    },
    []
  )

  const handleUpload = useCallback(async (): Promise<void> => {
    if (photos.length === 0 || !voiceFile) return

    setCurrentStep(3)
    setUploadState({ status: 'uploading', progress: 0, stage: 'uploading' })

    try {
      // Stage 1: Upload files
      const uploadResponse = await uploadMemory(
        {
          photos: photos.map((p) => p.file),
          voiceRecording: voiceFile,
          captions: photos.map((p) => p.caption),
          personName: personName.trim() || 'My loved one',
        },
        (progress: number) => {
          setUploadState((prev) => ({ ...prev, progress }))
        }
      )

      const memoryId = uploadResponse.memory_id

      // Stage 2: Cloning
      setUploadState({ status: 'processing', progress: 0, stage: 'cloning' })

      // Stage 3: Poll for completion with stage updates
      await pollMemoryReady(memoryId, {
        intervalMs: 2500,
        timeoutMs: 180_000,
        onPoll: (response) => {
          // Update stage based on server status
          if (response.embedding_ready) {
            setUploadState((prev) => ({ ...prev, stage: 'embedding', progress: 80 }))
          } else if (response.status === 'processing') {
            setUploadState((prev) => {
              const currentIdx = STAGE_SEQUENCE.indexOf(prev.stage)
              const nextStage =
                currentIdx < 2 ? STAGE_SEQUENCE[currentIdx + 1] : prev.stage
              return { ...prev, stage: nextStage as ProcessingStage }
            })
          }
        },
      })

      // Done
      setUploadState({
        status: 'ready',
        progress: 100,
        stage: 'ready',
        memoryId,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      setUploadState((prev) => ({
        ...prev,
        status: 'error',
        error: message,
      }))
    }
  }, [photos, voiceFile, personName])

  const canProceedToStep2 = photos.length > 0
  const canUpload = photos.length > 0 && voiceFile !== null
  const isUploading = uploadState.status === 'uploading' || uploadState.status === 'processing'

  const handleRetry = useCallback((): void => {
    setCurrentStep(2)
    setUploadState({ status: 'idle', progress: 0, stage: 'uploading' })
  }, [])

  // Processing screen handles its own full-screen rendering
  if (currentStep === 3) {
    return (
      <ProcessingScreen
        stage={uploadState.stage}
        uploadProgress={uploadState.progress}
        personName={personName.trim() || 'your loved one'}
        error={uploadState.status === 'error' ? uploadState.error : null}
        onRetry={uploadState.status === 'error' ? handleRetry : undefined}
        onViewMemory={
          uploadState.status === 'ready' && uploadState.memoryId
            ? () => navigate(`/memory/${uploadState.memoryId}`)
            : undefined
        }
      />
    )
  }

  return (
    <div className="min-h-screen bg-memory-bg relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px]
                      bg-radial-purple pointer-events-none" aria-hidden="true" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px]
                      bg-gold-glow pointer-events-none" aria-hidden="true" />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-10 sm:px-6 lg:px-8">
        <PageHeader />
        <StepIndicator currentStep={currentStep} />

        {/* Person name input — always visible above steps */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-5 mb-8 flex flex-col sm:flex-row sm:items-center gap-3"
        >
          <label htmlFor="person-name" className="text-sm font-medium text-memory-text whitespace-nowrap">
            Their name
          </label>
          <input
            id="person-name"
            type="text"
            value={personName}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPersonName(e.target.value)}
            placeholder="e.g. Dorothy, Grandpa Joe..."
            maxLength={60}
            className="flex-1 bg-transparent border-b border-white/20 focus:border-memory-accent
                       text-memory-text placeholder-memory-text-muted/50 pb-1 outline-none
                       transition-colors duration-200 text-sm"
          />
        </motion.div>

        {/* Step content */}
        <AnimatePresence mode="wait">
          {currentStep === 1 && (
            <motion.div
              key="step-1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
              className="space-y-6"
            >
              <div className="glass-card p-6 sm:p-8">
                <div className="mb-6">
                  <h2 className="text-xl font-bold text-memory-text mb-1">
                    Upload Memory Photos
                  </h2>
                  <p className="text-sm text-memory-text-muted">
                    Add photos from different life stages. The AI will organize them by era
                    and make each one accessible through voice conversation.
                  </p>
                </div>
                <PhotoUpload photos={photos} onPhotosChange={setPhotos} />
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => setCurrentStep(2)}
                  disabled={!canProceedToStep2}
                  className="btn-gold flex items-center gap-2 disabled:opacity-50"
                >
                  Continue to Voice Recording
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m9 18 6-6-6-6"/>
                  </svg>
                </button>
              </div>
            </motion.div>
          )}

          {currentStep === 2 && (
            <motion.div
              key="step-2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
              className="space-y-6"
            >
              <VoiceRecorder
                onRecordingComplete={handleVoiceComplete}
                disabled={false}
              />

              {/* Voice status summary */}
              {voiceFile && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-card p-4 flex items-center gap-3"
                >
                  <div className="status-dot-active" />
                  <span className="text-sm text-emerald-400 font-medium">
                    Voice recording ready ({Math.floor(voiceDuration)}s)
                  </span>
                </motion.div>
              )}

              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setCurrentStep(1)}
                  className="btn-ghost flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m15 18-6-6 6-6"/>
                  </svg>
                  Back
                </button>

                <button
                  type="button"
                  onClick={() => void handleUpload()}
                  disabled={!canUpload || isUploading}
                  className="btn-gold flex items-center gap-2 disabled:opacity-50 min-w-[180px] justify-center"
                  aria-busy={isUploading}
                >
                  {isUploading ? (
                    <>
                      <div className="w-4 h-4 rounded-full border-2 border-memory-bg/40 border-t-memory-bg animate-spin flex-shrink-0" />
                      Preparing...
                    </>
                  ) : (
                    <>
                      Build Memory Bridge
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
                      </svg>
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer */}
        <div className="mt-12 text-center">
          <p className="text-xs text-memory-text-muted/60">
            MemoryBridge — Built with care for Hack for Humanity 2026
          </p>
        </div>
      </div>
    </div>
  )
}

export default UploadPage
