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
RUN conda run -n aerlift-r Rscript -e 'devtools::install_github("accsensors/astr")'

# 4. Set up working directory
WORKDIR /aerlift

COPY . .

ENV PATH="/opt/conda/envs/aerlift-python/bin:$PATH"

# 7. Run snakemake
CMD ["snakemake", "--cores", "1", "--use-conda"]
