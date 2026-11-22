# Free public demo

[render.yaml](../render.yaml) defines two free Render services: a static site for the frontend and a Docker web service for the API. The site forwards `/api/*` to the API, so the browser sees one origin.

The demo holds **synthetic data only**. Its AI summaries are made on a developer machine and shipped in `data/summaries/` ([ADR-014](decisions/ADR-014-groq-and-shipped-summaries.md)), so Render never holds a model key. Every page needs a sign-in with the account you set below. Never load real patient data and never add a model key to a public instance.

## Deploy

1. Create a [Render](https://dashboard.render.com/register) account with GitHub and allow access to this repository. Stay on the free plan.
2. In the dashboard choose **New**, then **Blueprint**, select this repository and the `main` branch.
3. Check that it lists `ehr-mi-api-7c41` as **Free** and `ehr-mi-demo-7c41` as a static site. Render asks for `SEED_ACCOUNT_EMAIL` and `SEED_ACCOUNT_PASSWORD`: enter the email and password you will sign in with (at least 12 characters). Then apply. Stop if it shows a paid plan.
4. Wait for both deploys. The API image is 2.8 GB, so its first build is slow.
5. Open the API service and compare its URL with the `/api/*` destination in `render.yaml`. Render adds a suffix when a name is taken. If it did, change the destination, push, and sync the Blueprint.
6. Open the static site's URL, sign in with that email and password, search, and open a patient. The API's Swagger docs are at `/docs` on the API URL.

On an existing Blueprint, add the two settings by hand: open `ehr-mi-api-7c41`, then **Environment**, add `SEED_ACCOUNT_EMAIL` and `SEED_ACCOUNT_PASSWORD`, save, and deploy. The free plan resets the API's files at every start, so the account is created again from these settings each time: changing them and deploying changes the login.

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
- Feedback votes and sign-in sessions are lost when the API restarts, so visitors sign in again. The index is built into the image and comes back unchanged.
- After a change to `render.yaml` or the API, deploy both services. The API creates your account at startup when it does not exist yet.
- Rate limits count by the proxy's address, so visitors can share a limit. The forwarded address is not trusted, because a caller could forge it.
- The API is also reachable at its own URL, with the same limits. Its Swagger docs are at `/docs` there (for example `https://ehr-mi-api-7c41.onrender.com/docs`); they list the endpoints, and calls to data routes still need a sign-in.
- Free build minutes and bandwidth are capped each month. Without a payment method Render pauses instead of charging ([limits](https://render.com/docs/free)).
