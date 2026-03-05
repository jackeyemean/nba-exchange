"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCurrency, formatPct, pctColor } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";

function StatCard({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  accent?: "emerald" | "blue" | "amber";
}) {
  const accentClasses = {
    emerald:
      "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/50",
    blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-900/50",
    amber:
      "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-900/50",
  };
  return (
    <div className="relative overflow-hidden rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900/50">
      <div
        className={`mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg border ${accentClasses[accent || "emerald"]}`}
      >
        {icon}
      </div>
      <div className="text-xs font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
        {label}
      </div>
      <div className="mt-1 text-xl tracking-tight">{value}</div>
    </div>
  );
}

export default function PortfolioPage() {
  const { isLoggedIn } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.getPortfolio(),
    enabled: isLoggedIn,
  });

  const { data: tradesData } = useQuery({
    queryKey: ["trades"],
    queryFn: () => api.getTrades(),
    enabled: isLoggedIn,
  });

  if (!isLoggedIn) {
    return (
      <div>
        <h1 className="mb-2 text-2xl font-bold">Portfolio</h1>
        <p className="mb-6 text-neutral-500">
          Track your positions and trading history.
        </p>
        <div className="rounded-xl border border-neutral-200 py-20 text-center dark:border-neutral-800">
          <p className="mb-4 text-neutral-500">
            Log in to view your portfolio and trading history.
          </p>
          <Link
            href="/login"
            className="inline-block rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
          >
            Log in with Google
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-600 dark:border-neutral-700 dark:border-t-neutral-400" />
          <p className="text-sm text-neutral-500">Loading portfolio...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 py-16 text-center dark:border-red-900/50 dark:bg-red-950/30">
        <p className="mb-2 font-medium text-red-700 dark:text-red-400">
          Failed to load portfolio
        </p>
        <p className="text-sm text-red-600 dark:text-red-500">
          Try logging in again.
        </p>
      </div>
    );
  }

  const portfolio = data;
  const trades = tradesData?.trades || [];

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold">Portfolio</h1>
      <p className="mb-8 text-neutral-500">
        Your holdings and trading activity.
      </p>

      {/* Summary cards */}
      <div className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Value"
          value={formatCurrency(portfolio?.totalValue || 0)}
          accent="emerald"
          icon={
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          }
        />
        <StatCard
          label="Holdings"
          value={formatCurrency(portfolio?.totalPositionValue || 0)}
          accent="blue"
          icon={
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          }
        />
        <StatCard
          label="Cash Balance"
          value={formatCurrency(portfolio?.cashBalance || 0)}
          accent="amber"
          icon={
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          }
        />
      </div>

      {/* Positions */}
      <section className="mb-12">
        <h2 className="mb-4 text-lg font-semibold">Your Positions</h2>
        {(!portfolio?.positions || portfolio.positions.length === 0) &&
        (!portfolio?.indexPositions || portfolio.indexPositions.length === 0) ? (
          <div className="rounded-xl border border-neutral-200 py-16 text-center dark:border-neutral-800">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-800">
              <svg
                className="h-6 w-6 text-neutral-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                />
              </svg>
            </div>
            <p className="mb-1 font-medium text-neutral-700 dark:text-neutral-300">
              No positions yet
            </p>
            <p className="mb-6 text-sm text-neutral-500">
              Start trading on the Discover page to build your portfolio.
            </p>
            <Link
              href="/"
              className="inline-block rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
            >
              Discover players
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {portfolio.positions?.map((pos: any) => (
              <Link
                key={`player-${pos.playerSeasonId}`}
                href={`/players/${pos.playerSeasonId}`}
                className="block rounded-xl border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-300 hover:bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900/50 dark:hover:border-neutral-700 dark:hover:bg-neutral-900"
              >
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold">
                      {pos.player?.firstName} {pos.player?.lastName}
                    </p>
                    <p className="text-sm text-neutral-500">
                      {pos.quantity} shares · Avg {formatCurrency(pos.avgCost)}
                    </p>
                  </div>
                  <div className="flex items-baseline gap-6 text-right">
                    <div>
                      <p className="text-xs text-neutral-500">Value</p>
                      <p className="font-mono">
                        {formatCurrency(pos.marketValue)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500">P&L</p>
                      <p
                        className={`font-mono ${pctColor(pos.unrealizedPnlPct)}`}
                      >
                        {formatCurrency(pos.unrealizedPnl)} (
                        {formatPct(pos.unrealizedPnlPct)})
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
            {portfolio.indexPositions?.map((pos: any) => (
              <Link
                key={`index-${pos.indexId}`}
                href={`/indexes/${pos.indexId}`}
                className="block rounded-xl border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-300 hover:bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900/50 dark:hover:border-neutral-700 dark:hover:bg-neutral-900"
              >
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold">
                      {pos.index?.name}
                      {pos.index?.ticker && (
                        <span className="ml-2 font-mono text-sm text-neutral-500">
                          ({pos.index.ticker})
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-neutral-500">
                      {pos.quantity} shares · Avg {formatCurrency(pos.avgCost)}
                    </p>
                  </div>
                  <div className="flex items-baseline gap-6 text-right">
                    <div>
                      <p className="text-xs text-neutral-500">Value</p>
                      <p className="font-mono">
                        {formatCurrency(pos.marketValue)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-neutral-500">P&L</p>
                      <p
                        className={`font-mono ${pctColor(pos.unrealizedPnlPct)}`}
                      >
                        {formatCurrency(pos.unrealizedPnl)} (
                        {formatPct(pos.unrealizedPnlPct)})
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Recent trades */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Recent Trades</h2>
        {trades.length === 0 ? (
          <div className="rounded-xl border border-neutral-200 py-12 text-center dark:border-neutral-800">
            <p className="text-neutral-500">No trades yet.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800">
            <div className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {trades.slice(0, 15).map((t: any) => (
                <div
                  key={t.id}
                  className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-5"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`inline-flex h-8 min-w-[3rem] items-center justify-center rounded-md text-xs font-semibold ${
                        t.side === "buy"
                          ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
                      }`}
                    >
                      {t.side.toUpperCase()}
                    </span>
                    <div>
                      <p className="font-medium">
                        {t.player
                          ? `${t.player.firstName} ${t.player.lastName}`
                          : t.index?.name ?? "—"}
                      </p>
                      <p className="text-xs text-neutral-500">
                        {new Date(t.executedAt).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono">
                      {formatCurrency(t.total)}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {t.quantity} @ {formatCurrency(t.price)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
