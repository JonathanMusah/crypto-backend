import { supabase, Item } from "@/lib/supabase";
import { BRAND, WHATSAPP_NUMBER } from "@/lib/config";
import Marquee from "@/components/Marquee";
import ShopGrid from "@/components/ShopGrid";

export const revalidate = 0;

async function getItems(): Promise<Item[]> {
  const { data, error } = await supabase
    .from("items")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) {
    console.error(error);
    return [];
  }
  return data as Item[];
}

export default async function ShopPage() {
  const items = await getItems();
  const generalWa = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(
    "Hi! I'd like to know more about what's in stock."
  )}`;

  return (
    <>
      {/* HEADER */}
      <header className="grain relative bg-paper-100 pt-10 pb-8 px-6 sm:px-10 border-b border-emerald-900/10">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-3">
            <span className="font-display text-4xl sm:text-5xl text-emerald-900">T</span>
            <span className="w-6 h-3 sm:w-7 sm:h-3.5 bg-emerald-900 rounded-sm" />
            <span className="font-display text-4xl sm:text-5xl text-coral-600">FITZ</span>
          </div>
          <p className="font-script text-2xl text-emerald-800 mt-1">{BRAND.tagline}</p>
        </div>
      </header>

      <Marquee text={`NEW PIECES WEEKLY  •  ${BRAND.city.toUpperCase()}  •  DM TO COP  •`} />

      {/* HERO */}
      <section className="grain bg-emerald-900 text-paper-100 px-6 sm:px-10 py-12">
        <div className="max-w-6xl mx-auto">
          <h1 className="font-display text-5xl sm:text-6xl leading-[0.95]">
            The rack,<br /> online now.
          </h1>
          <p className="mt-4 max-w-md text-[15px] text-paper-100/80 font-medium">
            Every piece checked and cleaned by hand. Tap a piece to chat on
            WhatsApp and ask about size, condition, or price.
          </p>
        </div>
      </section>

      {/* GRID */}
      <main className="flex-1 px-6 sm:px-10 py-10">
        <div className="max-w-6xl mx-auto">
          <ShopGrid items={items} />
        </div>
      </main>

      {/* FOOTER */}
      <footer className="bg-emerald-900 text-paper-100 px-6 sm:px-10 py-10 mt-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
          <div>
            <div className="font-display text-2xl">T-FITZ</div>
            <p className="text-paper-100/60 text-[12.5px] mt-1">{BRAND.city}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a
              href={generalWa}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-[#25D366] text-emerald-950 text-[13px] font-bold px-4 py-2.5 rounded-full"
            >
              WhatsApp
            </a>
            <a
              href={`https://instagram.com/${BRAND.instagram}`}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-paper-100/10 text-paper-100 text-[13px] font-bold px-4 py-2.5 rounded-full"
            >
              @{BRAND.instagram}
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
