import { AppStateProvider } from "@/state/AppState";
import UploadPanel from "@/components/UploadPanel";
import AnnotationToolbox from "@/components/AnnotationToolbox";
import AnnotationList from "@/components/AnnotationList";
import ExportButton from "@/components/ExportButton";
import ParseButton from "@/components/ParseButton";
import SliceViewer from "@/components/SliceViewer";
import SliceControls from "@/components/SliceControls";
import { BRAND_NAME, BRAND_TAGLINE } from "@/config/brand";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 via-white to-zinc-100 dark:from-black dark:via-zinc-950 dark:to-black">
      <main className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-black transition-transform duration-300 hover:scale-[1.01] dark:text-zinc-50">
              {BRAND_NAME}
            </h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{BRAND_TAGLINE}</p>
          </div>
        </header>

        <AppStateProvider>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="md:col-span-1 space-y-4">
              <UploadPanel />
              <ParseButton />
              <SliceControls />
              <AnnotationToolbox />
              <div className="rounded-lg border border-zinc-200 p-4 shadow-sm transition-all duration-300 hover:shadow-md dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Export</h2>
                  <ExportButton />
                </div>
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Export annotations and metadata to JSON.</p>
              </div>
            </div>

            <div className="md:col-span-2 space-y-4">
              <SliceViewer />
              <AnnotationList />
            </div>
          </div>
        </AppStateProvider>
      </main>
    </div>
  );
}
