"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

export default function IndexesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["indexes"],
    queryFn: () => api.getIndexes(),
  });

  const indexes = data?.indexes || [];

  const grouped = {
    league: indexes.filter((i: any) => i.indexType === "league"),
    team: indexes.filter((i: any) => i.indexType === "team"),
    position: indexes.filter((i: any) => i.indexType === "position"),
    momentum: indexes.filter((i: any) => i.indexType === "momentum"),
  };

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Indexes</h1>

      {isLoading && (
        <div className="py-20 text-center text-neutral-500">Loading...</div>
      )}

      {Object.entries(grouped).map(([type, items]) => {
        if ((items as any[]).length === 0) return null;
        return (
          <div key={type} className="mb-8">
            <h2 className="mb-3 text-lg font-semibold capitalize">{type} Indexes</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(items as any[]).map((idx) => (
                <Link
                  key={idx.id}
                  href={`/indexes/${idx.id}`}
                  className="rounded-lg border border-neutral-200 p-4 transition-colors hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
                >
                  <div className="font-medium text-neutral-900 dark:text-white">
                    {idx.name}
                  </div>
                  {idx.description && (
                    <div className="mt-1 text-xs text-neutral-500">
                      {idx.description}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
