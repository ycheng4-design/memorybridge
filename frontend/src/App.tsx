import React, { lazy, Suspense, useEffect, useRef } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import UploadPage from '@/pages/UploadPage'
import TimelinePage from '@/pages/TimelinePage'

// ============================================================
// App — Root router
// ============================================================
// The WebSpatial quick-example pattern uses __XR_ENV_BASE__ as
// the basename so that spatial scene routing resolves correctly
// on visionOS. In browser mode __XR_ENV_BASE__ is '' (empty).
// ============================================================

// React.lazy for SpatialMemoryRoom — it is heavy (WebSpatial SDK)
// and only loaded when the /room/:id route is actually visited.
const SpatialMemoryRoom = lazy(
  () => import('@/components/spatial/SpatialMemoryRoom')
)

declare const __XR_ENV_BASE__: string

// Full-screen skeleton fallback for lazy-loaded spatial room
function SpatialLoadingFallback() {
  return (
    <div className="min-h-screen bg-memory-bg flex items-center justify-center">
      <div className="w-full max-w-2xl px-8 space-y-6">
        {/* Central orb skeleton */}
        <div className="flex justify-center mb-8">
          <div className="w-24 h-24 rounded-full skeleton" />
        </div>
        {/* Photo panel skeletons arranged in an arc */}
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
          {Array.from({ length: 8 }, (_, i) => (
            <div
              key={i}
              className="rounded-2xl skeleton"
              style={{
                height: 120,
                animationDelay: `${i * 100}ms`,
                opacity: 1 - i * 0.08,
              }}
            />
          ))}
        </div>
        <p className="text-center text-memory-text-muted text-sm">
          Loading memory room...
        </p>
      </div>
    </div>
  )
}

// Wrap route content with a page-level fade-in on each navigation
function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Remove and re-add the class to re-trigger the animation on route change
    el.classList.remove('animate-page-enter')
    void el.offsetWidth // force reflow
    el.classList.add('animate-page-enter')
  }, [location.pathname])

  return (
    <div ref={ref} className="animate-page-enter" style={{ willChange: 'opacity, transform' }}>
      {children}
    </div>
  )
}

function App() {
  // __XR_ENV_BASE__ is injected by the WebSpatial vite plugin.
  // Guard for environments where the plugin is not installed.
  const base =
    typeof __XR_ENV_BASE__ !== 'undefined' ? __XR_ENV_BASE__ : ''

  return (
    <div className="min-h-screen bg-memory-bg text-memory-text font-body">
      <Routes>
        {/* Home: upload flow */}
        <Route
          path={`${base}/`}
          element={
            <PageTransition>
              <UploadPage />
            </PageTransition>
          }
        />

        {/* Timeline: photo grid for a memory session */}
        <Route
          path={`${base}/memory/:id`}
          element={
            <PageTransition>
              <TimelinePage />
            </PageTransition>
          }
        />

        {/* Spatial room: full immersive memory experience */}
        <Route
          path={`${base}/room/:memoryId`}
          element={
            <PageTransition>
              <Suspense fallback={<SpatialLoadingFallback />}>
                <SpatialMemoryRoom />
              </Suspense>
            </PageTransition>
          }
        />

        {/* Legacy /memory/:memoryId route — still used by SpatialMemoryRoom internally */}
        <Route
          path={`${base}/memory/:memoryId`}
          element={
            <PageTransition>
              <Suspense fallback={<SpatialLoadingFallback />}>
                <SpatialMemoryRoom />
              </Suspense>
            </PageTransition>
          }
        />

        {/* Catch-all */}
        <Route
          path="*"
          element={
            <PageTransition>
              <div className="min-h-screen flex items-center justify-center bg-memory-bg">
                <div className="glass-card p-10 text-center space-y-4 max-w-sm">
                  <p className="text-4xl font-bold text-gradient-gold">404</p>
                  <p className="text-memory-text-muted">Page not found.</p>
                  <a href="/" className="btn-gold inline-block">
                    Go home
                  </a>
                </div>
              </div>
            </PageTransition>
          }
        />
      </Routes>
    </div>
  )
}

export default App
