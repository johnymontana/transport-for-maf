import type { Metadata } from "next";
import { Provider } from "@/components/ui/provider";

export const metadata: Metadata = {
  title: "TfL Explorer",
  description:
    "A graph-powered conversational agent for London Transport with geospatial visualization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body style={{ margin: 0, padding: 0 }}>
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
