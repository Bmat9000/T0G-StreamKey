# T0G StreamKey

Standalone Windows 10/11 utility for TikTok RTMP credentials, independent of
T0G Nexus and T0G Stream Control. The app has **no T0G account sign-in, no
auto-updater, no backend dependency**, and is distributed manually via GitHub
Releases or Discord.

## TikTok / Streamlabs features

- **Load from Web** opens Streamlabs' browser sign-in (the same Desktop login
  flow used by the T0G Stream Control OBS plugin). The local callback binds
  only to 127.0.0.1 and uses a PKCE verifier. No Streamlabs Desktop installation
  is required for this option.
- **Load from PC** is optional and explicitly scans the signed-in user's own
  Streamlabs Desktop LevelDB log for its token, matching Stream Control's
  Windows loader. No background scanning takes place.
- **Refresh** reads the TikTok username, application status, and LIVE eligibility
  from Streamlabs.
- **Start LIVE / Get Key** calls Streamlabs' TikTok stream-start operation,
  setting the title, optional game/category, and mature audience flag. This
  **creates a real TikTok LIVE session**, and if approved, Streamlabs returns
  an RTMP server and stream key for copying into OBS or other broadcasting
  software. It does **not** automatically start OBS transmission.
- **End TikTok LIVE** calls the corresponding API to end the session. It clears
  the local key fields on successful confirmation.
- Manual entry and copying of already-authorized RTMP credentials still works
  without any login or network connection.

**Eligibility and compatibility:** A TikTok account must be eligible for LIVE
access. These Streamlabs Desktop-specific endpoints and their browser login
are **not a documented, officially supported third-party Streamlabs API**.
They may change, reject the standalone application, or be subject to provider
restrictions. Importing the code does not imply Streamlabs/TikTok approval, and
successful live credential retrieval still requires real-account testing.
See [Streamlabs' TikTok guide](https://support.streamlabs.com/hc/en-us/articles/49480028480667-How-to-Find-Your-TikTok-Stream-Key).

## Privacy and lifecycle

- Tokens and streaming credentials remain in process memory, not in application
  settings files, logs, a T0G server, or GitHub. Browser sign-in is managed by
  Streamlabs and the user's browser.
- Keys are masked by default. Copying a key puts it on the system clipboard;
  Windows clipboard history and clipboard managers can independently retain it.
  Clear credentials removes the clipboard contents only when still owned by
  StreamKey.
- Closing the app does **not** end a TikTok LIVE session automatically.
  Use **End TikTok LIVE** first if you want to stop the session.
- The app has no automatic update checks or user analytics.

## Build on Windows

Install 64-bit Python 3.12 with Tk support and Inno Setup 6. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\build-windows.ps1
```

This installs the build-only requirements, runs unit tests, generates the icon,
packages PyInstaller's installer payload and portable EXE, and creates:

- `dist/T0G-StreamKey-Setup.exe`
- `dist/T0G-StreamKey-Portable.exe`

To run from source:

```powershell
py -3.12 -m pip install -e .
py -3.12 run_streamkey.py
py -3.12 -m unittest discover -s tests -v
```

Builds and tests on Windows 10/11, and a real Streamlabs LIVE account, still
need to be completed before any published release.

## Source provenance and license

The exact original Stream Control files relevant to TikTok credentials and
session management are in `reference/t0g-stream-control/`: the OBS C++ TikTok
service, the OBS Windows credential store, and the legacy Python
`TokenRetriever.py` / `Stream.py`. The standalone runnable port is in
`streamkey/streamlabs.py`; original OBS C++ files are **not** built into the
Windows utility. The original project's GPL-3.0 license text is included in
`LICENSE.txt` for its copied code. Review all applicable third-party notices
before distribution.

## Release

Run the Windows build and acceptance checklist, test an eligible TikTok
account, then create a **manual** GitHub release with the two executables and
SHA-256 hashes. This repository has no auto-update service. End users obtain
new versions from GitHub or Discord.

## Windows acceptance checklist

- [ ] Run installer, portable edition, and uninstall as a standard user
- [ ] Verify manual RTMPS URL/key entry, masking, copy, clear, and relaunch
- [ ] Load from Web on an approved Streamlabs account without installing Desktop
- [ ] Refresh account and verify username and LIVE permission status
- [ ] Start LIVE and copy the returned URL/key into OBS
- [ ] End LIVE and verify TikTok confirms the session ended
- [ ] Try a rejected/expired login, canceled browser login, and unauthorized account
- [ ] Verify no token/key written to disk or app logs and no updater is running
