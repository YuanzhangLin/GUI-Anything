# Project website

This is the static GitHub Pages website for GUI-Anything. It is published from the existing repository through `.github/workflows/pages.yml`. `website/demo.json` is a copy of `backend/data/demo.json`; the workflow verifies that they match. The map comes from a real Fast scan of Activity Diary source at commit `71254d4`; the website shows a readable subset of the 13 screens and 20 paths, with static UI element candidates and three Activity-to-Fragment hosting relations in page details. The site does not host the API, APKs, source files, decompiled files, or conversation data.

## Preview locally

From the repository root, run:

```bash
python -m http.server 8765 --directory website
```

Open `http://localhost:8765/` in your browser. Stop the server with `Ctrl+C`. Open through HTTP rather than double-clicking `index.html`, because the interactive map loads `demo.json` with `fetch`. If the platform Demo changes, copy `backend/data/demo.json` to `website/demo.json` before publishing.

Open `http://localhost:8765/viewer.html` for the full map review workspace. It loads the Demo automatically, accepts any schema-v2 Map JSON through the file picker, and can load a hosted map with `?map=relative-path.json`. Review states and notes stay in that browser until exported; they do not modify the source map. The skill CLI also generates a standalone HTML file with the map embedded, which opens directly without this server.

The viewer can also import a runtime `trace.json` from the navigation Skill, or load a hosted trace with `?map=map.json&trace=trace.json`. It marks verified and mismatched paths and shows the observed page beside the static prediction. Trace assets (UI XML and screenshots) remain in the local sibling directory named after the trace file; the generated standalone `trace.html` embeds screenshots for immediate replay.

## Publish

Push this website, the Pages workflow, and `backend/data/demo.json` to `master` (or `main`). In the repository's **Settings → Pages**, select **GitHub Actions** as the build and deployment source. The default URL is `https://yuanzhanglin.github.io/GUI-Anything/`.
After changing the Pages source, re-run the website workflow or push a change under `website/` to start a fresh deployment.

## Custom domain later

After buying a domain, enter it in **Settings → Pages → Custom domain** and configure the DNS records exactly as [GitHub documents](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site). Do not create a `CNAME` file with a placeholder domain. Verify HTTPS after DNS resolves. The site uses relative asset URLs, so the same files work under the default project URL and a custom domain.

## Curated coverage case

The `#coverage-case` section describes one Agent-assisted OmniNotes merge experiment. It publishes only the reviewed narrative and aggregate results, not raw coverage, traces, screenshots, APKs, databases or the local harness. Keep its wording distinct from the static Activity Diary map and from capabilities of the shipped navigation runner.
