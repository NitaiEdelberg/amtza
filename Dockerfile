# Backend container, shaped for Hugging Face Spaces (non-root uid 1000, port 7860).
#
# NOT the live deployment. Spaces now requires a paid plan for anything that runs
# compute — only Static Spaces are free, and those cannot run Python — so the
# backend runs on Render's free tier instead, from `render.yaml`, with no container
# involved. This file is kept because it is still correct, and any container host
# (Spaces on a paid plan, Fly, Cloud Run) can use it as-is.
#
# The vectors are streamed at boot (see _load_vec_url) rather than downloaded in
# full, so a cold start needs no persistent disk. Set PREBUILT_CACHE_URL to skip
# even that and fetch the finished 178MB caches instead.
# 3.10 chosen deliberately: requirements.txt pins numpy 1.24.4 / scikit-learn 1.3.2,
# which both ship prebuilt cp310 wheels — so the image builds without needing a
# compiler. (Local dev runs 3.8; 3.10 is the safe modern floor for these pins.)
FROM python:3.10-slim

# Spaces runs containers as a non-root user with UID 1000.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

COPY --chown=user backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user backend/ ./

# Writable location for the parsed .npy caches (ephemeral on the free tier).
ENV MODEL_CACHE_DIR=/home/user/models
RUN mkdir -p /home/user/models

# Spaces expects the app on 7860.
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
