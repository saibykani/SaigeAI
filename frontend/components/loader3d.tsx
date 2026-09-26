import { cn } from "@/utils/cn";

/** Three gimbal rings orbiting a glowing core, in the theme's accent. Pure CSS 3D. */
export function Loader3D({ size = 72, label, className }: { size?: number; label?: string; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={cn("loader3d flex flex-col items-center gap-4", className)}>
      <div className="loader3d-stage" style={{ width: size, height: size }}>
        <span className="loader3d-ring" />
        <span className="loader3d-ring" />
        <span className="loader3d-ring" />
        <span className="loader3d-core" />
      </div>
      {label && <p className="text-sm text-muted-foreground">{label}</p>}
      <span className="sr-only">Loading</span>
    </div>
  );
}
