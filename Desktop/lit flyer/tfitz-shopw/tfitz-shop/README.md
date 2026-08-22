# T-FITZ — Online Shop

A tiny, no-monthly-fee website for posting thrift pieces. Public shop
page for customers, plus a private admin page to add / edit / delete
items with photos.

- **Post a new piece** with a photo, name, category, and optional price
- **Mark items sold** or delete them when they're gone
- **"Chat to buy" button** opens WhatsApp with a pre-filled message —
  no WhatsApp API needed
- Fully free to run (Vercel free tier + Supabase free tier)

---

## 1. Create your free Supabase project (database + photo storage)

1. Go to [supabase.com](https://supabase.com) → **Start your project** → sign up (free).
2. **New project** → give it a name (e.g. `tfitz-shop`) → set a database
   password (save it somewhere) → choose the region closest to Ghana
   (e.g. `eu-west` / London) → **Create**. Takes ~2 minutes to spin up.
3. Once it's ready, go to **SQL Editor** (left sidebar) → **New query**.
4. Open `supabase/schema.sql` from this project, copy all of it, paste
   it in, and click **Run**. This creates the items table and the photo
   storage bucket, with the right permissions already set.
5. Go to **Authentication → Users** (left sidebar) → **Add user** →
   create the one admin login (her email + a password she'll remember).
   This is the login she'll use at `/admin` — nobody else can add or
   delete items without it.
6. Go to **Project Settings → API**. You'll need two values from this
   page in step 3 below:
   - **Project URL**
   - **anon / public** key

## 2. Get the code onto GitHub

1. Create a free account at [github.com](https://github.com) if you
   don't have one.
2. Create a **new repository** (e.g. `tfitz-shop`), keep it private if
   you like.
3. Upload this whole folder to that repository (GitHub's website lets
   you drag-and-drop files if you'd rather not use git commands — use
   "uploading an existing file" on the new repo page).

## 3. Deploy on Vercel (free)

1. Go to [vercel.com](https://vercel.com) → sign up with your GitHub
   account (free).
2. **Add New → Project** → pick the `tfitz-shop` repo you just created
   → **Import**.
3. Before clicking deploy, open **Environment Variables** and add:
   - `NEXT_PUBLIC_SUPABASE_URL` → the Project URL from step 1.6
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` → the anon/public key from step 1.6
4. Click **Deploy**. In about a minute you'll get a live link like
   `tfitz-shop.vercel.app`.
5. (Optional) In Vercel → your project → **Settings → Domains**, you
   can add a custom domain later if she buys one — not required.

That's it — it's live, free, and yours.

## 4. Using it day to day

- **Shop page** (share this link with customers): `yoursite.vercel.app`
- **Admin page** (only she should have this): `yoursite.vercel.app/admin`
  — log in with the email/password from step 1.5, then:
  - **Add a piece**: tap the photo box, choose a picture, fill in the
    name and category, optionally a price (or leave "Show price" off
    to display "DM for price" instead), tap **Post to shop**.
  - **Mark sold**: greys the photo out and stops the WhatsApp button —
    good for keeping a piece visible a little longer without selling
    it again by mistake.
  - **Edit**: change the name or price any time.
  - **Delete**: removes it and its photo for good.

## 5. Easy things to customise

Open `lib/config.ts` — everything editable without touching any other
file lives there:
- `WHATSAPP_NUMBER` — the number "Chat to buy" messages go to
- `BRAND` — name, tagline, Instagram/TikTok handles, city
- `CATEGORIES` — the list of categories in the add-item form

## Local development (optional, for further changes)

```
npm install
cp .env.local.example .env.local   # then fill in your Supabase values
npm run dev
```
