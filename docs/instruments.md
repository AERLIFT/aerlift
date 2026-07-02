# Instruments

Seven sensor platforms are supported. Each has a dedicated munge script that
parses its raw format, standardizes datetime to UTC, renames variables to
project conventions, deduplicates records, and writes a CF-1.8 NetCDF4 file.

---

## Anemometer (CP202526)

**Measurements:** Air flow velocity, flow indicator
**Raw format:** `.txt` (fixed-width, 6 header rows)
**Munge script:** `workflow/scripts/munge/anemometer.py`

Files may be organized in per-device subdirectories (e.g. `0_raw/anemometer/E102/`);
the pipeline globs recursively.

**Output variables:**

| Variable | Units | Description |
|---|---|---|
| `air_flow` | m/s | Air flow velocity |
| `flow_indicator` | — | Binary flow presence indicator |

---

## Aranet4

**Measurements:** CO₂, temperature, relative humidity, atmospheric pressure
**Raw format:** `.csv`
**Munge script:** `workflow/scripts/munge/aranet.py`

**Output variables:**

| Variable | Units | Description |
|---|---|---|
| `co2` | ppm | CO₂ mixing ratio |
| `temperature` | °C | Ambient temperature |
| `rh` | % | Relative humidity |
| `pressure` | hPa | Atmospheric pressure |

---

## Lascar EL-USB

**Measurements:** Carbon monoxide (CO)
**Raw format:** `.txt`
**Munge script:** `workflow/scripts/munge/lascar.py`

**Output variables:**

| Variable | Units | Description |
|---|---|---|
| `co` | ppm | CO mixing ratio |

---

## Atmotube Pro

**Measurements:** Particulate matter, air quality score, VOC, NOx, CO₂, met, GPS
**Raw format:** `.csv`
**Munge script:** `workflow/scripts/munge/atmotube.py`

**Output variables:**

| Variable | Units | Description |
|---|---|---|
| `aqs` | — | Air quality score (0–100) |
| `pm1` | µg/m³ | PM1.0 mass concentration |
| `pm25` | µg/m³ | PM2.5 mass concentration |
| `pm10` | µg/m³ | PM10 mass concentration |
| `temperature` | °C | Ambient temperature |
| `rh` | % | Relative humidity |
| `pressure` | hPa | Atmospheric pressure |
| `tvoc_index` | — | Total VOC index |
| `tvoc` | ppm | Total VOC concentration |
| `nox_index` | — | NOx index |
| `co2` | ppm | CO₂ mixing ratio |

---

## Aulifants

**Measurements:** Electrical power monitoring (voltage, current, power, energy)
**Raw format:** `.CSV` — files matching the pattern `*-D.CSV` inside per-device subdirectories named `{device}-Aulifant4-{date}/`
**Munge script:** `workflow/scripts/munge/aulifants.py`

The script parses unit-suffixed strings (e.g. `112.3Volt`, `0.00Amp`) by stripping
non-numeric characters before casting to float.

**Output variables:**

| Variable | Units | Description |
|---|---|---|
| `voltage` | V | Line voltage |
| `current` | A | Current draw |
| `power` | W | Real power |
| `power_factor` | — | Power factor |
| `cummulative_energy` | kWh | Cumulative energy consumed |
| `cost` | USD | Estimated energy cost |

---

## Home Health Box (HHB v2)

**Measurements:** Particulate matter, CO₂, electrochemical gases (NO₂, O₃), VOC, NOx, met
**Raw format:** `.csv`
**Munge scripts:** `workflow/scripts/munge/hhb.R` → `workflow/scripts/munge/hhb.py` (two-step)

HHB munging is split into two Snakemake rules. The R step (`munge_hhb_r`) uses the
`astr` package to decode the proprietary HHB CSV format into a tidy intermediate CSV.
The Python step (`munge_hhb`) reads that CSV, renames variables, and writes NetCDF4.

**Alphasense positions** must be set in `config.yaml` to match the physical sensors
installed in each HHB unit for the campaign:

```yaml
instruments:
  hhb:
    alphasense:
      position_1: 'NO2'
      position_2: 'O3'
      position_3: null
      position_4: null
```

**Output variables (selected):**

| Variable | Units | Description |
|---|---|---|
| `sen_pm1_raw` | µg/m³ | Sensirion PM1.0 mass concentration |
| `sen_pm25_raw` | µg/m³ | Sensirion PM2.5 mass concentration |
| `sen_pm10_raw` | µg/m³ | Sensirion PM10 mass concentration |
| `sen_temperature` | °C | Sensirion temperature |
| `sen_rh` | % | Sensirion relative humidity |
| `sen_voc_raw` | — | Raw VOC index signal |
| `sen_nox_raw` | — | Raw NOx index signal |
| `scd30_co2` | ppm | SCD30 CO₂ |
| `{gas}_algorithm1` | ppb | Alphasense electrochemical gas (position-dependent) |

---

## UPAS v2.1

**Measurements:** Particulate matter (mass + number), met, light, accelerometry, CO₂, VOC, NOx
**Raw format:** `.txt`
**Munge scripts:** `workflow/scripts/munge/upas.R` → `workflow/scripts/munge/upas.py` (two-step)

Like HHB, UPAS munging uses R (`astr` package) to parse the raw log format into an
intermediate CSV, then Python writes NetCDF4.

**Output variables (selected):**

| Variable | Units | Description |
|---|---|---|
| `upas_pm1_mc` / `upas_pm25_mc` / `upas_pm10_mc` | µg/m³ | PM mass concentration |
| `upas_pm1_nc` / `upas_pm25_nc` / `upas_pm10_nc` | #/cm³ | PM number concentration |
| `upas_atmo_temperature` | °C | Atmospheric temperature |
| `upas_atmo_rh` | % | Atmospheric relative humidity |
| `upas_atmo_pressure` | hPa | Atmospheric pressure |
| `upas_lux` | lux | Illuminance |
| `upas_uv_index` | — | UV index |
| `upas_co2` | ppm | CO₂ mixing ratio |
| `upas_voc_raw` | — | Raw VOC index signal |
| `upas_nox_raw` | — | Raw NOx index signal |
| `upas_accel_x/y/z` | mg | Accelerometer axes |
