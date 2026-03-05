"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { PriceChart } from "@/components/price-chart";
import { IndexTradePanel } from "@/components/index-trade-panel";
import { formatCurrency, formatCompact, formatPct, pctColor } from "@/lib/utils";
import Link from "next/link";

type PriceRange = "all" | "season" | "month" | "week" | "day";

const INDEX_NAME_TO_TICKER: Record<string, string> = {
  "S&P 500": "INX",
  "S&P 100": "OEX",
  "Dow Jones Industrial Average": "DJIA",
  "Magnificent 7": "MAG7",
  "Blue Chips": "BLUE",
  "Renaissance IPO Index": "IPO",
};

const TEAM_NAME_TO_ABBREV: Record<string, string> = {
  "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
  "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
  "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
  "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
  "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
  "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
  "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
  "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
  "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
  "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
};

function getIndexTicker(idx: { ticker?: string; indexType?: string; index_type?: string; name?: string; teamAbbreviation?: string; team_abbreviation?: string }): string {
  if (idx.ticker && idx.ticker.trim()) return idx.ticker;
  const name = idx.name || "";
  if (INDEX_NAME_TO_TICKER[name]) return INDEX_NAME_TO_TICKER[name];
  const type = idx.indexType || idx.index_type || "";
  if (type === "team") {
    const abbrev = idx.teamAbbreviation ?? idx.team_abbreviation;
    if (abbrev) return abbrev;
    const display = displayName(idx.name || "");
    return TEAM_NAME_TO_ABBREV[display] || "—";
  }
  if (type === "position") {
    const name = (idx.name || "").toLowerCase();
    if (name.includes("guard")) return "GUARD";
    if (name.includes("wing")) return "WINGS";
    if (name.includes("big")) return "BIGS";
  }
  return "—";
}

function displayName(name: string): string {
  return name.replace(/\s+Index$/i, "");
}

function getTicker(p: { ticker?: string; firstName: string; lastName: string }): string {
  if (p.ticker && p.ticker.trim()) return p.ticker;
  const f = (p.firstName || "").replace(/[^a-zA-Z]/g, "").slice(0, 2) || (p.firstName || "").slice(0, 1);
  const l = (p.lastName || "").replace(/[^a-zA-Z]/g, "").slice(0, 2) || (p.lastName || "").slice(0, 1);
  return (f + l).toUpperCase() || "—";
}

const TIER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  magnificent_7: { bg: "bg-amber-100 dark:bg-amber-900/40", text: "text-amber-800 dark:text-amber-300", label: "Mag 7" },
  blue_chip: { bg: "bg-blue-100 dark:bg-blue-900/40", text: "text-blue-800 dark:text-blue-300", label: "Blue Chip" },
  growth: { bg: "bg-emerald-100 dark:bg-emerald-900/40", text: "text-emerald-800 dark:text-emerald-300", label: "Growth" },
  mid_cap: { bg: "bg-purple-100 dark:bg-purple-900/40", text: "text-purple-800 dark:text-purple-300", label: "Mid Cap" },
  penny_stock: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-600 dark:text-red-400", label: "Penny" },
  small_cap: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-600 dark:text-red-400", label: "Penny" },
};

