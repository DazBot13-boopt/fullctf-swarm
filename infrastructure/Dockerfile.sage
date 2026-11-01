# Ajoute SageMath (via conda-forge) PAR-DESSUS l'arsenal hard-CTF, sans rebuilder
# le reste. SageMath = crypto avancée (courbes elliptiques, Coppersmith, lattices).
#
# Build : docker build -f infrastructure/Dockerfile.sage -t fullctf-worker:sage .
# (long : SageMath est volumineux). Puis on promeut en :latest.

FROM fullctf-worker:hardctf

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/conda/bin:${PATH}"

# --- Miniforge (conda + mamba), le moyen fiable d'installer SageMath sur Debian/Kali ---
RUN wget -q -O /tmp/miniforge.sh \
      https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm -f /tmp/miniforge.sh \
    && /opt/conda/bin/conda --version

# --- SageMath via conda-forge (mamba, plus rapide ; repli conda) ---
RUN /opt/conda/bin/mamba install -y -c conda-forge sage \
    || /opt/conda/bin/conda install -y -c conda-forge sage \
    || echo "SKIP sage"
RUN /opt/conda/bin/conda clean -afy || true

# --- un lien pour que `sage` soit toujours sur le PATH standard ---
RUN ln -sf /opt/conda/bin/sage /usr/local/bin/sage 2>/dev/null \
    && sage --version || echo "SKIP sage verify"

WORKDIR /work
CMD ["/bin/bash"]
