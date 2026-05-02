import type { Metadata } from "next";
import { IBM_Plex_Mono, M_PLUS_1p } from "next/font/google";
import "bootstrap/dist/css/bootstrap.min.css";
import "./globals.css";

const bodyFont = M_PLUS_1p({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const monoFont = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "松戸置き場用資材管理表",
  description: "資材の現在庫、入出庫ログ、Excel出力、共有、通知設定をまとめて管理するアプリ",
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className={`${bodyFont.variable} ${monoFont.variable}`}>
      <body>{children}</body>
    </html>
  );
}
