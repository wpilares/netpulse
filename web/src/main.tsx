import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ApiClientProvider } from "./api/ApiClientProvider";
import { createApiClient } from "./api/client";
import { createQueryClient } from "./api/queryClient";
import { ThemeProvider } from "./theme/ThemeProvider";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles.css";

const container = document.getElementById("root");

if (container === null) {
  throw new Error("Root element #root is missing from index.html");
}

const apiClient = createApiClient();
const queryClient = createQueryClient();

createRoot(container).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={apiClient}>
          <App />
        </ApiClientProvider>
        {import.meta.env.DEV ? <ReactQueryDevtools initialIsOpen={false} /> : null}
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
