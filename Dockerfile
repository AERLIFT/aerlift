FROM continuumio/miniconda3

# 1. Install system dependencies for R and data formats
RUN apt-get update && apt-get install -y \
    r-base \
    libnetcdf-dev \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Build Python environment (contains snakemake)
COPY workflow/envs/python.yaml /tmp/python.yaml
RUN conda env create -f /tmp/python.yaml && conda clean -a

# 3. Build R environment and install GitHub-specific package
COPY workflow/envs/r.yaml /tmp/r.yaml
RUN conda env create -f /tmp/r.yaml && conda clean -a
RUN conda run -n aerlift-r Rscript -e \
    'devtools::install_github("accsensors/astr", upgrade="never")'
# 4. Set up working directory
WORKDIR /aerlift
COPY . .

# 5. Expose both conda envs; python env takes priority for snakemake
ENV PATH="/opt/conda/envs/aerlift-python/bin:/opt/conda/envs/aerlift-r/bin:$PATH"
ENV CONDA_DEFAULT_ENV=aerlift-python
RUN ln -sf /opt/conda/envs/aerlift-r/bin/Rscript /usr/local/bin/Rscript

# 6. Run snakemake (no --use-conda: envs are already built into the image)
CMD ["snakemake", "--cores", "1"]