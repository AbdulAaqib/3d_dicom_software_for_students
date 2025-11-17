"use client";

import React, { useCallback } from "react";
import { useAppState } from "@/state/AppState";
import UploadPanel from "@/components/UploadPanel";
import ParseButton from "@/components/ParseButton";
import ImportSRPanel from "@/components/ImportSRPanel";
import SliceControls from "@/components/SliceControls";
import AnnotationToolbox from "@/components/AnnotationToolbox";
import ViewerSettingsPanel from "@/components/ViewerSettingsPanel";
import ExportButton from "@/components/ExportButton";
import ExportDICOMSRButton from "@/components/ExportDICOMSRButton";
import Viewer3D from "@/components/Viewer3D";
import SliceViewer from "@/components/SliceViewer";
import AnnotationList from "@/components/AnnotationList";
import { BRAND_NAME, BRAND_TAGLINE } from "@/config/brand";
import MeshGeneratorPanel from "@/components/MeshGeneratorPanel";

export default function WorkspaceLayout() {
  const { viewerSettings, updateViewerSettings } = useAppState();
  const toggleSidebar = useCallback(() => {
    updateViewerSettings({ showSidebar: !viewerSettings.showSidebar });
  }, [updateViewerSettings, viewerSettings.showSidebar]);

  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-black transition-transform duration-300 hover:scale-[1.01] dark:text-zinc-50">
            {BRAND_NAME}
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{BRAND_TAGLINE}</p>
        </div>
        <button
          onClick={toggleSidebar}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          {viewerSettings.showSidebar ? "Hide Sidebar" : "Show Sidebar"}
        </button>
      </header>

      <div className="grid gap-6 md:grid-cols-3">
        {viewerSettings.showSidebar && (
          <div className="space-y-4">
            <UploadPanel />
            <ParseButton />
            <ImportSRPanel />
            <SliceControls />
            <AnnotationToolbox />
            <ViewerSettingsPanel />
            <MeshGeneratorPanel />
            <div className="rounded-lg border border-zinc-200 p-4 shadow-sm transition-all duration-300 hover:shadow-md dark:border-zinc-800">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Export</h2>
                <ExportButton />
              </div>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Export annotations and metadata.</p>
              <div className="mt-3">
                <ExportDICOMSRButton />
              </div>
            </div>
          </div>
        )}

        <div className={`${viewerSettings.showSidebar ? "md:col-span-2" : "md:col-span-3"} space-y-4`}>
          <div className="grid gap-4 grid-cols-1 xl:grid-cols-2">
            <Viewer3D />
            <SliceViewer />
          </div>
          <AnnotationList />
        </div>
      </div>
    </main>
  );
}
