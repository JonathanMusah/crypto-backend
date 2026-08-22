"use client";

import { useEffect, useState, FormEvent } from "react";
import { supabase, Item } from "@/lib/supabase";
import { CATEGORIES, BRAND } from "@/lib/config";
import type { Session } from "@supabase/supabase-js";

export default function AdminPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setCheckingSession(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (checkingSession) return null;
  return session ? <Dashboard /> : <LoginForm />;
}

// ─────────────────────────────────────────────────────────
function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-emerald-950 px-6">
      <form onSubmit={handleLogin} className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <span className="font-display text-3xl text-paper-100">T</span>
          <span className="w-5 h-2.5 bg-marigold-400 rounded-sm" />
          <span className="font-display text-3xl text-coral-500">FITZ</span>
        </div>
        <p className="text-center text-paper-100/50 text-[13px] font-semibold tracking-wide mb-6">
          ADMIN LOGIN
        </p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full mb-3 px-4 py-3 rounded-lg bg-paper-100/5 border border-paper-100/15 text-paper-100 text-sm placeholder:text-paper-100/40 focus:outline-none focus:border-coral-500"
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-4 px-4 py-3 rounded-lg bg-paper-100/5 border border-paper-100/15 text-paper-100 text-sm placeholder:text-paper-100/40 focus:outline-none focus:border-coral-500"
          required
        />
        {error && <p className="text-coral-500 text-[13px] mb-3">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-coral-600 text-paper-100 font-bold text-sm py-3 rounded-lg disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
function Dashboard() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadItems() {
    setLoading(true);
    const { data } = await supabase
      .from("items")
      .select("*")
      .order("created_at", { ascending: false });
    setItems((data as Item[]) ?? []);
    setLoading(false);
  }

  useEffect(() => {
    loadItems();
  }, []);

  return (
    <div className="min-h-screen bg-paper-100">
      <header className="bg-emerald-900 text-paper-100 px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-display text-2xl">T</span>
          <span className="w-4 h-2 bg-marigold-400 rounded-sm" />
          <span className="font-display text-2xl text-coral-500">FITZ</span>
          <span className="ml-2 text-paper-100/50 text-[12px] font-semibold tracking-wide">
            ADMIN
          </span>
        </div>
        <button
          onClick={() => supabase.auth.signOut()}
          className="text-[13px] font-bold text-paper-100/70 hover:text-paper-100"
        >
          Sign out
        </button>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-10">
        <AddItemForm onAdded={loadItems} />

        <div>
          <h2 className="font-display text-2xl text-emerald-900 mb-4">
            Current pieces ({items.length})
          </h2>
          {loading ? (
            <p className="text-emerald-900/50 text-sm">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-emerald-900/50 text-sm">
              Nothing posted yet. Add your first piece above.
            </p>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <ItemRow key={item.id} item={item} onChanged={loadItems} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
function AddItemForm({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [price, setPrice] = useState("");
  const [showPrice, setShowPrice] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function handleFile(f: File | null) {
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Add a photo first.");
      return;
    }
    setSaving(true);
    setError("");

    try {
      const ext = file.name.split(".").pop();
      const path = `${crypto.randomUUID()}.${ext}`;
      const { error: uploadError } = await supabase.storage
        .from("items")
        .upload(path, file);
      if (uploadError) throw uploadError;

      const { data: pub } = supabase.storage.from("items").getPublicUrl(path);

      const { error: insertError } = await supabase.from("items").insert({
        name,
        category,
        price: price ? Number(price) : null,
        show_price: showPrice,
        image_url: pub.publicUrl,
        sold: false,
      });
      if (insertError) throw insertError;

      setName("");
      setPrice("");
      handleFile(null);
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-2xl border border-emerald-900/10 p-5 sm:p-6"
    >
      <h2 className="font-display text-2xl text-emerald-900 mb-4">Add a piece</h2>

      <div className="grid sm:grid-cols-[140px_1fr] gap-5">
        <label className="block">
          <div className="aspect-square rounded-xl border-2 border-dashed border-emerald-900/20 bg-emerald-900/5 flex items-center justify-center overflow-hidden cursor-pointer hover:border-coral-500 transition">
            {preview ? (
              <img src={preview} alt="Preview" className="w-full h-full object-cover" />
            ) : (
              <span className="text-emerald-900/40 text-[12px] font-semibold text-center px-2">
                Tap to add photo
              </span>
            )}
          </div>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <div className="space-y-3">
          <input
            type="text"
            placeholder="Item name (e.g. Black Flannel Shirt)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-lg border border-emerald-900/15 text-sm focus:outline-none focus:border-coral-500"
            required
          />

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-lg border border-emerald-900/15 text-sm focus:outline-none focus:border-coral-500"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-3">
            <input
              type="number"
              placeholder="Price (optional)"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="flex-1 px-3.5 py-2.5 rounded-lg border border-emerald-900/15 text-sm focus:outline-none focus:border-coral-500"
              min="0"
            />
            <label className="flex items-center gap-2 text-[12.5px] font-semibold text-emerald-900/70 shrink-0">
              <input
                type="checkbox"
                checked={showPrice}
                onChange={(e) => setShowPrice(e.target.checked)}
              />
              Show price
            </label>
          </div>
          <p className="text-[11.5px] text-emerald-900/45 -mt-1">
            Leave price blank, or turn off &quot;Show price&quot;, to display
            &quot;DM for price&quot; instead.
          </p>
        </div>
      </div>

      {error && <p className="text-coral-600 text-[13px] mt-3">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="mt-5 bg-emerald-900 text-paper-100 font-bold text-sm px-6 py-3 rounded-full disabled:opacity-50"
      >
        {saving ? "Posting…" : "Post to shop"}
      </button>
    </form>
  );
}

// ─────────────────────────────────────────────────────────
function ItemRow({ item, onChanged }: { item: Item; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(item.name);
  const [price, setPrice] = useState(item.price?.toString() ?? "");
  const [showPrice, setShowPrice] = useState(item.show_price);

  async function toggleSold() {
    setBusy(true);
    await supabase.from("items").update({ sold: !item.sold }).eq("id", item.id);
    setBusy(false);
    onChanged();
  }

  async function saveEdit() {
    setBusy(true);
    await supabase
      .from("items")
      .update({
        name,
        price: price ? Number(price) : null,
        show_price: showPrice,
      })
      .eq("id", item.id);
    setBusy(false);
    setEditing(false);
    onChanged();
  }

  async function handleDelete() {
    if (!confirm(`Delete "${item.name}"? This can't be undone.`)) return;
    setBusy(true);
    const path = item.image_url.split("/items/")[1];
    if (path) await supabase.storage.from("items").remove([path]);
    await supabase.from("items").delete().eq("id", item.id);
    setBusy(false);
    onChanged();
  }

  return (
    <div className="flex items-center gap-4 bg-white rounded-xl border border-emerald-900/10 p-3">
      <img
        src={item.image_url}
        alt={item.name}
        className={`w-16 h-16 rounded-lg object-cover shrink-0 ${
          item.sold ? "grayscale opacity-50" : ""
        }`}
      />

      {editing ? (
        <div className="flex-1 flex flex-wrap items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-emerald-900/15 text-sm w-40"
          />
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="Price"
            className="px-2.5 py-1.5 rounded-md border border-emerald-900/15 text-sm w-24"
          />
          <label className="flex items-center gap-1.5 text-[12px] font-semibold text-emerald-900/70">
            <input
              type="checkbox"
              checked={showPrice}
              onChange={(e) => setShowPrice(e.target.checked)}
            />
            Show price
          </label>
          <button
            onClick={saveEdit}
            disabled={busy}
            className="bg-emerald-900 text-paper-100 text-[12px] font-bold px-3 py-1.5 rounded-full"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-[12px] font-bold text-emerald-900/50 px-2"
          >
            Cancel
          </button>
        </div>
      ) : (
        <>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm truncate">{item.name}</p>
            <p className="text-[11px] font-bold tracking-wide text-coral-600">
              {item.category.toUpperCase()}
              {"  ·  "}
              {item.show_price && item.price != null
                ? `GH₵${item.price}`
                : "DM for price"}
              {item.sold ? "  ·  SOLD" : ""}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={toggleSold}
              disabled={busy}
              className="text-[12px] font-bold text-emerald-900/70 hover:text-emerald-900 px-2.5 py-1.5 rounded-full bg-emerald-900/8"
            >
              {item.sold ? "Mark available" : "Mark sold"}
            </button>
            <button
              onClick={() => setEditing(true)}
              className="text-[12px] font-bold text-emerald-900/70 hover:text-emerald-900 px-2.5 py-1.5 rounded-full bg-emerald-900/8"
            >
              Edit
            </button>
            <button
              onClick={handleDelete}
              disabled={busy}
              className="text-[12px] font-bold text-coral-600 hover:text-coral-700 px-2.5 py-1.5 rounded-full bg-coral-600/10"
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}
