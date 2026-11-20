import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@/index.css";
import { AppProviders } from "@/app/AppProviders";
import { createQueryClient } from "@/app/queryClient";
import { router } from "@/router";

const container = document.getElementById("root");
if (container === null) throw new Error("Missing #root element in index.html");

createRoot(container).render(
  <StrictMode>
    <AppProviders router={router} queryClient={createQueryClient()} />
  </StrictMode>,
);
