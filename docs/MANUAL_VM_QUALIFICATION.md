# Manual native qualification after runner retirement

GitHub Actions runs automated checks on GitHub-hosted virtual machines. There
is no GitHub self-hosted runner for this repository. The former `run_vm_e2e`
and `extended_qualification` workflow inputs and their remote jobs are retired.
Native qualification remains a separate, explicit maintainer operation; passing
the automated workflow does not claim native desktop or physical qualification.

## Trusted source handoff

1. Review the complete source and dependency changes at an exact 40-character
   commit. A pull request approval or a branch name alone is not a source pin.
2. Confirm that the commit resolves locally, then export it with Git's data-only
   archive command. Do not run repository build/install/test commands on the
   workstation as part of this handoff.

   ```bash
   commit=<reviewed-40-character-commit>
   test "$(git rev-parse --verify "${commit}^{commit}")" = "$commit"
   git archive --format=tar "$commit" > ../native-qualification-source.tar
   sha256sum ../native-qualification-source.tar
   ```

3. Transfer the archive to a disposable Fedora KDE guest through the separately
   maintained infrastructure helper. Build and test inside the guest. Do not
   expose a host home directory, SSH agent, desktop socket, container socket, or
   personal credential to the guest. Use a fresh overlay for every qualification.
4. Record the source commit, archive digest, guest image identity, actual QEMU
   CPU/memory limits, desktop session, command, result, and report paths. Copy
   only the reviewed evidence back to the workstation.
5. A missing guest, tool, resource budget, or report is **pending**, not passed.
   Do not register a runner to make a pending qualification execute automatically.

## Existing native test implementation

[The existing VM test guide](E2E_VM_TESTS.md) describes the preserved legacy
`e2e.vm` implementation and its commands. That implementation currently builds
an RPM on its invoking machine and uses a fixed **5 GiB** guest, with a
6 GiB memory and 40 GiB disk preflight. Wrapping that Python process does not
make its QEMU process follow the infrastructure's 4 GiB guest profile.

Use the isolated infrastructure handoff for the new 4 GiB qualification path.
Before executing the legacy controller, independently review its host-side
operations and satisfy its documented resource contract. Do not silently
change the preserved base image, claim a 4 GiB run, or execute untrusted PR
source through that controller. Hardware camera/TPM/PAM, a physical Wayland
session, and human screen-reader qualification remain separate evidence.
