import { permanentRedirect } from "next/navigation";

/** Preserve old bookmarks, including exact source-qualified period identities. */
export default async function RatingsRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(await searchParams)) {
    if (Array.isArray(value)) value.forEach((item) => query.append(name, item));
    else if (value !== undefined) query.set(name, value);
  }
  permanentRedirect(`/teams${query.size ? `?${query.toString()}` : ""}`);
}
