"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { PriceChart } from "@/components/price-chart";
import { formatCurrency, formatPct, pctColor } from "@/lib/utils";
import Link from "next/link";

export default function IndexDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const { data, isLoading } = useQuery({
    queryKey: ["index", id],
    queryFn: () => api.getIndex(id),
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

  const latestLevel = history?.[0];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{index.name}</h1>
        {index.description && (
          <p className="mt-1 text-sm text-neutral-500">{index.description}</p>
        )}
        {latestLevel && (
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-2xl font-semibold">
              {latestLevel.level?.toFixed(2)}
            </span>
            <span className={`text-sm ${pctColor(latestLevel.changePct)}`}>
              {formatPct(latestLevel.changePct)}
            </span>
          </div>
        )}
      </div>

      <div className="mb-8 rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <PriceChart data={chartData} />
      </div>

      <h2 className="mb-3 text-lg font-semibold">Constituents</h2>
      <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
              <th className="px-4 py-3 text-left font-medium text-neutral-600 dark:text-neutral-400">Player</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Weight</th>
              <th className="px-4 py-3 text-right font-medium text-neutral-600 dark:text-neutral-400">Price</th>
            </tr>
          </thead>
          <tbody>
            {(constituents || []).map((c: any) => (
              <tr
                key={c.playerSeasonId}
                className="border-b border-neutral-100 dark:border-neutral-800/50"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/players/${c.playerSeasonId}`}
                    className="font-medium hover:underline"
                  >
                    {c.player?.firstName} {c.player?.lastName}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {(c.weight * 100).toFixed(2)}%
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {formatCurrency(c.price)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
