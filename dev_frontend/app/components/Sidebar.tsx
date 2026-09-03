"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const NAV: NavItem[] = [
  {
    href: "/",
    label: "Search",
    description: "Find new leads",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0" aria-hidden="true">
        <circle cx="9" cy="9" r="5.25" stroke="currentColor" strokeWidth="1.5" />
        <path d="m13 13 3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/leads",
    label: "Saved leads",
    description: "Leads you kept",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0" aria-hidden="true">
        <path
          d="M4.75 3.75h10.5v12.5l-5.25-3-5.25 3V3.75Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

function isActive(pathname: string, href: string): boolean {
  // "/" must match exactly, or it would light up on every route. Section roots
  // match their children so /sessions/12 keeps "Saved sessions" highlighted.
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="shrink-0 border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950
                 md:sticky md:top-0 md:flex md:h-screen md:w-60 md:flex-col
                 md:border-b-0 md:border-r"
    >
      <div className="flex items-center gap-2 px-5 py-4 md:py-6">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-900 text-xs font-bold text-white dark:bg-zinc-100 dark:text-zinc-900">
          AI
        </span>
        <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Lead Intelligence
        </span>
      </div>

      {/* Horizontal on small screens, vertical from md up — avoids needing a
          hamburger and its open/closed state for only two destinations. */}
      <ul className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible md:pb-0">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="shrink-0 md:shrink">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-zinc-100 font-semibold text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
                    : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
                }`}
              >
                {item.icon}
                <span className="whitespace-nowrap">{item.label}</span>
              </Link>
              <p className="hidden pl-[2.1rem] text-xs text-zinc-400 dark:text-zinc-500 md:block">
                {item.description}
              </p>
            </li>
          );
        })}
      </ul>

      {/* mt-auto keeps this at the bottom of the flex column. It previously
          used absolute positioning and escaped the nav entirely. pb-16 clears
          the Next dev-tools badge that sits in the same corner. */}
      <p className="hidden px-5 pb-16 text-[11px] leading-relaxed text-zinc-400 dark:text-zinc-600 md:mt-auto md:block">
        Leads are kept only when you save them.
      </p>
    </nav>
  );
}
