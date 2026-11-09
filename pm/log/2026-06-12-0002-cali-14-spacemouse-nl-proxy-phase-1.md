### 2026-06-12 · CALI-14 · SpaceMouse NL-Proxy (driver coexistence) — phase 1
- WebHID needs the user to quit 3DxWare (raw HID can't be shared — confirmed on Theo's SpaceMouse
  Compact `256f:c635`: "Failed to open the device" while the driver holds it). CALI-14 adds a *driver*
  path that coexists with Fusion.
- Researched the integration: NL-Proxy at `https://127.51.68.120:8181/3dconnexion/nlproxy`, WAMP/WSS,
  a driver-installed cert, and 3Dconnexion's `_3Dconnexion` lib driving the camera via navlib callbacks.
- Phase 1 shipped: UI mode toggle (WebHID | Driver/NL-Proxy beta); driver mode loads the proxy lib,
  instantiates `_3Dconnexion`, attempts connect, and reports the API surface + errors on-screen (cert
  hint included). Verified the graceful-failure path in the preview (no driver → clear error, no crash).
  Cannot verify the happy path here — needs Theo's hardware + 3DxWare; phase 2 (camera nav) follows the
  on-screen telemetry. 71 passed.
- Commit: 9420ca8
