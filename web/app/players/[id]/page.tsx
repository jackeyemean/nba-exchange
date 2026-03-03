"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { PriceBadge } from "@/components/price-badge";
import { PriceChart } from "@/components/price-chart";
import { TradePanel } from "@/components/trade-panel";
import { formatCompact } from "@/lib/utils";

type PriceRange = "all" | "season" | "month" | "week";

export default function PlayerDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [range, setRange] = useState<PriceRange>("all");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["player", id, range],
    queryFn: () => api.getPlayer(id, range),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="py-20 text-center text-neutral-500">Loading...</div>
    );
  }

  if (!data?.player) {
    return (
      <div className="py-20 text-center text-neutral-500">
        Player not found
      </div>
    );
  }

  const { player, prices } = data;
  const latestPrice = prices?.[prices.length - 1]; // API returns chronological order now
  const chartData = (prices || []).map((p: any) => ({
    date: p.tradeDate,
    price: p.price,
  }));

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-baseline gap-2">
          <h1 className="text-2xl font-bold">
            {player.firstName} {player.lastName}
          </h1>
          <span className="text-sm text-neutral-500">
            {player.position} &middot; {player.teamAbbreviation}
          </span>
        </div>
        {latestPrice && (
          <div className="mt-2 flex items-baseline gap-4">
            <PriceBadge
              price={latestPrice.price}
              changePct={latestPrice.changePct}
              size="lg"
            />
            <span className="text-sm text-neutral-500">
              MCap {formatCompact(latestPrice.marketCap)}
            </span>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Price History</h2>
              <div className="flex gap-1 rounded-md border border-neutral-200 p-0.5 dark:border-neutral-700">
                {(["all", "season", "month", "week"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded px-2 py-1 text-xs font-medium capitalize transition-colors ${
                      range === r
                        ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                        : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
                    }`}
                  >
                    {r === "all" ? "All Time" : r === "season" ? "This Season" : r === "month" ? "Past Month" : "Past Week"}
                  </button>
                ))}
              </div>
            </div>
            <PriceChart data={chartData} range={range} />
          </div>

          {latestPrice && (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: "Perf Score", value: latestPrice.perfScore?.toFixed(1) },
                { label: "Age Mult", value: `${latestPrice.ageMult}x` },
                { label: "Win% Mult", value: `${latestPrice.winPctMult}x` },
                { label: "Injury Mult", value: `${latestPrice.salaryEffMult?.toFixed(3)}x` },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"
                >
                  <div className="text-xs text-neutral-500">{stat.label}</div>
                  <div className="mt-1 text-lg font-semibold">{stat.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <TradePanel
            playerSeasonId={player.id}
            playerName={`${player.firstName} ${player.lastName}`}
            currentPrice={latestPrice?.price || 0}
            onTradeComplete={() => refetch()}
          />
        </div>
      </div>
    </div>
  );
}
