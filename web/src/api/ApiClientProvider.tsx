import { createContext, type ReactNode, useContext } from "react";
import type { ApiClient } from "./client";

const ApiClientContext = createContext<ApiClient | null>(null);

export interface ApiClientProviderProps {
  readonly client: ApiClient;
  readonly children: ReactNode;
}

export const ApiClientProvider = ({ client, children }: ApiClientProviderProps) => (
  <ApiClientContext.Provider value={client}>{children}</ApiClientContext.Provider>
);

export const useApiClient = (): ApiClient => {
  const client = useContext(ApiClientContext);
  if (client === null) {
    throw new Error("useApiClient must be called inside an ApiClientProvider");
  }
  return client;
};
