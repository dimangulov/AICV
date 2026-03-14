import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Damir Imangulov — Interactive Digital Twin CV",
  description:
    "Principal Architect with 15+ years experience. Ask my AI digital twin anything about my background, projects, and technical expertise.",
  openGraph: {
    title: "Damir Imangulov — Interactive Digital Twin CV",
    description:
      "Principal Architect with 15+ years experience. Ask my AI digital twin anything.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="bg-gray-950 text-gray-100 antialiased">{children}</body>
    </html>
  );
}
