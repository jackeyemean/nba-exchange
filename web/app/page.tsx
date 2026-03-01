"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PlayerTable } from "@/components/player-table";
import { useState } from "react";

export default function DiscoverPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"price" | "change" | "mcap">("mcap");

  const { data, isLoading, error } = useQuery({
    queryKey: ["players"],
    queryFn: () => api.getPlayers(),
  });

  const players = (data?.players || [])
    .filter((p: any) => {
      if (!search) return true;
      const name = `${p.firstName} ${p.lastName}`.toLowerCase();
      return name.includes(search.toLowerCase());
    })
    .sort((a: any, b: any) => {
      if (sortBy === "price") return b.price - a.price;
      if (sortBy === "change") return (b.changePct ?? 0) - (a.changePct ?? 0);
      return b.marketCap - a.marketCap;
    });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Discover</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Browse all player stocks. Prices update at market open.
        </p>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="text"
          placeholder="Search players..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-neutral-200 bg-transparent px-3 py-2 text-sm dark:border-neutral-700 sm:max-w-xs"
        />
        <div className="flex gap-1 rounded-md border border-neutral-200 p-0.5 dark:border-neutral-700">
          {(["mcap", "price", "change"] as const).map((key) => (
            <button
              key={key}
              onClick={() => setSortBy(key)}
              className={`rounded px-3 py-1 text-xs font-medium capitalize transition-colors ${
                sortBy === key
                  ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                  : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
              }`}
            >
              {key === "mcap" ? "Market Cap" : key}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="py-20 text-center text-neutral-500">
          Loading players...
        </div>
      )}
      {error && (
        <div className="py-20 text-center text-red-500">
          Failed to load players
        </div>
      )}
      {!isLoading && !error && <PlayerTable players={players} />}
    </div>
  );
}
