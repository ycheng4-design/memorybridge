import React, { useState, useCallback, useRef } from 'react'
import { useDropzone, FileRejection } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import type { PhotoFile } from '@/types'

// ============================================================
// Constants
// ============================================================

const MAX_PHOTOS = 30
const MAX_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB
const ACCEPTED_TYPES = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
}

// ============================================================
// Sub-components
// ============================================================

interface PhotoPreviewProps {
  photo: PhotoFile
  index: number
  onRemove: (id: string) => void
  onCaptionChange: (id: string, caption: string) => void
}

const PhotoPreview: React.FC<PhotoPreviewProps> = ({
  photo,
  index,
  onRemove,
  onCaptionChange,
}) => {
  const [captionFocused, setCaptionFocused] = useState(false)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.85, y: 16 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.8, y: -8 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="relative group rounded-xl overflow-hidden bg-white/[0.06] border border-white/10"
    >
      {/* Photo */}
      <div className="aspect-square relative overflow-hidden">
        <img
          src={photo.previewUrl}
          alt={`Memory ${index + 1}`}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="lazy"
        />

        {/* Overlay with remove button */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors duration-200 flex items-start justify-end p-2">
          <button
            type="button"
            onClick={() => onRemove(photo.id)}
            aria-label={`Remove photo ${index + 1}`}
            className="opacity-0 group-hover:opacity-100 transition-opacity duration-200
                       w-7 h-7 rounded-full bg-red-500/90 hover:bg-red-500
                       flex items-center justify-center text-white text-sm font-bold
                       focus-visible:opacity-100"
          >
            x
          </button>
        </div>

        {/* Photo number badge */}
        <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-sm rounded-full
                        px-2 py-0.5 text-xs text-white/80 font-medium">
          {index + 1}
        </div>
      </div>

      {/* Caption input */}
      <div className="p-2">
        <input
          type="text"
          value={photo.caption}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            onCaptionChange(photo.id, e.target.value)
          }
          onFocus={() => setCaptionFocused(true)}
          onBlur={() => setCaptionFocused(false)}
          placeholder="Add a caption..."
          maxLength={500}
          className={`w-full bg-transparent text-xs text-memory-text placeholder-memory-text-muted/60
                     border-b transition-colors duration-200 pb-1 outline-none
                     ${captionFocused ? 'border-memory-accent' : 'border-white/10'}`}
        />
      </div>
    </motion.div>
  )
}

// ============================================================
// Drop Zone UI
// ============================================================

interface DropZoneContentProps {
  isDragActive: boolean
  isDragReject: boolean
  photoCount: number
}

const DropZoneContent: React.FC<DropZoneContentProps> = ({
  isDragActive,
  isDragReject,
  photoCount,
}) => {
  if (isDragReject) {
    return (
      <div className="flex flex-col items-center gap-3">
        <div className="text-4xl">x</div>
        <p className="text-red-400 font-medium">Only JPEG, PNG and WebP files are allowed</p>
      </div>
    )
  }

  if (isDragActive) {
    return (
      <div className="flex flex-col items-center gap-3">
        <motion.div
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 0.6, repeat: Infinity }}
          className="text-5xl"
        >
          +
        </motion.div>
        <p className="text-memory-accent font-semibold text-lg">Drop your memories here</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Icon */}
      <div className="w-16 h-16 rounded-2xl bg-memory-accent/10 border border-memory-accent/30
                      flex items-center justify-center animate-float">
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
          className="text-memory-accent"
        >
          <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
          <circle cx="9" cy="9" r="2" />
          <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
        </svg>
      </div>

      <div className="text-center">
        <p className="text-memory-text font-medium text-lg mb-1">
          Drag and drop photos here
        </p>
        <p className="text-memory-text-muted text-sm mb-3">
          or click to browse your files
        </p>
        <div className="flex items-center gap-4 justify-center text-xs text-memory-text-muted">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-memory-accent/60 inline-block" />
            JPEG, PNG &amp; WebP
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-memory-accent/60 inline-block" />
            Max 10 MB each
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-memory-accent/60 inline-block" />
            Up to {MAX_PHOTOS} photos
          </span>
        </div>
      </div>

      {photoCount > 0 && (
        <p className="text-memory-text-muted text-sm">
          {photoCount} / {MAX_PHOTOS} photos added — click to add more
        </p>
      )}
    </div>
  )
}

// ============================================================
// Main PhotoUpload Component
// ============================================================

interface PhotoUploadProps {
  photos: PhotoFile[]
  onPhotosChange: (photos: PhotoFile[]) => void
  disabled?: boolean
}

