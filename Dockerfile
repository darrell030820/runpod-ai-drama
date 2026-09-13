FROM runpod/comfyui:1.4.7-cuda13.0@sha256:094dc6d79448b6f118c4d2b054073f92d765c568598e7a96aaeda678a6bcbf3b

USER root
ENV COMFYUI_ROOT=/workspace/runpod-slim/ComfyUI \
    TRITON_CACHE_DIR=/workspace/runpod-slim/.cache/triton \
    TORCHINDUCTOR_CACHE_DIR=/workspace/runpod-slim/.cache/torchinductor
COPY . /opt/h3-setup/
RUN python3.12 /opt/h3-setup/build_image.py

# Preserve RunPod's SSH, Jupyter, FileBrowser and ComfyUI startup services.
ENTRYPOINT ["/start.sh"]
