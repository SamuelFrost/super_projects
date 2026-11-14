# Desktop application sandboxes

`desktop-sandboxes.json` is a vendored copy of Docker's default seccomp profile
with eight additional syscall rules for Chrome, Cursor, and VS Code terminal sandboxes.
Compose applies it to the devcontainer through
`seccomp=seccomp/desktop-sandboxes.json`, which makes the Compose client read and
inline the profile.

## Source and design context

The base was copied unchanged from
[`moby/profiles`, `seccomp/default.json` at `6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef`](https://github.com/moby/profiles/blob/6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef/seccomp/default.json).
Repository commit `59037fd20b36c5efb7a5af8ea065547733af3d9e` records the import
and its rationale: Docker maintains the profile in a separate repository, and a
custom profile replaces the daemon's built-in profile completely. Keeping the
full default preserves unrelated restrictions, including the AF_ALG socket
block, while making the application-specific exceptions reviewable.

Commit `1fc0bfe502941cab752915007e0f5e333282fb1a` documents Chrome's namespace
requirements and the architecture-specific argument positions used below.

## Added rules and their goals

All eight rules use `SCMP_ACT_ALLOW` and exclude containers that already hold
`CAP_SYS_ADMIN`; those containers retain Docker's broader upstream rules.
The `comment` fields explain the application-specific intent.

| Added rule | Fields and constraints | Goal |
| --- | --- | --- |
| Chrome `clone` | `args[0]`: argument index `0`, mask `235012096` (`0x0E020000`), expected value `0`, `SCMP_CMP_MASKED_EQ`; excludes s390/s390x | Allow user, PID, and network namespaces while rejecting mount, UTS, IPC, and cgroup namespace flags in this rule. |
| Chrome `clone` on s390/s390x | Same mask and comparison, argument index `1`; `includes.arches` selects s390/s390x | Apply the same allowance where the syscall uses a different argument order. |
| Chrome `unshare` | Argument index `0`, mask `235012096` (`0x0E020000`), expected value `0`, `SCMP_CMP_MASKED_EQ` | Allow Chrome's namespace setup while keeping mount, UTS, IPC, and cgroup flags out of this rule. |
| Cursor `unshare` | Argument index `0`, mask `301989888` (`0x12000000`), expected value `268435456` (`CLONE_NEWUSER`), `SCMP_CMP_MASKED_EQ` | Allow mount, UTS, and IPC namespace creation when the same call creates a user namespace; reject cgroup namespace creation. |
| Cursor `mount` | No argument filter; Linux capability checks still apply | Allow the terminal sandbox to remount its isolated filesystem inside its new user/mount namespace. |
| VS Code `clone` | Argument index `0`, mask `301989888` (`0x12000000`), expected value `268435456` (`CLONE_NEWUSER`), `SCMP_CMP_MASKED_EQ`; excludes s390/s390x | Let Bubblewrap create its mount, UTS, IPC, PID, and network namespaces alongside a new user namespace; reject cgroup creation. |
| VS Code `clone` on s390/s390x | Same mask and comparison, argument index `1`; `includes.arches` selects s390/s390x | Apply the same allowance with the architecture's syscall argument order. |
| VS Code `pivot_root`, `umount2` | No argument filter; Linux capability checks still apply | Switch to the sandbox filesystem root and detach setup mounts inside the isolated namespace. |

The container keeps its default capabilities: neither `CAP_SYS_ADMIN` nor
privileged mode is required. Linux denies mounts in the container's user
namespace without the corresponding capability. The sandbox obtains capabilities
inside its own new user namespace. Seccomp cannot inspect the caller's current
namespace, so allowing `mount`, `pivot_root`, and `umount2` increases the available syscall surface without
granting container-wide mount capabilities. No host sysctl or AppArmor policy
changes are configured; additional host restrictions may need separate analysis.

## Applying changes

Recreate the devcontainer after changing this profile. Restarting an application
alone cannot change Docker's seccomp policy.
