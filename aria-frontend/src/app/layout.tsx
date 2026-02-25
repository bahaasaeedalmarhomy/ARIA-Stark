import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ViewportWarning } from "@/components/ui/viewport-warning";
import { FirebaseAuthProvider } from "@/components/providers/firebase-auth-provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ARIA — AI Browser Automation",
  description: "ARIA: AI-powered browser automation agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark`}>
      <body className="antialiased">
        {/* FirebaseAuthProvider silently authenticates the user on page load */}
        <FirebaseAuthProvider />
        <ViewportWarning />
        {children}
      </body>
    </html>
  );
}
