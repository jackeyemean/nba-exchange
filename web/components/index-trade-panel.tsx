"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { useAuth } from "./auth-provider";

interface IndexTradePanelProps {
  indexId: number;
  indexName: string;
  currentPrice: number;
  onTradeComplete?: () => void;
}

export function IndexTradePanel({
  indexId,
  indexName,
  currentPrice,
  onTradeComplete,
}: IndexTradePanelProps) {
  const { isLoggedIn } = useAuth();
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const confirmDialogRef = useRef<HTMLDialogElement>(null);

  const total = quantity * currentPrice;
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearHold = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startHold = useCallback(
    (delta: number) => {
      const step = () =>
        setQuantity((q) => {
          const next = q + delta;
          if (next < 1) {
            clearHold();
            return 1;
          }
          return next;
        });
      step();
      timeoutRef.current = setTimeout(() => {
        intervalRef.current = setInterval(step, 80);
      }, 400);
    },
    [clearHold]
  );

  const openConfirm = () => {
    setError(null);
    confirmDialogRef.current?.showModal();
  };

  const closeConfirm = () => {
    confirmDialogRef.current?.close();
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.placeIndexOrder(indexId, side, quantity);
      closeConfirm();
      setSuccess(
        `${side === "buy" ? "Bought" : "Sold"} ${quantity} shares of ${indexName}`
      );
      setShowSuccessModal(true);
      onTradeComplete?.();
      setTimeout(() => setShowSuccessModal(false), 2500);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <h3 className="mb-3 text-sm font-semibold text-neutral-900 dark:text-white">
          Trade {indexName}
        </h3>
        <p className="mb-4 text-sm text-neutral-500">
          Log in to buy and sell shares.
        </p>
        <Link
          href="/login"
          className="block rounded-md bg-neutral-900 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
        >
          Log in with Google
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <h3 className="mb-3 text-sm font-semibold text-neutral-900 dark:text-white">
        Trade {indexName}
      </h3>

      <div className="mb-3 flex rounded-md border border-neutral-200 dark:border-neutral-700">
        <button
          onClick={() => setSide("buy")}
          className={`flex-1 rounded-l-md py-2 text-sm font-medium transition-colors ${
            side === "buy"
              ? "bg-green-600 text-white"
              : "text-neutral-600 hover:bg-neutral-50 dark:text-neutral-400 dark:hover:bg-neutral-800"
          }`}
        >
          Buy
        </button>
        <button
          onClick={() => setSide("sell")}
          className={`flex-1 rounded-r-md py-2 text-sm font-medium transition-colors ${
            side === "sell"
              ? "bg-red-600 text-white"
              : "text-neutral-600 hover:bg-neutral-50 dark:text-neutral-400 dark:hover:bg-neutral-800"
          }`}
        >
          Sell
        </button>
      </div>

      <label className="mb-1 block text-xs text-neutral-500">Shares</label>
      <div className="mb-3 flex rounded-md border border-neutral-200 dark:border-neutral-700">
        <button
          type="button"
          onMouseDown={() => startHold(-1)}
          onMouseUp={clearHold}
          onMouseLeave={clearHold}
          onTouchStart={() => startHold(-1)}
          onTouchEnd={clearHold}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-l-md border-r border-neutral-200 text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900 dark:border-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
          aria-label="Decrease"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
        <input
          type="number"
          min={1}
          value={quantity}
          onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
          className="w-full border-0 bg-transparent px-3 py-2 text-center text-sm [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none dark:bg-transparent"
        />
        <button
          type="button"
          onMouseDown={() => startHold(1)}
          onMouseUp={clearHold}
          onMouseLeave={clearHold}
          onTouchStart={() => startHold(1)}
          onTouchEnd={clearHold}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-r-md border-l border-neutral-200 text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900 dark:border-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
          aria-label="Increase"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="text-neutral-500">Price</span>
        <span className="font-mono">{formatCurrency(currentPrice)}</span>
      </div>
      <div className="mb-4 flex items-center justify-between text-sm">
        <span className="text-neutral-500">Total</span>
        <span className="font-mono">{formatCurrency(total)}</span>
      </div>

      <button
        onClick={openConfirm}
        disabled={loading}
        className={`w-full rounded-md py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50 ${
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

      <dialog
        ref={confirmDialogRef}
        className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-neutral-200 bg-white p-0 shadow-lg dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 [&::backdrop]:bg-black/50"
        onCancel={closeConfirm}
      >
        <div className="p-5">
          <h4 className="mb-4 text-base font-medium text-neutral-900 dark:text-neutral-100">
            Confirm {side === "buy" ? "Buy" : "Sell"}
          </h4>
          <div className="space-y-2 rounded-md border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-600 dark:bg-neutral-900/50">
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500 dark:text-neutral-400">Index</span>
              <span>{indexName}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500 dark:text-neutral-400">Shares</span>
              <span className="font-mono">{quantity}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500 dark:text-neutral-400">Price</span>
              <span className="font-mono">{formatCurrency(currentPrice)}</span>
            </div>
            <div className="flex justify-between border-t border-neutral-200 pt-2 dark:border-neutral-600">
              <span>Total</span>
              <span className="font-mono">{formatCurrency(total)}</span>
            </div>
          </div>
          {error && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>
          )}
          <div className="mt-5 flex gap-2">
            <button
              onClick={closeConfirm}
              disabled={loading}
              className="flex-1 rounded-md border border-neutral-200 py-2.5 text-sm hover:bg-neutral-50 dark:border-neutral-600 dark:hover:bg-neutral-700"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={loading}
              className={`flex-1 rounded-md py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50 ${
                side === "buy"
                  ? "bg-green-600 hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-700"
                  : "bg-red-600 hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700"
              }`}
            >
              {loading ? "Processing..." : "Confirm"}
            </button>
          </div>
        </div>
      </dialog>

      {showSuccessModal && (
        <div className="fixed bottom-4 right-4 z-50" aria-live="polite">
          <div className="flex items-center gap-2.5 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 shadow-md dark:border-neutral-600 dark:bg-neutral-800">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/40">
              <svg
                className="h-3.5 w-3.5 text-green-600 dark:text-green-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-neutral-800 dark:text-neutral-200">
                {success}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
