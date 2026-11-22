# Free public demo

[render.yaml](../render.yaml) defines two free Render services: a static site for the frontend and a Docker web service for the API. The site forwards `/api/*` to the API, so the browser sees one origin.

The demo holds **synthetic data only** and uses the **offline extractive summarizer**. It has no login. Never load real patient data and never add a model key to a public instance.

## Deploy

1. Create a [Render](https://dashboard.render.com/register) account with GitHub and allow access to this repository. Stay on the free plan.
2. In the dashboard choose **New**, then **Blueprint**, select this repository and the `main` branch.
3. Check that it lists `ehr-mi-api-7c41` as **Free** and `ehr-mi-demo-7c41` as a static site, then apply. Stop if it shows a paid plan.
4. Wait for both deploys. The API image is 2.8 GB, so its first build is slow.
5. Open the API service and compare its URL with the `/api/*` destination in `render.yaml`. Render adds a suffix when a name is taken. If it did, change the destination, push, and sync the Blueprint.
6. Open the static site's URL, search, and open a patient.

Later deploys are started by hand (**Manual Deploy**), after the checks in the README pass.

## What to expect on the free plan

Measured locally on the production image limited to 512 MB and 0.1 CPU. Render itself may differ.

| | Result |
|---|---|
| Wake from sleep | About 3 minutes. The banner says so and the page recovers by itself |
| First search after waking | 2.1 s, slightly over the 2 s target |
| Later uncached searches | 0.4 s median, 0.6 s at most |
| Memory | Runs at the 512 MB limit by reclaiming file cache. No out of memory kill in testing |

- The API sleeps after 15 minutes without traffic. Open the site a few minutes before showing it.
- Feedback votes are lost when the API restarts. The index is built into the image and comes back unchanged.
- Rate limits count by the proxy's address, so visitors can share a limit. The forwarded address is not trusted, because a caller could forge it.
- The API is also reachable at its own URL, with the same limits and no interactive docs.
- Free build minutes and bandwidth are capped each month. Without a payment method Render pauses instead of charging ([limits](https://render.com/docs/free)).
