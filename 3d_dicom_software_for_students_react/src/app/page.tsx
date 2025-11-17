import { AppStateProvider } from "@/state/AppState";
import WorkspaceLayout from "@/components/WorkspaceLayout";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 via-white to-zinc-100 dark:from-black dark:via-zinc-950 dark:to-black">
      <AppStateProvider>
        <WorkspaceLayout />
      </AppStateProvider>
    </div>
  );
}
