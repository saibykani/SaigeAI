import { AppShell } from "@/components/app-shell";
import { UndoSendProvider } from "@/components/undo-send";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UndoSendProvider>
      <AppShell>{children}</AppShell>
    </UndoSendProvider>
  );
}
