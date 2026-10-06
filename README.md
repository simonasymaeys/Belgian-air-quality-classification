# Belgian Air Quality: Predicting Elevated PM2.5 Tomorrow

**Author:** Simona Barbuceanu  
**Programme:** BSc Artificial Intelligence & Sustainable Technologies, Tomorrow University  
**Project:** Supervised classification capstone

## Project overview

Can recent pollution measurements help identify elevated fine-particle pollution tomorrow? This project predicts whether the next local calendar day's average PM2.5 will exceed **15 µg/m³** at a Belgian monitoring station.

PM2.5 refers to fine airborne particles with a diameter of 2.5 micrometres or less. The project explores an environmental decision-support question: could analysts use a prediction to identify days worth reviewing for a possible pollution warning?

The threshold is an analytical rule informed by the WHO 2021 air-quality guidelines. It is **not a legal limit, a complete WHO compliance assessment, or a safe/unsafe boundary**. This is an educational retrospective prototype; no real-world health or societal benefit has been demonstrated.

## Prediction timing

Predictions are defined for **23:00 Europe/Brussels**, with an assumed evidence cutoff of **22:00**, for the following day. Today's daily average is unfinished at prediction time, so the latest complete daily input is yesterday: **two calendar days before the target**.

For example, a prediction made on 10 January at 23:00 targets 11 January and uses complete daily pollution measurements through 9 January. The one-hour publication buffer is an assumption. Live availability and revision timing have not been validated.

## Data and preparation

- **Sources:** IRCEL–CELINE measurements, reconciled against official Belgian EEA E1a reporting records.
- **Period:** 2022–2025, covering 60 Belgian monitoring stations.
- **Scale:** 87,660 calendar station-days, of which 85,734 have eligible labels.
- **Target:** `above_15 = 1` when an eligible daily PM2.5 average is strictly greater than 15 µg/m³.
- **Quality rules:** verified, valid, finite, non-negative hourly measurements; daily labels require at least 75% valid hourly coverage.
- **Time handling:** Belgian local days, including 23- and 25-hour daylight-saving days. Missing dates remain on the calendar grid; target labels are never imputed.
- **Station selection:** at least 90% verified hourly coverage in each training year, without using future-year coverage for selection.

The bundled daily data allow offline notebook execution once dependencies are installed. Hourly data, provenance records and rebuilding scripts are also included.

## Features and evaluation design

The original model uses 23 features: previous pollution readings, rolling averages and variability, recent changes, data-availability indicators, and cyclical calendar information. Features are calculated within each station and use only information permitted by the prediction cutoff. Station identifiers remain metadata; weather inputs are not included.

| Purpose | Years |
|---|---|
| Training | 2022–2023 |
| Validation and model/threshold selection | 2024 |
| Final evaluation of the frozen primary model | 2025 |

A chronological split represents forecasting future days and avoids mixing nearby observations across random splits. Imputation and scaling are fitted only on training data inside model pipelines. Calendar-boundary checks and future-value mutation checks test feature alignment and leakage prevention.

## Models

1. **Persistence:** predict an elevated day if the latest available complete daily reading exceeded 15 µg/m³, with a training-majority fallback when missing.
2. **Logistic regression:** compare class weights and probability-score thresholds on 2024 data. The frozen primary model uses positive-class weight 8, `C=1`, and threshold 0.40.
3. **Random forest:** a nonlinear comparator with a modest depth/leaf-size search on validation data.
4. **Reduced logistic regression:** an exploratory 11-feature simplification.

Always-elevated and always-non-elevated rules provide additional reference points. Selection prioritises **F2**, which gives more weight to recall, while precision and F1 expose the false-alarm trade-off.

**Evaluation history:** the original logistic model was selected before examining 2025. Random forest and reduced-feature comparisons were added after the original 2025 evaluation; their test results are exploratory. They do not replace the primary model based on test-year performance. No fitting or tuning uses 2025 data.

## Key results

Results below cover **21,275 eligible station-days in 2025**, including 3,196 elevated days.

