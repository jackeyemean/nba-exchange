import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Navbar } from "@/components/navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hoop Exchange",
  description:
    "A fan simulation stock exchange for basketball players. No real money. Not affiliated with any professional league.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.className} bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100 antialiased`}
      >
        <ThemeProvider>
          <QueryProvider>
            <Navbar />
            <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
            <footer className="border-t border-neutral-200 dark:border-neutral-800 py-6 text-center text-xs text-neutral-500">
              Fan simulation. Not affiliated with any professional league. No
              real monetary value.
            </footer>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
