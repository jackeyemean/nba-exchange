"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default function LeaderboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["leaderboard"],
    queryFn: () => api.getLeaderboard(),
  });

  const entries = data?.entries || [];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Leaderboard</h1>

      {isLoading && (
        <div className="py-20 text-center text-neutral-500">Loading...</div>
      )}

      {!isLoading && entries.length === 0 && (
        <div className="rounded-lg border border-neutral-200 py-10 text-center text-neutral-500 dark:border-neutral-800">
          No leaderboard data yet.
        </div>
      )}

      {entries.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Rank</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">User</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Portfolio</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Cash</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Total</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry: any, i: number) => (
                <tr
                  key={entry.userId}
                  className="border-b border-neutral-100 dark:border-neutral-800/50"
                >
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                        i === 0
                          ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                          : i === 1
                            ? "bg-neutral-200 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300"
                            : i === 2
                              ? "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300"
                              : "text-neutral-500"
                      }`}
                    >
                      {entry.rank || i + 1}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium">{entry.username}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {formatCurrency(entry.portfolioValue)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-neutral-500">
                    {formatCurrency(entry.cashBalance)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {formatCurrency(entry.totalValue)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
