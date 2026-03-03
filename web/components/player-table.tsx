"use client";

import Link from "next/link";
import { formatCurrency, formatCompact, formatPct, pctColor } from "@/lib/utils";

interface PlayerRow {
  id: number;
  firstName: string;
  lastName: string;
  position: string;
  teamAbbreviation: string;
  tier: string;
  floatShares: number;
  price: number;
  changePct: number | null;
  marketCap: number;
}

const TIER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  magnificent_7: { bg: "bg-amber-100 dark:bg-amber-900/40", text: "text-amber-800 dark:text-amber-300", label: "Mag 7" },
  blue_chip:     { bg: "bg-blue-100 dark:bg-blue-900/40",   text: "text-blue-800 dark:text-blue-300",   label: "Blue Chip" },
  growth:        { bg: "bg-emerald-100 dark:bg-emerald-900/40", text: "text-emerald-800 dark:text-emerald-300", label: "Growth" },
  mid_cap:       { bg: "bg-purple-100 dark:bg-purple-900/40", text: "text-purple-800 dark:text-purple-300", label: "Mid Cap" },
  small_cap:     { bg: "bg-neutral-100 dark:bg-neutral-800",  text: "text-neutral-600 dark:text-neutral-400", label: "Small Cap" },
  penny_stock:   { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-600 dark:text-red-400", label: "Penny" },
};

function TierBadge({ tier }: { tier: string }) {
  const style = TIER_STYLES[tier] || TIER_STYLES.penny_stock;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

export function PlayerTable({ players }: { players: PlayerRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
            <th className="w-10 px-3 py-3 text-center font-medium text-neutral-600 dark:text-neutral-400">#</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Pos</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Team</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Tier</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Shares</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Change</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Market Cap</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p, idx) => (
              <tr
                key={p.id}
                className="border-b border-neutral-100 transition-colors hover:bg-neutral-50 dark:border-neutral-800/50 dark:hover:bg-neutral-900/50"
              >
                <td className="w-10 px-3 py-3 text-center font-mono text-neutral-400 dark:text-neutral-500">
                  {idx + 1}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/players/${p.id}`}
                    className="font-medium text-neutral-900 hover:underline dark:text-white"
                  >
                    {p.firstName} {p.lastName}
                  </Link>
                </td>
                <td className="px-4 py-3 text-neutral-600 dark:text-neutral-400">{p.position}</td>
                <td className="px-4 py-3 text-neutral-600 dark:text-neutral-400">{p.teamAbbreviation}</td>
                <td className="px-4 py-3">
                  <TierBadge tier={p.tier} />
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-600 dark:text-neutral-400">
                  {formatCompact(p.floatShares)}
                </td>
                <td className="px-4 py-3 text-right font-mono">{formatCurrency(p.price)}</td>
                <td className={`px-4 py-3 text-right font-mono ${pctColor(p.changePct)}`}>
                  {formatPct(p.changePct)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-600 dark:text-neutral-400">
                  {formatCompact(p.marketCap)}
                </td>
              </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
