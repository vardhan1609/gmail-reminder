import "./globals.css";
import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/providers/theme-provider";

export const metadata: Metadata = {
  title: "Gmail to WhatsApp & Telegram Alert System",
  description: "Secure multi-user email processing and multi-channel notification application.",
};

const antiFoucScript = `
(function() {
  try {
    var stored = localStorage.getItem('theme_preference');
    var isDark = stored === 'dark' || (!stored || stored === 'system') && window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: antiFoucScript }} />
      </head>
      <body className="bg-background text-foreground font-sans antialiased min-h-screen selection:bg-primary/20">
        <AuthProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