| Model | Precision | Recall | F1 | F2 | Status |
|---|---:|---:|---:|---:|---|
| Persistence | 49.9% | 49.3% | 0.496 | 0.494 | Baseline |
| Logistic regression | 27.4% | 90.1% | 0.420 | 0.618 | Frozen primary model |
| Random forest | 32.5% | 82.5% | 0.466 | 0.631 | Exploratory |
| Reduced logistic regression | 27.8% | 90.7% | 0.426 | 0.625 | Exploratory |

The primary model detected **2,878 elevated station-days**, missed **318**, and generated **7,641 false alarms**. Its average precision was **0.508** and ROC AUC **0.844**.

Compared with persistence, the primary model caught 1,302 more elevated station-days but produced 6,058 more false alarms. It achieved higher recall and F2; persistence achieved higher precision and F1. These are monitoring-location days, not people or unique national pollution events.

## Repository contents

| Location | Contents |
|---|---|
| `notebooks/classification_capstone.ipynb` | Complete analysis, code, embedded visuals, interpretation and ethics reflection |
| `data/pm25_daily_belgian_time.csv` | Authoritative bundled daily modelling input |
| `data/pm25_hourly_reconciled.csv.gz` | Official hourly input for rebuilding daily data |
| `data/pm25_daily_rebuilt.csv` | Rebuilt daily table, checked against the modelling input |
| `data/` | Source manifest, quality checks, station mapping and frozen model/configuration |
| `src/e1a_to_hourly.py` | Download, hash-check and extract official hourly records |
| `src/hourly_to_daily.py` | Convert hourly records into eligible Belgian daily averages |
| `results/` | Comparison tables, predictions, feature diagnostics and summary files |
| `requirements.txt` | Python dependencies |

## Run the notebook

Use Python 3.11 or later. From the extracted project root, create and activate a virtual environment:

```bash
python -m venv .venv
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project dependencies and JupyterLab:

```bash
python -m pip install -r requirements.txt
python -m pip install jupyterlab
python -m jupyterlab
```

Open `notebooks/classification_capstone.ipynb` and run all cells in order. Use the project root or `notebooks/` as the notebook working directory. Execution regenerates result files in `results/`. Existing notebook outputs can be read without rerunning the analysis.

### Optional data rebuilding

Rebuild daily data from the bundled hourly file:

```bash
python src/hourly_to_daily.py
```

For a full reconstruction from official source files, run:

```bash
python src/e1a_to_hourly.py
python src/hourly_to_daily.py
```

The full source reconstruction requires internet access and downloads approximately 1.1 GB of XML files. The manifest records URLs and SHA-256 hashes. The daily rebuilding script writes `pm25_daily_rebuilt.csv`; it does not overwrite the authoritative modelling file. The notebook checks that core daily columns match.

## Reliability, ethics and intended use

Performance varies by season and station. Autumn recall is substantially lower than the annual figure, and false alarms are frequent. Class-weighted scores have not been calibrated and should not be presented as reliable event probabilities. Correlated station-days also limit interpretation of sample size; no confidence intervals are claimed.

The model predicts outdoor station concentrations, not personal exposure or symptoms. Monitoring-network coverage may underrepresent some communities. Station-level diagnostics assess geographic performance variation but do not establish demographic fairness.

A future pilot would require validated live-data timing, weather forecasts available before cutoff, calibrated scores, an agreed false-alarm tolerance, human oversight and prospective evaluation on a fresh period. The model should not be used as an autonomous public-warning service or a replacement for official forecasts.

## Sources and attribution

- [IRCEL–CELINE open data](https://www.irceline.be/en/documentation/open-data)
- [IRCEL historical measurement documentation](https://github.com/irceline/open_data/blob/master/datasets/measurements.md)
- [Official Belgian E1a reporting](https://cdr.eionet.europa.eu/be/eu/aqd/e1a/)
- [WHO 2021 global air-quality guidelines](https://www.who.int/publications/i/item/9789240034228)

Source measurements are attributed to **IRCEL–CELINE** under **CC BY 4.0**. This project aggregates hourly observations and creates derived features and labels; see the notebook and source manifest for provenance. The source-data licence does not automatically license the project code.
