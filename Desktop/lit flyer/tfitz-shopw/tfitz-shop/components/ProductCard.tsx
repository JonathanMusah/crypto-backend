import { Item } from "@/lib/supabase";
import PriceTag from "./PriceTag";
import { WHATSAPP_NUMBER } from "@/lib/config";

export default function ProductCard({ item }: { item: Item }) {
  const message = encodeURIComponent(
    `Hi! Is the "${item.name}" still available?`
  );
  const waLink = `https://wa.me/${WHATSAPP_NUMBER}?text=${message}`;

  return (
    <div className="group">
      <div className="relative">
        <div className="aspect-square overflow-hidden rounded-xl bg-emerald-900/5 border border-emerald-900/10">
          <img
            src={item.image_url}
            alt={item.name}
            className={`w-full h-full object-cover transition duration-300 group-hover:scale-[1.03] ${
              item.sold ? "grayscale opacity-60" : ""
            }`}
          />
        </div>
        {!item.sold && (
          <PriceTag price={item.price} showPrice={item.show_price} />
        )}
        {item.sold && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="bg-emerald-900 text-paper-100 text-xs font-extrabold tracking-[0.15em] px-4 py-1.5 rounded-full rotate-[-6deg]">
              SOLD
            </span>
          </div>
        )}
      </div>

      <div className="mt-3 flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-[15px] leading-tight">{item.name}</p>
          <p className="text-[11px] font-bold tracking-[0.1em] text-coral-600 mt-0.5">
            {item.category.toUpperCase()}
          </p>
        </div>
      </div>

      {!item.sold && (
        <a
          href={waLink}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2.5 flex items-center justify-center gap-2 w-full bg-emerald-900 text-paper-100 text-[13px] font-bold py-2.5 rounded-full hover:bg-emerald-800 transition"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <path d="M12 2a10 10 0 00-8.6 15L2 22l5.2-1.4A10 10 0 1012 2zm5.8 14.2c-.3.7-1.4 1.3-2 1.4-.5.1-1.2.2-3.7-.8-3.1-1.3-5.1-4.4-5.3-4.6-.1-.2-1.3-1.7-1.3-3.2s.8-2.3 1.1-2.6c.3-.3.6-.4.8-.4h.6c.2 0 .4 0 .6.5.3.6 1 2.1 1.1 2.2.1.2.1.4 0 .6-.1.2-.2.3-.4.5l-.5.6c-.2.2-.3.4-.1.7.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.4 2.5 1.6.3.1.5.1.6-.1.2-.2.7-.8.9-1.1.2-.3.4-.2.6-.1l1.9.9c.2.1.4.2.4.3.1.2.1.7-.1 1.4z" />
          </svg>
          Chat to buy
        </a>
      )}
    </div>
  );
}
