export default function Marquee({ text }: { text: string }) {
  const item = (
    <span className="mx-4 text-[12px] font-extrabold tracking-[0.22em] text-paper-100 whitespace-nowrap">
      {text}
    </span>
  );
  return (
    <div className="bg-emerald-900 overflow-hidden py-2.5 border-y border-emerald-800">
      <div className="marquee-track">
        {Array.from({ length: 8 }).map((_, i) => (
          <span key={i}>{item}</span>
        ))}
      </div>
    </div>
  );
}