function TierBadge({ tier }: { tier: string }) {
  const style = TIER_STYLES[tier] || TIER_STYLES.penny_stock;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

export default function IndexDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [range, setRange] = useState<PriceRange>("season");
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["index", id, range],
    queryFn: () => api.getIndex(id, range),
    enabled: !!id,
  });

  if (isLoading) {
    return <div className="py-20 text-center text-neutral-500">Loading...</div>;
  }

  if (!data?.index) {
    return <div className="py-20 text-center text-neutral-500">Index not found</div>;
  }

  const { index, constituents, history } = data;
  const chartData = (history || [])
    .slice()
    .reverse()
    .map((h: any) => ({
      date: h.tradeDate,
      price: h.level,
    }));

  const rangeChangePct =
    chartData.length >= 2 && chartData[0].price > 0
      ? (chartData[chartData.length - 1].price - chartData[0].price) / chartData[0].price
      : null;

  const ticker = getIndexTicker(index);

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-baseline gap-2">
          <h1 className="text-2xl font-bold">{displayName(index.name)}</h1>
          <span className="font-mono text-lg font-semibold text-neutral-500 dark:text-neutral-400">
            ({ticker})
          </span>
        </div>
        {index.description && (
          <p className="mt-1 text-sm text-neutral-500">{index.description}</p>
        )}
        <div className="mt-2 flex items-baseline gap-3">
          {chartData.length > 0 && (
            <>
              <span className="text-2xl font-semibold">
                {chartData[chartData.length - 1].price?.toFixed(2)}
              </span>
              <span className={`text-sm ${pctColor(rangeChangePct)}`}>
                {formatPct(rangeChangePct)}
              </span>
              <span className="text-xs text-neutral-500">
                {range === "all" ? "All time" : range === "season" ? "This season" : range === "month" ? "Past month" : range === "week" ? "Past week" : "Past Day"}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="mb-8 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Index Level</h2>
              <div className="flex gap-1 rounded-md border border-neutral-200 p-0.5 dark:border-neutral-700">
                {(["all", "season", "month", "week", "day"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded px-2 py-1 text-xs font-medium capitalize transition-colors ${
                      range === r
                        ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                        : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
                    }`}
                  >
                    {r === "all" ? "All Time" : r === "season" ? "This Season" : r === "month" ? "Past Month" : r === "week" ? "Past Week" : "Past Day"}
                  </button>
                ))}
              </div>
            </div>
            <PriceChart data={chartData} range={range} />
          </div>
        </div>
        <div>
          <IndexTradePanel
            indexId={id}
            indexName={displayName(index.name)}
            currentPrice={chartData.length > 0 ? chartData[chartData.length - 1].price : 0}
            onTradeComplete={() => {
              queryClient.invalidateQueries({ queryKey: ["portfolio"] });
            }}
          />
        </div>
      </div>

      <h2 className="mb-3 text-lg font-semibold">Holdings</h2>
      <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
              <th className="w-10 px-3 py-3 text-center font-medium text-neutral-600 dark:text-neutral-400">#</th>
              <th className="px-3 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Ticker</th>
              <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
              <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Pos</th>
              <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Team</th>
              <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Tier</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Shares</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Weight</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Change</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Market Cap</th>
            </tr>
          </thead>
          <tbody>
            {(constituents || []).map((c: any, idx: number) => (
              <tr
                key={c.playerSeasonId}
                className="border-b border-neutral-100 transition-colors hover:bg-neutral-50 dark:border-neutral-800/50 dark:hover:bg-neutral-900/50"
              >
                <td className="w-10 px-3 py-3 text-center font-mono text-neutral-400 dark:text-neutral-500">
                  {idx + 1}
                </td>
                <td className="px-3 py-3 font-mono text-sm font-semibold text-neutral-700 dark:text-neutral-300">
                  {getTicker(c.player || { firstName: "", lastName: "" })}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/players/${c.playerSeasonId}`}
                    className="font-medium text-neutral-900 hover:underline dark:text-white"
                  >
                    {c.player?.firstName} {c.player?.lastName}
                  </Link>
                </td>
                <td className="px-4 py-3 text-neutral-600 dark:text-neutral-400">{(c.position ?? c.pos) || "—"}</td>
                <td className="px-4 py-3 text-neutral-600 dark:text-neutral-400">{(c.teamAbbreviation ?? c.team_abbreviation) || "—"}</td>
                <td className="px-4 py-3">
                  <TierBadge tier={c.tier || "penny_stock"} />
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-600 dark:text-neutral-400">
                  {formatCompact(c.floatShares ?? 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-600 dark:text-neutral-400">
                  {((c.weight ?? 0) * 100).toFixed(2)}%
                </td>
                <td className="px-4 py-3 text-right font-mono">{formatCurrency(c.price ?? 0)}</td>
                <td className={`px-4 py-3 text-right font-mono ${pctColor(c.changePct ?? c.change_pct)}`}>
                  {formatPct(c.changePct ?? c.change_pct)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-600 dark:text-neutral-400">
                  {formatCompact(c.marketCap ?? 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
