rule trim_anemometer:
    input:
        nc = Path(config['munged_dir']) / "anemometer.nc"
    output:
        nc = Path(config['trimmed_dir']) / "anemometer.nc"
    params:
        instrument = 'anemometer',
        start      = config['campaign']['start'],
        end        = config['campaign']['end'],
        exclude    = config['campaign']['exclude']['anemometer']
    log:
        "logs/trim/anemometer.log"
    script:
        "../scripts/trim/trim.py"

rule trim_aranet:
    input:
        nc = Path(config['munged_dir']) / "aranet.nc"
    output:
        nc = Path(config['trimmed_dir']) / "aranet.nc"
    params:
        instrument = 'aranet',
        start      = config['campaign']['start'],
        end        = config['campaign']['end'],
        exclude    = config['campaign']['exclude']['aranet']
    log:
        "logs/trim/aranet.log"
    script:
        "../scripts/trim/trim.py"

rule trim_lascar:
    input:
        nc = Path(config['munged_dir']) / "lascar.nc"
    output:
        nc = Path(config['trimmed_dir']) / "lascar.nc"
    params:
        instrument = 'lascar',
        start      = config['campaign']['start'],
        end        = config['campaign']['end'],
        exclude    = config['campaign']['exclude']['lascar']
    log:
        "logs/trim/lascar.log"
    script:
        "../scripts/trim/trim.py"

rule trim_hhb:
    input:
        nc = Path(config['munged_dir']) / "hhb.nc"
    output:
        nc = Path(config['trimmed_dir']) / "hhb.nc"
    params:
        instrument = 'hhb',
        start      = config['campaign']['start'],
        end        = config['campaign']['end'],
        exclude    = config['campaign']['exclude']['hhb']
    log:
        "logs/trim/hhb.log"
    script:
        "../scripts/trim/trim.py"

rule trim_upas:
    input:
        nc = Path(config['munged_dir']) / "upas.nc"
    output:
        nc = Path(config['trimmed_dir']) / "upas.nc"
    params:
        instrument = 'upas',
        start      = config['campaign']['start'],
        end        = config['campaign']['end'],
        exclude    = config['campaign']['exclude']['upas']
    log:
        "logs/trim/upas.log"
    script:
        "../scripts/trim/trim.py"