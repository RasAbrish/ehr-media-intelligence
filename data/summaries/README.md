# Shipped model summaries

`summaries.json` holds AI summaries of the synthetic patients, made on a developer machine with
`ehr-mip summaries export` (ADR-014). The API image imports them while it builds, so the public
demo shows model summaries without holding a model key. A summary is only used while its
patient's data is unchanged; otherwise the offline summary is shown.

Regenerate after a data or prompt change: set `GROQ_API_KEY` (or `ANTHROPIC_API_KEY`) in `.env`,
run `make pipeline`, then `cd backend && uv run ehr-mip summaries export`.
