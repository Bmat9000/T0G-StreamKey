# T0G StreamKey

T0G StreamKey is a standalone Windows utility for copying TikTok RTMP credentials into OBS, T0G Nexus, or another broadcaster. Version 0.1.0 supports manual entry of an RTMP server URL and stream key already issued by TikTok. It opens directly to the credential screen and keeps credentials in memory.

## Install and use

- **Installer**. Download `T0G-StreamKey-Setup.exe` from the project's GitHub Releases page or the T0G Discord. Run Setup to install for the current Windows user. The Start menu shortcut is included, and Setup offers a desktop shortcut. Uninstall from **Settings → Apps**.
- **Portable**. Download `T0G-StreamKey-Portable.exe` from the same sources and run it directly. The bundle unpacks its runtime into a temporary folder while running. It has no persistent application profile. The installed edition also has no persistent profile.
- **Credentials**. Use the Streamlabs guide link for eligibility information. If your TikTok account has RTMP access, obtain the URL and key through TikTok's authorized interface. Paste both, select **Use credentials**, and copy them individually. To replace an expired pair, paste the new values and select **Use credentials** again.
- **Privacy**. The app masks the key by default and clears the in-memory fields on exit. Windows clipboard history and clipboard managers can retain copies independently of the app. **Clear saved session** and **Clear local application data** clear in-memory credentials. Browser sign-in is managed in the browser.

TikTok verifies keys when broadcasting. The utility checks only the format. Streamlabs' native TikTok integration can allow going live without granting a transferable RTMP key. [Streamlabs guide](https://support.streamlabs.com/hc/en-us/articles/49480028480667-How-to-Find-Your-TikTok-Stream-Key)

## Build on Windows

Use Windows 10 or 11 with x64 Python 3.12 (including Tcl/Tk), the Python launcher, and Inno Setup 6. Run from the repository root in PowerShell.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\build-windows.ps1
```

The script installs the build-only dependency into `.venv`, runs the automated tests, and packages both editions in `dist`. If Inno Setup is installed elsewhere, pass `-InnoCompiler` with the path to `ISCC.exe`. End users receive the bundled runtime.

Run the application from source and run the tests with Python 3.12 and Tk installed.

```powershell
py -3.12 run_streamkey.py
py -3.12 -m unittest discover -s tests -v
```

## Manual release

1. Confirm the project's license and add the approved `LICENSE` file. Review the notices for the bundled Python and Tcl/Tk distributions and PyInstaller.
2. Set the intended version in `pyproject.toml`, build both executables, and complete the Windows checklist below on Windows 10 and 11. Sign the files if a signing certificate is available. Recompute SHA-256 hashes after signing.
3. Create a draft GitHub release for a `v<version>` tag on the tested commit. Attach both executables and their SHA-256 hashes. Describe manual credential entry and Windows architecture support in the release notes.
4. After release approval, publish on GitHub Releases and share the release or approved executable in the T0G Discord. Users install new versions manually.

## Streamlabs integration review

The Nexus and T0G Stream Control OBS plugins use a Streamlabs Desktop browser sign-in and loopback callback, exchange the code through a Desktop-specific auth API, then call Desktop TikTok account and stream APIs with a bearer token. The stream-start operation creates a TikTok LIVE session and returns `rtmp`, `key`, and a stream ID for the separate end operation. The C++ service also defines a helper for reading tokens from Streamlabs Desktop's local LevelDB. Stream Control's Python tools use the same Desktop API family through a browser callback and HTTP client. [Nexus native service](https://github.com/Bmat9000/T0G-Nexus-2.0/blob/main/obs-plugin/src/tiktok-service.cpp) · [Stream Control auth](https://github.com/Bmat9000/T0G-Stream-Control/blob/main/TokenRetriever.py) · [Stream Control stream service](https://github.com/Bmat9000/T0G-Stream-Control/blob/main/Stream.py)

The public Streamlabs developer scopes do not document third-party TikTok key retrieval. Automatic retrieval, refresh, and provider session status require Streamlabs to confirm an approved app registration, authorization flow, credential endpoint, and LIVE session lifecycle. The standalone app reimplements only the generic URL/key handling. Its Python/Tk interface, validator, and OS clipboard run locally. The only browser launch is the user-selected support link, with no credentials attached. [Streamlabs developer scopes](https://dev.streamlabs.com/docs/scopes)

## Verification

Automated tests exercise format validation, redacted credential representation, copy actions, invalidation when editing, key masking, clearing, and shutdown. Window-action tests mock the OS clipboard and Tk widgets.

| Windows acceptance check | Status |
| --- | --- |
| Install as a standard user, first launch directly to credentials, Start menu shortcut and optional desktop shortcut | Pending |
| Paste a sample RTMPS URL/key, apply, show/hide, copy both values to a test editor, replace them, clear, and relaunch | Pending |
| Clear session and application data, verify unrelated clipboard content survives | Pending |
| Run portable as a standard user alongside installed edition, verify state isolation, uninstall installed edition | Pending |
| Disconnect network, launch and use local controls, observe processes and network activity to verify no update checks or background updater | Pending |
| Streamlabs sign-in, live credential retrieval, automatic refresh, expired sessions and provider rejection | Requires an approved integration and an eligible account |

T0G StreamKey is an independent utility. Streamlabs and TikTok are third-party services.
