import { QueryClient } from "@tanstack/react-query";

export interface QueryClientOptions {
  readonly retry?: number | boolean;
}

const DEFAULT_RETRY = 1;

export const createQueryClient = ({ retry = DEFAULT_RETRY }: QueryClientOptions = {}): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: { retry, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
