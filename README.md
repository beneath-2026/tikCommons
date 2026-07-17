# commons

The shared **[Tik Manager 4](https://github.com/masqu3rad3/tik_manager4) commons folder** of
the *beneath* student film pipeline: one folder on the studio share that every artist
machine points at, holding the user roster, project structure templates, metadata defaults —
and all of our custom publish/validation plugins per DCC.

## Structure

| Path | What it is |
|---|---|
| `*.example.json` | Deployment configs — **copy each to `<name>.json` and fill in the placeholders** (the real files are git-ignored). |
| `metadata.json` | Default per-project metadata schema (fps, resolution, frame ranges, …). |
| `structures.json` | Project folder-structure templates. |
| `preview_settings.json` / `project_settings.json` | Playblast/preview + project defaults. |
| `plugins/blender/` | RenderPal submission, Alembic/FBX export, publish-collections, render-settings validation, Discord publish notification. |
| `plugins/houdini/` | USD ROP extract/validation, Alembic + USD geo ingest. |
| `plugins/nuke/` | RenderPal submitter and a multi-write batch submitter. |
| `plugins/standalone/` | Standalone publish tool + path tool hook. |
| `_templates/` | Blender asset/shot template scenes. |

## Setup

1. Clone this repo and **make sure the folder is named `commons`** — Tik Manager expects
   that exact folder name (the GitHub repo is called `tikCommons` only because the name
   alone would be ambiguous):
   ```bash
   git clone https://github.com/beneath-2026/tikCommons.git commons
   ```
   Put it on a share all machines can reach and select it as the **commons directory**
   when Tik Manager asks on first launch.
2. Copy every `*.example.json` to its real name (e.g. `additional_config.example.json` →
   `additional_config.json`) and fill in the placeholders (`X:\path\to\...`,
   `your-kitsu-server`, `your_project_name`).
   - `users.json` ships with Tik's four default users (password `1234`) — add your own
     users and change the passwords.
   - `additional_config.json` — vendor folder for python deps, project name, optional
     Discord webhook for publish notifications, render output roots.
   - `management_settings.json` — your Kitsu URL; `commons_id` is written by Tik Manager.
3. **Render farm credentials are read from the environment** — the RenderPal submitters
   expect `RP_USER`, `RP_PASSWORD` and `RP_SERVER` (see the
   [pipeline-launchers](https://github.com/beneath-2026/pipeline-launchers) repo, which
   sets them at app startup). Nothing secret lives in this folder.

## Dependencies

- [Tik Manager 4](https://github.com/masqu3rad3/tik_manager4) (the plugins subclass its
  `ExtractCore` / `ExtensionCore`).
- [gazu](https://github.com/cgwire/gazu) for the Kitsu-connected plugins, PySide6 for the
  standalone tools — installed into the vendor folder that `additional_config.json` points at.
- RenderPal V2 command-line client (`rprccmd`) for the farm submitters.
