import type { ComponentProps, ReactNode } from "react";
import clsx from "clsx";
import { Footer, Header } from "@/components/Header";
import { publicationScope } from "@/lib/publication";
import { PAGE_WIDTHS, type PageWidth } from "@/lib/page-width";

type HeaderProps = Omit<ComponentProps<typeof Header>, "width" | "publicationMode"> &
  Partial<Pick<ComponentProps<typeof Header>, "publicationMode">>;

/**
 * Header + `<main id="main-content">` + Footer at one page width.
 * Pages pass `header` (season, status, …); loading boundaries omit it and get
 * a bare header. `main` accepts className plus aria-* for loading states.
 */
export function PageShell({
  width = "narrow",
  header,
  mainClassName,
  footer = true,
  children,
  ...mainProps
}: {
  width?: PageWidth;
  header?: HeaderProps;
  mainClassName?: string;
  /** Loading boundaries pass false so the footer is not duplicated while streaming. */
  footer?: boolean;
  children: ReactNode;
} & Omit<ComponentProps<"main">, "className" | "children" | "id" | "tabIndex">) {
  const publicationMode = header?.publicationMode ?? publicationScope.mode;
  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={null}
        systemName={null}
        updatedAt={null}
        {...header}
        publicationMode={publicationMode}
        width={width}
        loading={Boolean(mainProps["aria-busy"])}
      />
      <main
        {...mainProps}
        id="main-content"
        tabIndex={-1}
        className={clsx("mx-auto w-full flex-1 px-4", PAGE_WIDTHS[width], mainClassName)}
      >
        {children}
      </main>
      {footer && <Footer publicationMode={publicationMode} width={width} />}
    </div>
  );
}
