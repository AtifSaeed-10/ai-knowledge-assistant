import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ 
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jakarta"
});

export const metadata: Metadata = {
  title: "DocuSage | Premium AI PDF Assistant",
  description: "Upload PDFs and have intelligent, cited conversations with your documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${jakarta.variable} font-sans bg-brand-app text-foreground min-h-screen flex`}>
        {children}
      </body>
    </html>
  );
}