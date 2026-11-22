import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@/index.css";
import { AppProviders } from "@/app/AppProviders";
import { createApp } from "@/app/create-app";

const container = document.getElementById("root");
if (container === null) throw new Error("Missing #root element in index.html");

const { router, queryClient } = createApp();
createRoot(container).render(
  <StrictMode>
    <AppProviders router={router} queryClient={queryClient} />
  </StrictMode>,
);
