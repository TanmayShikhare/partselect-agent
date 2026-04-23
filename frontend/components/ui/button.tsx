import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "outline" | "ghost";
type Size = "default" | "sm" | "icon";

const variantStyles: Record<Variant, string> = {
  default:
    "bg-[#0066CC] text-white hover:bg-[#005bb8] disabled:bg-zinc-300 disabled:text-zinc-600",
  secondary:
    "bg-zinc-100 text-zinc-900 hover:bg-zinc-200 disabled:bg-zinc-100 disabled:text-zinc-400",
  outline:
    "border border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-50 disabled:text-zinc-400",
  ghost: "text-zinc-900 hover:bg-zinc-100 disabled:text-zinc-400",
};

const sizeStyles: Record<Size, string> = {
  default: "h-10 px-4",
  sm: "h-8 px-3 text-sm",
  icon: "h-10 w-10",
};

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  asChild?: boolean;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "default", size = "default", asChild, ...props },
    ref
  ) => {
    const classes = cn(
      "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0066CC]/40 disabled:cursor-not-allowed",
      variantStyles[variant],
      sizeStyles[size],
      className
    );

    if (asChild) {
      const child = React.Children.only(props.children) as React.ReactElement<{
        className?: string;
      }>;
      return React.cloneElement(child, {
        className: cn(classes, child.props.className),
      });
    }

    return <button ref={ref} className={classes} {...props} />;
  }
);
Button.displayName = "Button";

