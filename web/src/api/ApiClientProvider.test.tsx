import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createFakeApiClient } from "../test/fakeApiClient";
import { ApiClientProvider, useApiClient } from "./ApiClientProvider";

describe("useApiClient", () => {
  it("returns the client provided by the nearest ApiClientProvider", () => {
    const client = createFakeApiClient();
    const wrapper = ({ children }: { readonly children: ReactNode }) => (
      <ApiClientProvider client={client}>{children}</ApiClientProvider>
    );

    const { result } = renderHook(() => useApiClient(), { wrapper });

    expect(result.current).toBe(client);
  });

  it("fails loudly outside a provider", () => {
    expect(() => renderHook(() => useApiClient())).toThrow(/ApiClientProvider/);
  });
});
