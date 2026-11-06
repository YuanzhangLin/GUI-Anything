# Local setup

GUI-Anything runs its Web UI, backend, OpenCode and Android tools on the same machine. Open **Management Console → Local environment** first. The page exposes the same report as `GET /api/environment/diagnostics`, so a user or another coding agent can inspect every detected path and repair hint.

## OpenCode

GUI-Anything first uses a compatible `OPENCODE_BIN` or `opencode` already on `PATH`. It does not replace that installation. If none is found, an administrator can select **Install managed version**. The backend installs the pinned `opencode-ai@1.19.5` package under `~/.gui-anything/tools/opencode/1.19.5`; it does not modify the global npm prefix or `PATH`.

The managed install needs Node.js and npm. For a manual installation, use `npm install -g opencode-ai@1.19.5`, then verify `opencode --version`. OpenCode documents its CLI installation and its `serve` command at [OpenCode installation](https://opencode.ai/docs/) and [OpenCode server](https://opencode.ai/docs/server/).

Model credentials are configured in **Management Console → Model service**. Fast Map and source browsing do not need a model. Full Map and Agent operations send project material to the selected provider and may incur provider charges; review the provider, model and material summary before starting them.

## Android SDK and virtual devices

Install Android SDK Platform-Tools, Android Emulator, Android SDK Command-line Tools (latest), and at least one supported x86_64 or arm64-v8a system image. Set `ANDROID_SDK_ROOT` when the SDK is outside the default location.

The environment page can list installed and available system images, create an AVD, install a missing image, start or normally stop a GUI-Anything-managed emulator, and expose separate actions for clearing data and deleting the AVD. It will not close an emulator started by another program.

Windows is supported directly with the Android SDK installed by Android Studio or the command-line tools. Hardware virtualization must be enabled in UEFI/BIOS. macOS and Linux use the same SDK packages; ensure the current user can execute the SDK tools. On Linux, configure KVM access. Apple silicon requires an arm64 system image.

## Common failures

- **OpenCode missing:** use the managed install button or set `OPENCODE_BIN` to a compatible executable.
- **npm missing:** install a current Node.js release, reopen the backend, and rerun diagnostics.
- **ADB missing:** install Platform-Tools and set `ANDROID_SDK_ROOT`.
- **No images shown:** install Command-line Tools (latest) so `sdkmanager` is available.
- **Emulator starts but stays offline:** wait for Android boot, then inspect `adb devices -l`; restart only the affected AVD.
- **Port already in use:** stop the process occupying the configured local port before starting the paired services.
- **Insufficient resources:** keep at least 12 GiB free disk space and 8 GiB physical memory; running two AVDs may require more.

The paired launcher is `python -m app.local_services` from `backend/`. It generates temporary local service credentials, registers the GUI observe/action/verification tools, starts OpenCode and the backend together, verifies the OpenCode API and tool registration, and stops the other process if either service exits.
