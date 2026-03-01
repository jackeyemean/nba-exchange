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
  price: number;
  changePct: number | null;
  marketCap: number;
}

export function PlayerTable({ players }: { players: PlayerRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Pos</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Team</th>
            <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Tier</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Change</th>
            <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Market Cap</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <tr
              key={p.id}
              className="border-b border-neutral-100 transition-colors hover:bg-neutral-50 dark:border-neutral-800/50 dark:hover:bg-neutral-900/50"
            >
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
                <span className="inline-block rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium capitalize dark:bg-neutral-800">
                  {p.tier}
                </span>
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
