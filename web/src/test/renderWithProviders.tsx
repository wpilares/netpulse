import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { ApiClientProvider } from "../api/ApiClientProvider";
import type { ApiClient } from "../api/client";
import { createQueryClient } from "../api/queryClient";
import { createFakeApiClient } from "./fakeApiClient";

export interface ProviderOptions {
  readonly apiClient?: ApiClient;
  readonly queryClient?: QueryClient;
}

export interface TestProviders {
  readonly apiClient: ApiClient;
  readonly queryClient: QueryClient;
  readonly wrapper: (props: { readonly children: ReactNode }) => ReactElement;
}

export const createTestProviders = ({
  apiClient = createFakeApiClient(),
  queryClient = createQueryClient({ retry: false }),
}: ProviderOptions = {}): TestProviders => ({
  apiClient,
  queryClient,
  wrapper: ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={apiClient}>{children}</ApiClientProvider>
    </QueryClientProvider>
  ),
});

export const renderWithProviders = (ui: ReactElement, options: ProviderOptions = {}) => {
  const providers = createTestProviders(options);
  return { ...render(ui, { wrapper: providers.wrapper }), ...providers };
};

export interface HookOptions<Props> extends ProviderOptions {
  readonly initialProps?: Props;
}

export const renderHookWithProviders = <Result, Props>(
  hook: (props: Props) => Result,
  { initialProps, ...options }: HookOptions<Props> = {},
) => {
  const providers = createTestProviders(options);
  return {
    ...renderHook(hook, {
      wrapper: providers.wrapper,
      ...(initialProps === undefined ? {} : { initialProps }),
    }),
    ...providers,
  };
};
