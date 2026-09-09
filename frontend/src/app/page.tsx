export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 bg-canvas text-gray-200">
      <div className="w-full max-w-2xl bg-surface border border-borderSubtle rounded-xl p-8 shadow-2xl space-y-6">
        <div className="flex items-center justify-between border-b border-borderSubtle pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-3.5 h-3.5 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-xl font-semibold tracking-tight text-white">SocialOS Command Center</h1>
          </div>
          <span className="px-2.5 py-1 text-xs font-mono uppercase bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 rounded">
            Foundation Ready
          </span>
        </div>

        <p className="text-sm text-gray-400 leading-relaxed">
          Step 4 Scaffolding initialized. Core decoupled architecture standard: Next.js 15 App Router +
          FastAPI + PostgreSQL + Celery/Redis + AWS S3/CloudFront.
        </p>

        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          <div className="p-3 rounded-lg bg-surfaceCard border border-borderSubtle space-y-1">
            <span className="text-gray-500">Frontend Layer</span>
            <p className="text-white font-medium">Next.js 15 + React 19</p>
          </div>
          <div className="p-3 rounded-lg bg-surfaceCard border border-borderSubtle space-y-1">
            <span className="text-gray-500">Backend API</span>
            <p className="text-white font-medium">Python FastAPI + Pydantic v2</p>
          </div>
          <div className="p-3 rounded-lg bg-surfaceCard border border-borderSubtle space-y-1">
            <span className="text-gray-500">Persistence</span>
            <p className="text-white font-medium">PostgreSQL / Supabase</p>
          </div>
          <div className="p-3 rounded-lg bg-surfaceCard border border-borderSubtle space-y-1">
            <span className="text-gray-500">Queue & Async</span>
            <p className="text-white font-medium">Redis 7.2 + Celery</p>
          </div>
        </div>

        <div className="pt-2 text-xs text-gray-500 flex items-center justify-between border-t border-borderSubtle">
          <span>Production Media: AWS S3 + Amazon CloudFront</span>
          <span>Local Storage: MinIO</span>
        </div>
      </div>
    </main>
  );
}
