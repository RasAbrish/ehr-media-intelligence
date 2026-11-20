/**
 * Every user-facing string lives here (docs/06-UI-DESIGN.md section 14).
 * Sentence case, short, neutral. No exclamation marks.
 */
export const copy = {
  product: "Media Intelligence",
  skipLink: "Skip to content",
  nav: {
    label: "Primary",
    menu: "Open navigation menu",
    search: "Search",
    patients: "Patients",
    quality: "Data quality",
  },
  theme: {
    trigger: "Change theme",
    label: "Theme",
    light: "Light",
    dark: "Dark",
    system: "System",
  },
  search: {
    pageLabel: "Search patient records",
    idleTitle: "Search across every patient record",
    idleBody: "Find notes, imaging and lab reports by meaning, not just keywords.",
  },
  patients: {
    title: "Patients",
    body: "Every patient in the current dataset, with identity and record counts.",
  },
  quality: {
    title: "Data quality",
    body: "Ingestion statistics, validation issues, the audit log and quarantined records.",
  },
  indexEmpty: {
    title: "No records indexed yet",
    before: "Run",
    command: "make pipeline",
    after: ", then reload.",
  },
  notFound: {
    title: "Page not found",
    body: "This address doesn't match a page in the app.",
    action: "Go to search",
  },
} as const;
