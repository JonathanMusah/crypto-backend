export default function PriceTag({
  price,
  showPrice,
}: {
  price: number | null;
  showPrice: boolean;
}) {
  const label = showPrice && price != null ? `GH₵${price}` : "DM for price";

  return (
    <div className="absolute -top-2 -right-2 rotate-6 drop-shadow-md">
      <svg width="76" height="40" viewBox="0 0 76 40" className="overflow-visible">
        <path
          d="M8 2 H68 L74 20 L68 38 H8 A6 6 0 0 1 2 32 V8 A6 6 0 0 1 8 2 Z"
          fill="var(--marigold-400)"
          stroke="var(--emerald-900)"
          strokeWidth="1.5"
        />
        <circle cx="11" cy="20" r="2.2" fill="var(--emerald-900)" />
        <text
          x="42"
          y="24"
          textAnchor="middle"
          fontFamily="Work Sans"
          fontWeight="800"
          fontSize={label.length > 9 ? "9.5" : "12"}
          fill="var(--emerald-900)"
        >
          {label}
        </text>
      </svg>
    </div>
  );
}
