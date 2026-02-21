# How To Push Updates (GitHub + Manual XML)

This guide explains how to ship a new Pypad update using:
- GitHub Releases (installer hosting)
- Manual edit of `notepad.xml` (update feed)

## 1. Prepare Version

1. Pick next version (example: `1.6.9-prerelease`).
2. Update `assets/version.txt` to that version text.
3. Update `CHANGELOG.md` with a new section for that version/date.

## 2. Build App + Installer

From repo root:

```bat
compile.bat
build_installer.bat
```

Expected installer output:

```text
dist\installer\NotepadClone-Setup-<version>.exe
```

## 3. Create GitHub Release

1. Push your code changes to GitHub.
2. Open your repo on GitHub.
3. Go to **Releases** -> **Draft a new release**.
4. Create/select tag for the new version.
5. Set release title (example: `Pypad 1.6.9-prerelease`).
6. Paste release notes (from `CHANGELOG.md`).
7. Upload installer EXE (`dist\installer\...exe`) as release asset.
8. Publish release.

## 4. Copy Direct Download URL

After publishing, copy the asset URL. It should look like:

```text
https://github.com/<owner>/<repo>/releases/download/<tag-or-id>/NotepadClone-Setup-<version>.exe
```

## 5. Manually Edit `notepad.xml`

Edit `notepad.xml` (or your hosted feed file) and update:
- `<title>`
- `<version>`
- `<pubDate>` (YYYY-MM-DD)
- `<description>` bullets
- `<enclosure url="...">` with the GitHub release asset URL

Template:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<updates>
  <item>
    <title>Pypad 1.6.9-prerelease</title>
    <version>1.6.9</version>
    <pubDate>2026-02-18</pubDate>
    <description>
      - Short bullet 1
      - Short bullet 2
      - Short bullet 3
    </description>
    <enclosure
      url="https://github.com/<owner>/<repo>/releases/download/<tag-or-id>/NotepadClone-Setup-1.6.9-prerelease.exe"
      type="application/octet-stream" />
  </item>
</updates>
```

Important:
- Keep XML valid.
- Keep `<version>` numerically higher than currently installed version.
- If app is `1.6.6`, feed must be `1.6.7` or higher to trigger update.

## 6. Push Feed File

Commit and push XML update:

```bat
git add notepad.xml CHANGELOG.md assets/version.txt
git commit -m "release: 1.6.9-prerelease update feed"
git push
```

If your app reads a different hosted feed file, update/push that file in the feed repo/branch.

## 7. Verify Feed URL

Open your configured update feed URL in browser and confirm:
- It is reachable (HTTP 200)
- It contains latest version and correct installer URL

Default feed currently used by app:

```text
https://raw.githubusercontent.com/ne0gl1tch20/neogl1tch20server/refs/heads/main/updates/notepad.xml
```

## 8. Verify In App

1. Launch app.
2. `Help` -> `Check for Updates`.
3. Confirm behavior:
   - If newer version exists: `Update Available` dialog appears.
   - If equal/older: `App Is Up To Date`.
   - If issue: open `Help` -> `Show Debug Logs` and inspect `[Updater]` lines.

## Quick Troubleshooting

- No update shown:
  - Feed version is not higher than current app version.
  - Feed URL points to wrong file.
- Slow/timeout:
  - Network/proxy issue to `raw.githubusercontent.com`.
- Download fails:
  - Release asset URL is wrong or private.

