# KasmVNC dependency hardening (in progress)

These patches target KasmVNC v1.5.2, commit
`b3ab9ac88e5283e986c65236cf0ed7462ec1505e`. Apply them in filename order.
They are preparation for replacing the upstream Debian packages; the Dockerfile
still installs the original packages, so these patches currently change no runtime behavior.

The first patch uses the socket peer for authentication throttling, ignoring
client-supplied forwarded-address headers. Clients behind a proxy share that
proxy's throttling identity. The second removes HTTP directory enumeration while
preserving the existing root index rewrite and static-file handler. It removes
the directory-listing HTML interpolation, allocation leak, and unchecked scandir
failure path rather than leaving unused vulnerable code behind.

## Required before enabling the source build

- Pin builder images by digest and every downloaded archive by SHA-256. Eliminate
  certificate-check bypasses and the X.Org HTTP fallback.
- Pin libyuv by commit. Review and commit the web-client npm lockfile; build with
  `npm ci` and disabled lifecycle scripts, explicitly invoking reviewed build steps.
- Compare embedded X.Org 21.1.12 against later official security fixes and backport
  every applicable fix. Record evidence for any exclusions.
- Inventory static and dynamic dependencies, check current advisories, and produce
  an SBOM and exact build-input manifest for each architecture.
- Add a Docker builder stage producing the Debian package; install only the
  package in the runtime stage. Never silently fall back to upstream binaries.
- Exercise authentication throttling with changing forwarded headers, directory
  requests, static assets, malformed handshakes, and applicable X.Org regressions.
- Build amd64 and arm64 and inspect PIE, NX, full RELRO, and stack protection.
- Recreate the nested target container and verify desktop startup, reconnect,
  resizing, clipboard, logout/restart, and browser automation.

## Validation status

The patches apply in sequence to the pinned source. Compilation, behavioral
regressions, dependency resolution, and image builds have not been completed.
The development container's root filesystem was full during preparation. Do not
merge this work as completed security remediation until the gates above pass.

Future updates must rebase each patch explicitly, rerun its regression coverage,
refresh the dependency manifest and SBOM, and retire patches only after verifying
the replacement upstream release contains the corresponding fix.