export const PhotoUpload: React.FC<PhotoUploadProps> = ({
  photos,
  onPhotosChange,
  disabled = false,
}) => {
  const [errors, setErrors] = useState<string[]>([])
  const idCounterRef = useRef(0)

  const createPhotoId = useCallback((): string => {
    idCounterRef.current += 1
    return `photo-${Date.now()}-${idCounterRef.current}`
  }, [])

  const addPhotos = useCallback(
    (acceptedFiles: File[]): void => {
      const remaining = MAX_PHOTOS - photos.length

      if (remaining <= 0) {
        setErrors([`Maximum ${MAX_PHOTOS} photos allowed`])
        return
      }

      const filesToAdd = acceptedFiles.slice(0, remaining)
      const skipped = acceptedFiles.length - filesToAdd.length

      const newErrors: string[] = []
      if (skipped > 0) {
        newErrors.push(`${skipped} photo(s) skipped — limit of ${MAX_PHOTOS} reached`)
      }

      const newPhotoFiles: PhotoFile[] = filesToAdd.map((file) => ({
        file,
        previewUrl: URL.createObjectURL(file),
        caption: '',
        id: createPhotoId(),
      }))

      onPhotosChange([...photos, ...newPhotoFiles])
      setErrors(newErrors)
    },
    [photos, onPhotosChange, createPhotoId]
  )

  const handleRejections = useCallback((rejections: FileRejection[]): void => {
    const newErrors = rejections.map((rejection) => {
      const file = rejection.file
      const err = rejection.errors[0]

      if (err?.code === 'file-too-large') {
        return `"${file.name}" is too large (max 10 MB)`
      }
      if (err?.code === 'file-invalid-type') {
        return `"${file.name}" is not a JPEG, PNG or WebP`
      }
      return `"${file.name}": ${err?.message ?? 'invalid file'}`
    })

    setErrors(newErrors.slice(0, 3)) // show max 3 errors
  }, [])

  const removePhoto = useCallback(
    (id: string): void => {
      const photo = photos.find((p) => p.id === id)
      if (photo) {
        URL.revokeObjectURL(photo.previewUrl)
      }
      onPhotosChange(photos.filter((p) => p.id !== id))
      setErrors([])
    },
    [photos, onPhotosChange]
  )

  const updateCaption = useCallback(
    (id: string, caption: string): void => {
      onPhotosChange(
        photos.map((p) => (p.id === id ? { ...p, caption } : p))
      )
    },
    [photos, onPhotosChange]
  )

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDropAccepted: addPhotos,
    onDropRejected: handleRejections,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_BYTES,
    disabled: disabled || photos.length >= MAX_PHOTOS,
    multiple: true,
  })

  const canAddMore = photos.length < MAX_PHOTOS && !disabled

  return (
    <div className="space-y-5">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`
          relative rounded-2xl border-2 border-dashed p-8 cursor-pointer
          transition-all duration-200 min-h-[200px] flex items-center justify-center
          ${isDragReject
            ? 'border-red-400/60 bg-red-500/10'
            : isDragActive
            ? 'border-memory-accent bg-memory-accent/10 scale-[1.01]'
            : canAddMore
            ? 'border-white/20 bg-white/[0.04] hover:border-memory-accent/50 hover:bg-white/[0.07]'
            : 'border-white/10 bg-white/[0.02] cursor-not-allowed opacity-60'
          }
        `}
        aria-label="Photo upload drop zone"
      >
        <input {...getInputProps()} aria-label="File input" />
        <DropZoneContent
          isDragActive={isDragActive}
          isDragReject={isDragReject}
          photoCount={photos.length}
        />
      </div>

      {/* Error messages */}
      <AnimatePresence>
        {errors.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="space-y-1"
          >
            {errors.map((error, i) => (
              <p key={i} className="text-sm text-red-400 flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center text-xs flex-shrink-0">
                  !
                </span>
                {error}
              </p>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Photo count indicator */}
      {photos.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-memory-text-muted text-sm">
            <span className="text-memory-accent font-semibold">{photos.length}</span>
            {' '}/{' '}{MAX_PHOTOS} photos
          </p>
          {photos.length > 0 && (
            <button
              type="button"
              onClick={() => {
                photos.forEach((p) => URL.revokeObjectURL(p.previewUrl))
                onPhotosChange([])
                setErrors([])
              }}
              className="text-xs text-memory-text-muted hover:text-red-400 transition-colors duration-200"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {/* Photo grid */}
      <AnimatePresence>
        {photos.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
          >
            <AnimatePresence mode="popLayout">
              {photos.map((photo, index) => (
                <PhotoPreview
                  key={photo.id}
                  photo={photo}
                  index={index}
                  onRemove={removePhoto}
                  onCaptionChange={updateCaption}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default PhotoUpload
