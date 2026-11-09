import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ThemeProvider } from "@/app/theme-provider";
import { EvidenceDrawerProvider } from "@/components/shared/EvidenceDrawerContext";
import { Toaster } from "@/components/ui/sonner";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <EvidenceDrawerProvider>
          {children}
          <Toaster position="bottom-right" closeButton />
        </EvidenceDrawerProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
