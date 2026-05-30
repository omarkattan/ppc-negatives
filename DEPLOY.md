# Deploying to GitHub + Render at a sub-path of tools.sandstormdigital.com

The app is one FastAPI service that serves both the JSON API and the frontend, so it deploys as a single Render web service. It is base-path aware, so the same build runs at a domain root or under a sub-path.

## Step 1. Push to GitHub

From the repo root:

```bash
git init
git add .
git commit -m "Negative keyword engine: web app"
git branch -M main
git remote add origin https://github.com/<your-account>/ppc-negative-tool.git
git push -u origin main
```

The repo name is yours to choose. The matching local repo on this machine is `omarkattan/ContentGenerator` style, but keep this one separate since it is a different product.

## Step 2. Create the Render service

Two options.

Blueprint (recommended, reproducible): Render reads `render.yaml`. In Render, New > Blueprint, point at the repo, apply. It provisions the web service with the start command, health check, and env var slots already defined.

Manual: New > Web Service, connect the repo, then set:
- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Plan: Starter or higher. Avoid Free for a client-facing tool: the free tier sleeps after 15 minutes and cold-starts take 30 to 50 seconds, which looks broken to a client clicking a link.

Set these environment variables in the Render dashboard:
- `BASIC_AUTH_USER` and `BASIC_AUTH_PASS`: set both to switch on HTTP basic auth. The tool processes client search-term data, so do not run it open. Leave unset only for a throwaway demo.
- `BASE_PATH`: leave empty for now (root). Set it in Step 4 only if you go the sub-path route.
- `PYTHON_VERSION`: `3.12.3`.

Render gives you a URL like `https://ppc-negative-tool.onrender.com`. Confirm `https://...onrender.com/health` returns `{"status":"ok"}` and the page loads.

## Step 3. Decide: sub-path or subdomain

This is the fork I flagged. Render maps one custom domain to one service at its root and does no path routing, so `tools.sandstormdigital.com/xxx` cannot point at Render by itself.

Subdomain (far simpler). If `xxx.sandstormdigital.com` is acceptable, or `tools.sandstormdigital.com` will host only this tool: in Render add the custom domain to the service, then add the CNAME Render shows you at your DNS provider. Done. Skip Step 4. Leave `BASE_PATH` empty.

Sub-path (what you asked for). Only worth it if `tools.sandstormdigital.com` is, or will become, a landing page hosting several tools each at a path. It needs a reverse proxy in front of the domain. Continue to Step 4.

## Step 4. Sub-path routing (only if you chose the sub-path)

Set `BASE_PATH=/xxx` and `ROOT_PATH=/xxx` in Render and redeploy. The frontend then injects `<base href="/xxx/">` and all API calls resolve under `/xxx/`. The proxy in front must strip the `/xxx` prefix before forwarding to Render, so the app keeps serving its routes at root.

Pick whichever fronting layer already owns `tools.sandstormdigital.com`.

If it is on Cloudflare, a Worker is the clean way:

```js
// Route the Worker on tools.sandstormdigital.com/xxx*
export default {
  async fetch(request) {
    const url = new URL(request.url);
    // strip the /xxx prefix, forward the rest to Render
    const path = url.pathname.replace(/^\/xxx/, "") || "/";
    const target = "https://ppc-negative-tool.onrender.com" + path + url.search;
    const req = new Request(target, request);
    return fetch(req);
  }
}
```

If it is on an Nginx host you control:

```nginx
location /xxx/ {
    proxy_pass https://ppc-negative-tool.onrender.com/;   # trailing slash strips the prefix
    proxy_set_header Host ppc-negative-tool.onrender.com;
    proxy_ssl_server_name on;
    proxy_set_header X-Forwarded-Proto https;
}
# redirect the no-slash form so relative URLs resolve
location = /xxx { return 308 /xxx/; }
```

If it is on Vercel or Netlify, add a rewrite from `/xxx/:path*` to `https://ppc-negative-tool.onrender.com/:path*`.

The single requirement across all three: strip the `/xxx` prefix before the request reaches Render, and keep the trailing-slash redirect so the browser resolves `<base href="/xxx/">` correctly.

## Step 5. Verify

- `tools.sandstormdigital.com/xxx/health` returns ok
- `tools.sandstormdigital.com/xxx/` loads the page, prompts for basic auth, and an upload returns recommendations

## Notes

- Costs: Render Starter is roughly 7 USD per month per service at time of writing; check current pricing.
- Secrets: never commit `BASIC_AUTH_PASS`. It lives only in Render env vars (`sync: false` in the blueprint keeps it out of the repo).
- This is read-only intelligence: it suggests and exports negatives, it does not write to Google Ads. Applying them is a separate connector build, deliberately not wired yet so nothing touches a live account by accident.
