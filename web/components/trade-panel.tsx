"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

interface TradePanelProps {
  playerSeasonId: number;
  playerName: string;
  currentPrice: number;
  onTradeComplete?: () => void;
}

export function TradePanel({
  playerSeasonId,
  playerName,
  currentPrice,
  onTradeComplete,
}: TradePanelProps) {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const total = quantity * currentPrice;

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      await api.placeOrder(playerSeasonId, side, quantity);
      setSuccess(
        `${side === "buy" ? "Bought" : "Sold"} ${quantity} shares of ${playerName}`
      );
      onTradeComplete?.();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <h3 className="mb-3 text-sm font-semibold text-neutral-900 dark:text-white">
        Trade {playerName}
      </h3>

      <div className="mb-3 flex rounded-md border border-neutral-200 dark:border-neutral-700">
        <button
          onClick={() => setSide("buy")}
          className={`flex-1 py-2 text-sm font-medium transition-colors rounded-l-md ${
            side === "buy"
              ? "bg-green-600 text-white"
              : "text-neutral-600 hover:bg-neutral-50 dark:text-neutral-400 dark:hover:bg-neutral-800"
          }`}
        >
          Buy
        </button>
        <button
          onClick={() => setSide("sell")}
          className={`flex-1 py-2 text-sm font-medium transition-colors rounded-r-md ${
            side === "sell"
              ? "bg-red-600 text-white"
              : "text-neutral-600 hover:bg-neutral-50 dark:text-neutral-400 dark:hover:bg-neutral-800"
          }`}
        >
          Sell
        </button>
      </div>

      <label className="mb-1 block text-xs text-neutral-500">Shares</label>
      <input
        type="number"
        min={1}
        value={quantity}
        onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
        className="mb-3 w-full rounded-md border border-neutral-200 bg-transparent px-3 py-2 text-sm dark:border-neutral-700"
      />

      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="text-neutral-500">Price</span>
        <span className="font-mono">{formatCurrency(currentPrice)}</span>
      </div>
      <div className="mb-4 flex items-center justify-between text-sm font-medium">
        <span className="text-neutral-500">Total</span>
        <span className="font-mono">{formatCurrency(total)}</span>
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className={`w-full rounded-md py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
          side === "buy"
            ? "bg-green-600 hover:bg-green-700"
            : "bg-red-600 hover:bg-red-700"
        }`}
      >
        {loading
          ? "Processing..."
          : `${side === "buy" ? "Buy" : "Sell"} ${quantity} shares`}
      </button>

      {error && (
        <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
      {success && (
        <p className="mt-2 text-xs text-green-600 dark:text-green-400">
          {success}
        </p>
      )}
    </div>
  );
}
