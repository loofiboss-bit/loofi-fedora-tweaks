# v25.0.4 “Proof” — Version Lineage and Collision Report

Status: v25.0.4 is the selected public Proof identity. Historical tags remain
unchanged and are documented below.

## Exact tag-to-commit mapping

| Tag | Tag object | Peeled commit | Historical meaning |
| --- | --- | --- | --- |
| `v24.0.0` | `d5d8173417b7074a0683a106ab710a61a8b2944b` | `709faf837649989724b3d744b60dae538b5cec8b` | Flow public release |
| `v25.0.0` | `0d9d125046e8b7754bde2b3d8f9902b48676df37` | `d4b5ace42f1c2c0a4e889689f0d899ccd3725dce` | Plugin Architecture historical line |
| `v25.0.1` | `545592be9cf915a7feaf4b82fe6dc2b0a9665c07` | `5ad7aa7d775a56524ae0918510285997da02bd9d` | Historical hotfix |
| `v25.0.2` | `f9464e5aabe9b12b14c41150b313a11d138df0be` | `011e6b25f0ae01d1bcecf605a63807565e20935d` | Historical testability hotfix |
| `v25.0.3` | `f7cc9078327172635e4854412095a97c917d93de` | `da9adde7885e743ed0f5265a34b4a7ec346697bf` | Historical maintenance-crash hotfix |
| `legacy-v24.0.0-power-features` | `dd2a23f8bfb837d3f20e2fc65e63c21a11cb8cd8` | same | Preserved v24 collision lineage |

The `v25.0.x` tags through `v25.0.3` predate Proof and were not moved,
deleted, or recreated. `v25.0.4` is the first unused v25 patch identity and is
the canonical Proof release tag.

## Publication decision

The historical collision is resolved non-destructively by using `v25.0.4`.
The release workflow must still prove that `v25.0.4` points to the exact release
commit before publication.
