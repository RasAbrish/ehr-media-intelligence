import { copy } from "@/lib/copy";

const WIDTHS = [960, 1440, 2400] as const;
const srcset = (format: string) =>
  WIDTHS.map((width) => `/signin/corridor-${String(width)}.${format} ${String(width)}w`).join(", ");
const SIZES = "(min-width: 64rem) 50vw, 100vw";

/** Decorative photo half (docs/06 section 6.1a; source and license in docs/ASSETS.md). */
export function SignInPhoto() {
  return (
    <div className="relative h-40 overflow-hidden bg-muted lg:h-auto lg:min-h-dvh">
      <picture>
        <source type="image/avif" srcSet={srcset("avif")} sizes={SIZES} />
        <source type="image/webp" srcSet={srcset("webp")} sizes={SIZES} />
        <img
          src="/signin/corridor-1440.jpg"
          srcSet={srcset("jpg")}
          sizes={SIZES}
          alt=""
          width={2400}
          height={1799}
          fetchPriority="high"
          decoding="async"
          className="absolute inset-0 size-full object-cover"
        />
      </picture>
      {/* A teal wash ties the photo to the palette; the scrim keeps the caption readable. */}
      <div aria-hidden className="absolute inset-0 bg-primary/25 mix-blend-multiply" />
      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2 bg-linear-to-t from-scrim to-transparent px-6 pt-16 pb-5 text-on-scrim lg:px-10 lg:pb-10">
        {/* Not a link: every page leads back here until the user signs in. */}
        <p className="flex items-center gap-2 text-heading">
          <span aria-hidden="true" className="size-3.5 rounded-sm bg-primary" />
          {copy.product}
        </p>
        <p className="max-w-md text-body text-on-scrim/90 max-lg:hidden">{copy.auth.tagline}</p>
      </div>
    </div>
  );
}
