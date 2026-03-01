"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { formatCurrency } from "@/lib/utils";

interface PriceChartProps {
  data: { date: string; price: number }[];
  height?: number;
}

export function PriceChart({ data, height = 300 }: PriceChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-neutral-200 dark:border-neutral-800 text-neutral-500"
        style={{ height }}
      >
        No price history yet
      </div>
    );
  }

  const isPositive =
    data.length >= 2 && data[data.length - 1].price >= data[0].price;
  const color = isPositive ? "#16a34a" : "#dc2626";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.2} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.1} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          stroke="#888"
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          stroke="#888"
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--tooltip-bg, #1a1a1a)",
            border: "1px solid #333",
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number) => [formatCurrency(value), "Price"]}
        />
        <Area
          type="monotone"
          dataKey="price"
          stroke={color}
          strokeWidth={2}
          fill="url(#priceGradient)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
