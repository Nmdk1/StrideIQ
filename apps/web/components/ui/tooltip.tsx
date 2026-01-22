"use client"

import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"

import { cn } from "@/lib/utils"

const TooltipProvider = TooltipPrimitive.Provider

const Tooltip = TooltipPrimitive.Root

const TooltipTrigger = TooltipPrimitive.Trigger

const STRIDEIQ_TOOLTIP_CONTENT_CLASS =
  // Match the "good" StrideIQ chart tooltips (Efficiency / Age-Graded):
  // bg-slate-800 + soft border + rounded + shadow + readable type.
  "z-50 max-w-xs overflow-hidden rounded-lg border border-slate-700/50 bg-slate-800 px-3 py-2 text-xs leading-relaxed text-slate-200 shadow-lg whitespace-pre-line " +
  "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 " +
  "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 " +
  "origin-[--radix-tooltip-content-transform-origin]"

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      STRIDEIQ_TOOLTIP_CONTENT_CLASS,
      className
    )}
    {...props}
  >
    {props.children}
    <TooltipPrimitive.Arrow className="fill-slate-800" />
  </TooltipPrimitive.Content>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, STRIDEIQ_TOOLTIP_CONTENT_CLASS }
