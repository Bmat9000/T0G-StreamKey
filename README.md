# T0G StreamKey

A standalone Windows 10/11 desktop utility for obtaining authorized TikTok RTMP
credentials through Streamlabs. T0G StreamKey has no T0G sign-in, no backend,
no automatic updates, and remains separate from T0G Nexus and T0G Stream Control.

## What the buttons do

- **Load from Web**: sign in through Streamlabs using the browser callback
  originally implemented by the T0G Stream Control OBS plugin.
- **Save**: securely save **only the current Streamlabs authentication token**
  in **Windows Credential Manager** for this Windows user. It does **not** save
  the RTMP URL, stream key, or your Streamlabs password. Saving is opt-in.
- **Start**: use the connected or restored Streamlabs token to request a TikTok
  LIVE session. If Streamlabs approves it, the app displays the RTMP URL and
  a masked stream key, with **Copy URL** and **Copy Key** buttons. Starting
  creates an actual TikTok LIVE session; it does not automatically transmit from
  OBS. Because the requested UI has no input fields, the title sent to
  Streamlabs is the fixed default "TikTok LIVE" (no game/category or mature flag).
- **Stop**: ask Streamlabs to end the TikTok LIVE session and clear generated
  credentials only after receiving a successful response.
- **Need Help?**: display steps and open the Streamlabs TikTok support guide.
- **Settings → Forget saved Streamlabs token**: delete the saved login and
  disconnect without uninstalling the app.

**On launch**, StreamKey reads a previously saved token from Windows Credential
Manager and checks whether Streamlabs accepts it. If valid, you can click Start
without loading from the web again. If Streamlabs rejects it (HTTP 401/403),
StreamKey deletes the saved token and asks you to use Load from Web and Save
again. Other failures (such as temporary connectivity or LIVE entitlement
issues) **do not silently erase your saved token**. If a start request repeatedly
fails to return valid credentials, reauthenticate using Load from Web, then
press Save to replace the old token.

The two credentials are shown in read-only displays, not editable input fields.
No RTMP credentials are saved by the Save button; they are cleared when Stop
succeeds or StreamKey exits. The clipboard may temporarily hold copied data,
including through Windows clipboard history.

## Streamlabs and TikTok limitations

The integration is adapted from Streamlabs Desktop-specific APIs already used
in T0G Stream Control. These endpoints are **not a documented public API for
third-party apps**, and Streamlabs or TikTok can change or reject the workflow.
A TikTok account must be authorized for LIVE access. No claim is made that
live account authentication or RTMP retrieval has been verified on Windows yet.

See [Streamlabs TikTok help](https://support.streamlabs.com/hc/en-us/articles/49480028480667-How-to-Find-Your-TikTok-Stream-Key).

## Build and test

Windows 10/11 x64, Python 3.12 with Tk, and Inno Setup 6 are required for
packaging. From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\build-windows.ps1
```

The script runs unit tests, produces the app icon, and packages:

- `dist/T0G-StreamKey-Setup.exe`
- `dist/T0G-StreamKey-Portable.exe`

To run from source:

```powershell
py -3.12 -m pip install -e .
py -3.12 run_streamkey.py
py -3.12 -m unittest discover -s tests -v
```

The GitHub Actions tests use mocked Streamlabs APIs, and do not create a real
LIVE stream. Manual Windows acceptance testing and a user-approved TikTok LIVE
account are necessary before release.

## Privacy / behavior

The saved token is stored by Windows Credential Manager under the target
`T0G.StreamKey.StreamlabsToken`. The app does not write any token or key into
plain-text files, GitHub, logs, or servers of its own. The installed and
portable builds share the saved token when run under the same Windows account.
Closing the app does not automatically end an active TikTok LIVE stream: use
Stop first. New versions are downloaded manually from GitHub Releases or Discord.

## License / attribution

The original credential-related T0G Stream Control source files are retained
verbatim in `reference/t0g-stream-control/`. The app uses a Python port of
that API sequence in `streamkey/streamlabs.py`. The copied original project
uses GPL-3.0 (included in `LICENSE.txt`); review license and third-party
notices prior to distribution.

## Windows acceptance checklist

- [ ] Start with no saved token → Load from Web → Save → exit → reopen → restored
- [ ] Check an expired/rejected token clears saved credentials and requests login
- [ ] Verify network failures do not delete saved tokens
- [ ] Start and confirm generated RTMP URL/key copy into OBS
- [ ] Stop and verify the TikTok LIVE session actually ends
- [ ] Verify read-only credential displays, no inputs, and Copy buttons
- [ ] Verify no secrets in logs, application settings, or build artifacts
- [ ] Build and install setup/portable editions on supported Windows versions
