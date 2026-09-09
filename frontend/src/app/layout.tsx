import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SocialOS — Command Center",
  description: "Enterprise Social Media Command Center & Team Operations System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-canvas text-gray-100 antialiased selection:bg-brandPrimary selection:text-white">
        {children}
      </body>
    </html>
  );
}
