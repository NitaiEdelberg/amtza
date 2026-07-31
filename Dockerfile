# Backend container, sized for Hugging Face Spaces (free tier: 2 vCPU / 16GB RAM).
#
# Why HF Spaces rather than a serverless host: this process keeps ~350MB of
# fastText vectors resident, so it needs a real long-lived container with real
# memory. Spaces gives that away for free, which Railway/Render do not.
#
# The vectors are streamed at boot (see _load_vec_url) rather than downloaded in
# full, so a cold start is ~2 minutes and needs no persistent disk — which matters
# here because free Spaces have ephemeral storage and rebuild on restart.
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
