"use client";

import { useMemo, useState } from "react";
import { Item } from "@/lib/supabase";
import ProductCard from "./ProductCard";

export default function ShopGrid({ items }: { items: Item[] }) {
  const [active, setActive] = useState("All");

  const categories = useMemo(() => {
    const set = new Set(items.map((i) => i.category));
    return ["All", ...Array.from(set)];
  }, [items]);

  const filtered = useMemo(
    () => (active === "All" ? items : items.filter((i) => i.category === active)),
    [items, active]
  );

  if (items.length === 0) {
    return (
      <div className="text-center py-24 px-6">
        <p className="font-display text-3xl text-emerald-900">
          Rack&apos;s being restocked.
        </p>
        <p className="mt-2 text-sm text-emerald-900/60 max-w-sm mx-auto">
          Nothing posted yet — check back soon, or message us directly on WhatsApp.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex gap-2 overflow-x-auto pb-1 px-1 -mx-1 mb-6">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActive(cat)}
            className={`shrink-0 px-4 py-2 rounded-full text-[12.5px] font-bold tracking-wide transition ${
              active === cat
                ? "bg-emerald-900 text-paper-100"
                : "bg-emerald-900/8 text-emerald-900 hover:bg-emerald-900/15"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-5 gap-y-9">
        {filtered.map((item) => (
          <ProductCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
