"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatCurrency, formatPct, pctColor } from "@/lib/utils";
import Link from "next/link";

export default function PortfolioPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.getPortfolio(),
  });

  const { data: tradesData } = useQuery({
    queryKey: ["trades"],
    queryFn: () => api.getTrades(),
  });

  if (isLoading) {
    return (
      <div className="py-20 text-center text-neutral-500">Loading...</div>
    );
  }

  const portfolio = data;
  const trades = tradesData?.trades || [];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Portfolio</h1>

      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
          <div className="text-xs text-neutral-500">Total Value</div>
          <div className="mt-1 text-2xl font-bold">
            {formatCurrency(portfolio?.totalValue || 0)}
          </div>
        </div>
        <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
          <div className="text-xs text-neutral-500">Portfolio Value</div>
          <div className="mt-1 text-2xl font-bold">
            {formatCurrency(portfolio?.totalPositionValue || 0)}
          </div>
        </div>
        <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
          <div className="text-xs text-neutral-500">Cash Balance</div>
          <div className="mt-1 text-2xl font-bold">
            {formatCurrency(portfolio?.cashBalance || 0)}
          </div>
        </div>
      </div>

      <h2 className="mb-3 text-lg font-semibold">Positions</h2>
      {(!portfolio?.positions || portfolio.positions.length === 0) ? (
        <div className="rounded-lg border border-neutral-200 py-10 text-center text-neutral-500 dark:border-neutral-800">
          No positions yet. Start trading on the Discover page.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Qty</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Avg Cost</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Value</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">P&L</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((pos: any) => (
                <tr
                  key={pos.playerSeasonId}
                  className="border-b border-neutral-100 dark:border-neutral-800/50"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/players/${pos.playerSeasonId}`}
                      className="font-medium hover:underline"
                    >
                      {pos.player?.firstName} {pos.player?.lastName}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{pos.quantity}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatCurrency(pos.avgCost)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatCurrency(pos.currentPrice)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatCurrency(pos.marketValue)}</td>
                  <td className={`px-4 py-3 text-right font-mono ${pctColor(pos.unrealizedPnlPct)}`}>
                    {formatCurrency(pos.unrealizedPnl)} ({formatPct(pos.unrealizedPnlPct)})
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="mb-3 mt-8 text-lg font-semibold">Recent Trades</h2>
      {trades.length === 0 ? (
        <div className="rounded-lg border border-neutral-200 py-10 text-center text-neutral-500 dark:border-neutral-800">
          No trades yet.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Date</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Side</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Qty</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Total</th>
              </tr>
            </thead>
            <tbody>
              {trades.slice(0, 20).map((t: any) => (
                <tr key={t.id} className="border-b border-neutral-100 dark:border-neutral-800/50">
                  <td className="px-4 py-3 text-neutral-500">{new Date(t.executedAt).toLocaleDateString()}</td>
                  <td className="px-4 py-3 font-medium">{t.player?.firstName} {t.player?.lastName}</td>
                  <td className="px-4 py-3">
                    <span className={t.side === "buy" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                      {t.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{t.quantity}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatCurrency(t.price)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatCurrency(t.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
