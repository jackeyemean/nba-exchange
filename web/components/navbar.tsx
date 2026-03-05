"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./theme-provider";
import { useAuth } from "./auth-provider";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const isActive =
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      className={`relative py-3 transition-colors ${
        isActive
          ? "text-neutral-900 dark:text-white font-semibold"
          : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
      }`}
    >
      {children}
      {isActive && (
        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-neutral-900 dark:bg-white rounded-full" />
      )}
    </Link>
  );
}

export function Navbar() {
  const { theme, toggle } = useTheme();
  const { isLoggedIn, username } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-neutral-200 bg-white/80 backdrop-blur-md dark:border-neutral-800 dark:bg-neutral-950/80">
      <nav className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <Link
          href="/"
          className="text-lg font-bold tracking-tight text-neutral-900 dark:text-white"
        >
          Hoop Exchange
        </Link>

        <div className="flex items-center gap-6 text-sm font-medium">
          <NavLink href="/rules">Rules</NavLink>
          <NavLink href="/">Discover</NavLink>
          <NavLink href="/indexes">Indexes</NavLink>
          <NavLink href="/portfolio">Portfolio</NavLink>
          <NavLink href="/leaderboard">Leaderboard</NavLink>
          {isLoggedIn && (
            <>
              <NavLink href="/profile">{username || "Profile"}</NavLink>
              <Link
                href="/logout"
                className="rounded-md px-2 py-1 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                Log out
              </Link>
            </>
          )}
          {!isLoggedIn && (
            <Link
              href="/login"
              className="rounded-md px-3 py-1.5 font-medium transition-colors bg-neutral-900 text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
            >
              Log in
            </Link>
          )}
          <button
            onClick={toggle}
            className="rounded-md p-1.5 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            )}
          </button>
        </div>
      </nav>
    </header>
  );
}
