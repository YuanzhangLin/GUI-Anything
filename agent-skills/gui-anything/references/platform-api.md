# Platform API workflow

Use this mode only when the user has a running GUI-Anything backend. Set `GUI_ANYTHING_BASE_URL` to its base URL and obtain `GUI_ANYTHING_TOKEN` through the platform's normal login. Never place the token in answers, logs, map JSON, or generated HTML.

1. `GET /api/map_status/{app_id}` with `Authorization: Bearer <token>` checks whether a map exists.
2. `POST /api/map/{app_id}/generate` with `{"mode":"fast"}` starts deterministic generation. Poll `GET /api/map/tasks/{task_id}` until `success` or `error`.
3. `GET /api/map/{app_id}` returns the map. Save it as JSON if the user wants to inspect it in the standalone viewer (`website/viewer.html`, via its file selector).

Do not use `GET /api/demo/map` as a substitute for a failed real-project analysis. It is a fixed public example.
