"""Refresh small upstream metadata only; never download model weights."""
import concurrent.futures
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPOS = {
    "ComfyUI": "Comfy-Org/ComfyUI",
    "ComfyUI-KJNodes": "kijai/ComfyUI-KJNodes",
    "rgthree-comfy": "rgthree/rgthree-comfy",
    "ComfyUI-Easy-Use": "yolain/ComfyUI-Easy-Use",
    "ComfyUI-VideoHelperSuite": "Kosinkadink/ComfyUI-VideoHelperSuite",
    "ComfyUI-H3-Prompt-IDE": "ethanfel/ComfyUI-H3-Prompt-IDE",
    "H3-Optimizations": "Zironic/H3-Optimizations",
    "Comfyui_Minimax_h3_latent_Upscaler": "LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler",
    "ComfyUI-H3-Motion-Context": "NikoDemon80/ComfyUI-H3-Motion-Context",
    "ComfyUI-Minimax-H3-Reference-Library": "nikaskeba/ComfyUI-Minimax-H3-Reference-Library",
    "ComfyUI-Sol-H3": "xmarre/ComfyUI-Sol-H3",
}
MODELS = [
    ("WarmBloodAban/Minimax-h3_Singularity", "Minimax-h3_Singularity_ref2va_Pruned_v1.3_int8.safetensors", "diffusion_models"),
    ("Comfy-Org/MiniMax-H3", "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "text_encoders"),
    ("Kijai/MiniMax-H3-experimental", "minimax_h3_video_vae_int8_convrot.safetensors", "vae"),
    ("Comfy-Org/MiniMax-H3", "vae/minimax_h3_audio_vae_fp32.safetensors", "vae"),
    ("LBH-123-AI/Minimax_h3_latent_Upscaler", "minimax_h3_latent_upscaler_3d_bf16.safetensors", "latent_upscale_models"),
]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "h3-image-builder"}), timeout=60) as response:
        return json.load(response)


def resolve_repo(item):
    name, repo = item
    commit = get(f"https://api.github.com/repos/{repo}/commits?per_page=1")[0]
    return {"name": name, "repo": repo, "revision": commit["sha"], "date": commit["commit"]["committer"]["date"]}


def resolve_model(item):
    repo, filename, directory = item
    info = get(f"https://huggingface.co/api/models/{repo}?blobs=true")
    file = next(x for x in info["siblings"] if x["rfilename"] == filename)
    return {"repo": repo, "revision": info["sha"], "filename": filename,
            "directory": directory, "name": pathlib.PurePosixPath(filename).name,
            "size": file["size"], "sha256": file["lfs"]["sha256"]}


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        repos = list(pool.map(resolve_repo, REPOS.items()))
        models = list(pool.map(resolve_model, MODELS))
    for name, data in [("repositories.json", repos), ("models.json", models)]:
        (ROOT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Resolved {len(repos)} repositories and {len(models)} models: {sum(x['size'] for x in models)/1e9:.2f} GB.")
