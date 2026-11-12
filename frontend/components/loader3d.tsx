import { DotRing } from "@/components/dot-ring";
import { cn } from "@/utils/cn";

/**
 * Full-page / route loader. It used to be three CSS-3D gimbal rings (preserve-3d layers that kept the GPU busy);
 * it now renders the lightweight DotRing sweep, keeping the same API for every caller.
 */
export function Loader3D({ size = 72, label, className }: { size?: number; label?: string; className?: string }) {
  return (
    <div className={cn("loader3d flex flex-col items-center gap-4", className)}>
      <DotRing size={size} dots={size >= 56 ? 36 : 24} />
      {label && <p className="text-sm text-muted-foreground">{label}</p>}
    </div>
  );
}
