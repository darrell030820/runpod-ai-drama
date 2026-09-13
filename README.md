# Prepared H3 image for RunPod

Extends **runpod/comfyui:1.4.7-cuda13.0**, pinned to its verified image digest.
Build this in GitHub Actions. No Docker installation or model downloads are needed on your PC.

## What is prepared

- ComfyUI's newest main-branch commit checked on **13 September 2026**, recorded in `repositories.json`.
- All custom-node packs required by `EP01_SOL_FULL_6_GEN_CACHED_EXACT.json`, including nodes inside subgraphs.
- LBH's latent upscaler and Niko's Motion Context pack.
- Sol-H3 Exact Runtime and its Linux dependencies. This node is still separate from the checked ComfyUI core.
- Reference caching, H3 Prompt IDE, KJNodes, rgthree, Easy Use, VideoHelperSuite and H3 Optimizations.
- Five exact model filenames, with pinned download revisions, byte sizes and SHA256 checksums.
- Eight Episode 1 reference images and the current workflow. Steps, MP, prompts, seeds and latent wiring are unchanged.
- RunPod's existing SSH, Jupyter, FileBrowser and ComfyUI startup services.

ComfyUI and node source/dependencies are installed during the cloud image build.
Models download to persistent `/workspace/runpod-slim/ComfyUI/models` on the first start.
Subsequent starts reuse verified files, and interrupted downloads resume from `.part` files.
This avoids storing another 52.58 GB of weights inside the image and pulling them on every new machine.

The disabled Cinema LoRA is not downloaded because the current workflow does not use it.
The upscaler checkpoint **is** included so the existing optional upscale branch remains usable.
This package covers the current workflow's model set, not every unrelated JSON in the workspace.

## Build from your browser

1. Create an empty GitHub repository, for example `h3-runpod`.
2. Upload the **contents** of this folder to the repository root, including `.github/workflows/build.yml`.
   GitHub must show `Dockerfile` at the top level, not inside a `runpod_h3` directory.
   If the upload picker hides `.github`, use GitHub **Add file -> Create new file**, name it
   `.github/workflows/build.yml`, and paste the supplied file contents.
3. Open **Actions -> Build H3 RunPod image -> Run workflow**.
4. After it succeeds, open the run summary and copy the exact `ghcr.io/...:sha-...` image name.
5. Open your GitHub profile's **Packages -> h3-comfy -> Package settings**.
   For a public image, change package visibility to public. Alternatively keep it private and
   configure RunPod registry credentials with a GitHub token that can read the package.

The Actions build uses GitHub's temporary disk. It removes unused SDKs on that disposable runner,
checks free space, then builds for Linux AMD64. If your account's runner lacks disk or build minutes,
use a larger hosted runner by changing `runs-on`. No paid runner is selected automatically.

## RunPod template

Create a custom Pod template with:

| Setting | Value |
| --- | --- |
| Container image | Exact `ghcr.io/...:sha-...` value from the successful build summary |
| Container start command | Leave empty; preserve the image entrypoint |
| HTTP ports | `8188,8888,8080` |
| TCP port | `22` if you use SSH |
| Network volume mount | `/workspace` |
| Network volume capacity | 100 GB minimum suggested for 52.58 GB models plus inputs, caches and outputs |
| Container disk | 30 GB suggested; increase if RunPod reports insufficient space for the image |
| GPU | Your RTX PRO 6000 Blackwell workstation GPU |

Set your usual Jupyter/FileBrowser passwords in the template environment variables
`JUPYTER_PASSWORD` and `FILEBROWSER_PASSWORD`. Keep the same network volume for later Pods.
Select a GPU in the network volume's data center.

If your existing model files are already at the path above, they are verified and reused.
If they are in another installation, move/copy them **within RunPod** to the matching model folders
before startup, or use a fresh volume and let this image download them once.
Do not attach the same writable workspace to two rendering Pods concurrently.

The image uses a dedicated `/opt/h3-venv`, so an old persistent virtual environment cannot
override the image's Python/CUDA packages. The base updater refreshes the managed ComfyUI/node
code on the workspace while preserving models, input, output and user data. Manual edits inside
those managed code repositories are replaced by the baked versions.

## Confirm it is ready

The first boot includes model download and checksum time. Watch the Pod logs for:

`H3 models and reference inputs ready. Starting ComfyUI.`

Then check this file from Jupyter or FileBrowser:

`/workspace/runpod-slim/h3-readiness.log`

It must end with `PASS: all workflow node types registered...`.
To repeat the check in the Pod terminal:

```bash
/opt/h3-venv/bin/python /opt/h3-setup/check_nodes.py --wait 60
```

Open ComfyUI on port 8188. The workflow is under
`user/default/workflows/H3_PREPARED/EP01_SOL_FULL_6_GEN_CACHED_EXACT.json`.
Run your normal episode. The readiness check confirms node availability and Niko's continuation
provider; it does not prove CUDA kernels, visual quality or a complete render.
First-use compilation can still happen, with compatible caches retained on the volume.

## Version and conflict handling

`repositories.json` pins the source snapshot; restarting a Pod never runs `git pull` or pip installs.
To deliberately refresh sources later, run `python resolve_manifest.py` in a cloud terminal,
commit the updated JSON files, then rebuild. Review compatibility when updating.

The Skeba pack also bundles Motion Context nodes. This build replaces **only its registration
entrypoint** with a cache-only entrypoint (two cached-reference nodes), preserving upstream code
and an `__init__.py.upstream` copy. Niko is the sole intended continuation provider. Do not update
the Skeba pack through Manager without reapplying that adjustment. Other pre-existing duplicate
packs on an old volume can still cause a readiness failure and should be reviewed.

The build constrains torch, torchvision and torchaudio to the CUDA 13 versions in the base image.
If a dependency cannot resolve with those versions, the build fails rather than silently changing
the GPU runtime. The finished image records `installed-packages.txt` under `/opt/h3-setup`.

## Validation status

Prepared and checked locally: exact base-image metadata/startup script, upstream repository
revisions, Hugging Face file sizes and hashes, all workflow node types, input filenames,
Python syntax, startup patch behavior and downloader integrity/reuse tests.

**The Docker image has not yet been built/pushed, and no GPU render has been run with it.**
Those checks require the GitHub Actions build and your RunPod startup/render.

## Sources

- [RunPod ComfyUI template source](https://github.com/runpod/containers/tree/main/official-templates/comfyui)
- [RunPod custom templates](https://docs.runpod.io/pods/templates/create-custom-template)
- [RunPod network volumes](https://docs.runpod.io/storage/network-volumes)
- [GitHub container publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
- [LBH latent upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler)
- [Niko Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)
- [Sol-H3 Exact Runtime](https://github.com/xmarre/ComfyUI-Sol-H3)
- Model sources and immutable revisions: `models.json`.
