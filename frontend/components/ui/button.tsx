import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/utils/cn";

const baseVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-sm hover:shadow-[var(--shadow-lift)] hover:brightness-110",
        gradient: "bg-[image:var(--hero-gradient)] text-white shadow-sm hover:shadow-[var(--shadow-lift)] hover:brightness-110",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:brightness-110",
        outline: "border border-input bg-card-solid/60 hover:bg-muted",
        secondary: "bg-secondary text-secondary-foreground hover:brightness-95",
        ghost: "hover:bg-muted",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-8 px-3.5 text-xs",
        lg: "h-12 px-7 text-[15px]",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

/** Tailwind-merged so a caller's className (e.g. a custom bg/text colour) always wins. */
function buttonVariants({ className, ...variants }: VariantProps<typeof baseVariants> & { className?: string } = {}) {
  return cn(baseVariants(variants), className);
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof baseVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, size, className }))} {...props} />
  ),
);
Button.displayName = "Button";

export { buttonVariants };
