"use client";

import { formatCurrency, formatPct, pctColor } from "@/lib/utils";

interface PriceBadgeProps {
  price: number;
  changePct: number | null;
  size?: "sm" | "md" | "lg";
}

export function PriceBadge({ price, changePct, size = "md" }: PriceBadgeProps) {
  const sizeClasses = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-2xl font-semibold",
  };

  return (
    <div className="flex items-baseline gap-2">
      <span className={sizeClasses[size]}>{formatCurrency(price)}</span>
      <span className={`text-sm ${pctColor(changePct)}`}>
        {formatPct(changePct)}
      </span>
    </div>
  );
}
