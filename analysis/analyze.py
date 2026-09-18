"""
analyze.py - Turns the flight_*.csv files into plots and an interactive dashboard.

Run this AFTER the flight on your laptop (or on the Pi):

    pip install -r requirements-analysis.txt
    python analysis/analyze.py                      reads data/, writes analysis_output/
    python analysis/analyze.py --data /media/usb/x  another data directory
    python analysis/analyze.py --cdn                small dashboard file (needs internet to view)
    python analysis/analyze.py --no-png             skip the static PNG plots

Output (in analysis_output/):
    dashboard.html   interactive dashboard: key numbers, all charts, tables.
                     Open it in any browser. Zoom by dragging, hover for values.
    plots/*.png      the same charts as images, for reports and presentations
    summary.csv      min / max / mean of every measured column (table view)

How the file is organised:
    1. loading      - read the CSV files, convert to numbers, derive altitude
    2. statistics   - the key numbers for the top of the dashboard
    3. chart specs  - ONE list that says which charts exist (add yours here)
    4. renderers    - the specs drawn with plotly (dashboard) and matplotlib (PNG)
    5. dashboard    - the HTML page around the charts
"""

import argparse
import datetime
import html
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.flight_data import load_all  # noqa: E402

# ---------------------------------------------------------------------------
# Colours (a colour-blind-safe palette; see README "Auswertung")
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]        # fixed order, never cycled
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Columns that belong to each sensor; used for the availability table.
SENSOR_COLUMNS = {
    "bme280": ["temperature_c", "humidity_pct", "pressure_hpa"],
    "as7265x": ["spectrum_410nm"],
    "hmc5883l": ["mag_x_ut", "heading_deg"],
    "uv": ["uv_index"],
    "mq9": ["mq9_raw"],
    "co2": ["co2_ppm"],
    "radiation": ["radiation_1min_usvh"],
}

HEATMAP_MAX_COLUMNS = 1500   # downsample long flights for the heatmaps


# ===========================================================================
# 1. loading
# ===========================================================================

def load_dataframe(data_dir, prefix):
    """Reads all flight files into one pandas DataFrame with numeric columns."""
    columns, rows, files = load_all(data_dir, prefix)
    if not rows:
        raise SystemExit(f"No usable rows found in {data_dir}. Is the directory right?")

    df = pd.DataFrame(rows, columns=columns)
    for column in columns:
        if column not in ("time", "file", "errors"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df["errors"] = df["errors"].fillna("")

    if "pressure_hpa" in df:
        df["altitude_m"] = pressure_to_altitude(df["pressure_hpa"])
        df["phase"] = flight_phase(df["altitude_m"])
    return df, files


def pressure_to_altitude(pressure_hpa):
    """
    Estimated altitude above sea level from air pressure (international
    standard atmosphere). Good to a few hundred metres; the BME280 itself
    stops being reliable below about 300 hPa (~9 km).
    """
    ratio = pressure_hpa.clip(lower=0.1) / 1013.25
    return (44330.77 * (1 - ratio ** 0.190263)).round(0)


def flight_phase(altitude_m):
    """'ascent' up to the highest point, 'descent' afterwards."""
    phase = pd.Series("ascent", index=altitude_m.index)
    if altitude_m.notna().any():
        top = altitude_m.idxmax()
        phase.loc[altitude_m.index > top] = "descent"
    return phase


# ===========================================================================
# 2. statistics
# ===========================================================================

def compute_stats(df, files):
    """The key numbers shown at the top of the dashboard."""
    stats = []

    def add(label, value, unit="", note=""):
        stats.append({"label": label, "value": value, "unit": unit, "note": note})

    valid_times = df["time"].dropna()
    if len(valid_times) >= 2:
        duration = valid_times.max() - valid_times.min()
        add("Flight duration", format_duration(duration.total_seconds()),
            note=f"{valid_times.min():%d.%m.%Y %H:%M} - {valid_times.max():%H:%M}")
    add("Measurements", f"{len(df):,}".replace(",", " "), note=f"in {len(files)} file(s)")
    add("Restarts", str(max(0, len(files) - 1)), note="new file per program start")

    broken = sum(f["broken_rows"] for f in files)
    complete = (df["errors"] == "").mean() * 100 if len(df) else 0
    add("Complete rows", f"{complete:.1f}", "%", note=f"{broken} cut-off row(s) skipped")

    if "altitude_m" in df and df["altitude_m"].notna().any():
        add("Max altitude (est.)", f"{df['altitude_m'].max():,.0f}".replace(",", " "), "m",
            note="from pressure, standard atmosphere")
    if "pressure_hpa" in df:
        add("Min pressure", f"{df['pressure_hpa'].min():.1f}", "hPa")
    if "temperature_c" in df:
        add("Min temperature", f"{df['temperature_c'].min():.1f}", "°C",
            note=f"max {df['temperature_c'].max():.1f} °C")
    if "uv_index" in df:
        add("Max UV index", f"{df['uv_index'].max():.1f}")
    if "radiation_10min_usvh" in df:
        add("Max radiation", f"{df['radiation_10min_usvh'].max():.2f}", "µSv/h",
            note="10-minute average")
    if "radiation_vibration" in df and df["radiation_vibration"].notna().any():
        add("Shocks", f"{df['radiation_vibration'].mean() * 100:.0f}", "%",
            note="measurements the radiation sensor flagged as disturbed")
    if "co2_ppm" in df:
        add("CO2", f"{df['co2_ppm'].median():.0f}", "ppm",
            note=f"{df['co2_ppm'].min():.0f} - {df['co2_ppm'].max():.0f} ppm")
    return stats


def sensor_availability(df):
    """Per sensor: how many rows have a value, in percent."""
    result = []
    for sensor, columns in SENSOR_COLUMNS.items():
        present = [c for c in columns if c in df]
        if not present:
            continue
        ok = df[present[0]].notna().mean() * 100
        result.append({"sensor": sensor, "ok_pct": ok, "failed": int((df[present[0]].isna()).sum())})
    return result


def summary_table(df):
    """min / max / mean of every measured column (the 'table view' of the charts)."""
    skip = {"restart_no", "uptime_s", "measurement_no"}
    rows = []
    for column in df.columns:
        if column in skip or not pd.api.types.is_numeric_dtype(df[column]):
            continue
        series = df[column].dropna()
        if series.empty:
            continue
        rows.append({
            "column": column, "count": int(series.count()),
            "min": round(float(series.min()), 3), "max": round(float(series.max()), 3),
            "mean": round(float(series.mean()), 3),
            "first": round(float(series.iloc[0]), 3), "last": round(float(series.iloc[-1]), 3),
        })
    return pd.DataFrame(rows)


def format_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes = rest // 60
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


# ===========================================================================
# 3. chart specs - the single place that defines which charts exist
# ===========================================================================

def chart_specs(df):
    """
    Returns a list of chart descriptions. Every entry has:
      kind    - "lines" (over time), "profile" (vs altitude), "spectrum_heatmap",
                "spectrum_mean", "availability_heatmap", "availability_bars"
      title, unit, columns, labels, note (one line: what to look for)
    Only charts whose columns exist in the data are returned.
    """
    specs = [
        dict(kind="lines", section="Flight profile", title="Estimated altitude", unit="m",
             columns=["altitude_m"], labels=["altitude"],
             note="From air pressure. Climb, burst (the peak) and descent should be clearly visible."),
        dict(kind="lines", section="Flight profile", title="Air pressure", unit="hPa",
             columns=["pressure_hpa"], labels=["pressure"],
             note="Falls roughly exponentially with altitude. Below ~300 hPa the BME280 is out of its range."),
        dict(kind="lines", section="Atmosphere", title="Temperature", unit="°C",
             columns=["temperature_c"], labels=["temperature"],
             note="Drops about 6.5 °C per km up to the tropopause (~11 km), then stays or rises slightly."),
        dict(kind="lines", section="Atmosphere", title="Relative humidity", unit="%",
             columns=["humidity_pct"], labels=["humidity"],
             note="Usually falls quickly with altitude; a jump may mean a cloud layer."),
        dict(kind="lines", section="Atmosphere", title="CO2 concentration", unit="ppm",
             columns=["co2_ppm"], labels=["CO2"],
             note="Around 420 ppm outdoors. The sensor needs ~3 minutes warm-up after every start."),
        dict(kind="lines", section="Radiation", title="UV index", unit="",
             columns=["uv_index"], labels=["UV index"],
             note="Rises with altitude as less atmosphere filters the sunlight. Depends on the sensor's orientation."),
        dict(kind="lines", section="Radiation", title="Gamma radiation dose rate", unit="µSv/h",
             columns=["radiation_10min_usvh", "radiation_1min_usvh"], labels=["10-min average", "1-min average"],
             note="Cosmic radiation increases with altitude and peaks around 20 km (Pfotzer maximum). "
                  "The column radiation_vibration marks measurements the sensor considers disturbed."),
        dict(kind="lines", section="Gas and orientation", title="MQ-9 gas sensor (raw)", unit="ADC value",
             columns=["mq9_raw"], labels=["MQ-9 raw"],
             note="Uncalibrated. Only the change over time is meaningful, not the absolute value."),
        dict(kind="lines", section="Gas and orientation", title="Compass heading", unit="°",
             columns=["heading_deg"], labels=["heading"], markers=True,
             note="0 = north, 90 = east. Shows how fast the payload spins under the balloon."),
        dict(kind="lines", section="Gas and orientation", title="Magnetic field", unit="µT",
             columns=["mag_x_ut", "mag_y_ut", "mag_z_ut"], labels=["X", "Y", "Z"],
             note="The Earth's field is roughly 50 µT in total. Sudden jumps mean nearby metal or electronics."),
        dict(kind="spectrum_heatmap", section="Light spectrum", title="Light spectrum over time", unit="µW/cm²",
             note="Each row is one wavelength (410 nm violet ... 940 nm infrared), darker = brighter."),
        dict(kind="spectrum_mean", section="Light spectrum", title="Average spectrum of the whole flight", unit="µW/cm²",
             note="Sunlight peaks in the green/yellow range; the atmosphere absorbs some infrared bands."),
        dict(kind="profile", section="Vertical profiles", title="Temperature vs altitude", unit="°C",
             columns=["temperature_c"], note="The classic balloon plot: temperature on the way up and down."),
        dict(kind="profile", section="Vertical profiles", title="Radiation vs altitude", unit="µSv/h",
             columns=["radiation_10min_usvh"],
             note="Where is the radiation maximum? The 10-minute average is used here because the "
                  "1-minute value is very noisy at these low count rates."),
        dict(kind="profile", section="Vertical profiles", title="UV index vs altitude", unit="",
             columns=["uv_index"], note="How much more UV reaches the payload higher up?"),
        dict(kind="availability_bars", section="Data quality", title="Failed readings per sensor", unit="%",
             note="Which sensors had problems? Details are in the 'errors' column of the CSV files."),
        dict(kind="availability_heatmap", section="Data quality", title="Failed readings over time", unit="%",
             note="Dark cells = many failures in that time window. Vertical stripes = something affected all sensors."),
    ]
    usable = []
    for spec in specs:
        needed = spec.get("columns", [])
        if spec["kind"] == "profile":
            needed = needed + ["altitude_m"]
        if spec["kind"].startswith("spectrum"):
            needed = ["spectrum_410nm"]
        if all(column in df for column in needed):
            usable.append(spec)
    return usable


def spectrum_columns(df):
    columns = [c for c in df.columns if c.startswith("spectrum_") and c.endswith("nm")]
    return sorted(columns, key=lambda c: int(c[len("spectrum_"):-2]))


def with_gaps(df, column):
    """
    Returns x and y lists with a None inserted between two files, so that a
    line chart does not draw a false line across a restart / power cut.
    """
    xs, ys = [], []
    for _, group in df.groupby("restart_no", sort=True):
        if xs:
            xs.append(None)
            ys.append(None)
        xs.extend(group["time"].tolist())
        ys.extend(group[column].tolist())
    return xs, ys


def downsample(df, max_rows):
    step = max(1, math.ceil(len(df) / max_rows))
    return df.iloc[::step]


def availability_matrix(df, bins=60):
    """Failed readings in percent per sensor and time window."""
    sensors = [s for s, cols in SENSOR_COLUMNS.items() if cols[0] in df]
    window = pd.cut(range(len(df)), bins=min(bins, max(1, len(df))), labels=False)
    matrix = []
    for sensor in sensors:
        failed = df[SENSOR_COLUMNS[sensor][0]].isna().astype(float) * 100
        matrix.append(failed.groupby(window).mean().tolist())
    labels = df["time"].groupby(window).first().tolist()
    return sensors, labels, matrix


# ===========================================================================
# 4a. renderer: plotly (interactive dashboard)
# ===========================================================================

def plotly_figure(spec, df):
    import plotly.graph_objects as go

    fig = go.Figure()
    kind = spec["kind"]

    if kind == "lines":
        for i, (column, label) in enumerate(zip(spec["columns"], spec["labels"])):
            x, y = with_gaps(df, column)
            mode = "markers" if spec.get("markers") else "lines"
            fig.add_trace(go.Scatter(
                x=x, y=y, name=label, mode=mode, connectgaps=False,
                line=dict(width=2, color=SERIES[i]), marker=dict(size=4, color=SERIES[i]),
                hovertemplate="%{y} " + spec["unit"] + "<extra>" + label + "</extra>",
            ))
        layout = base_layout(spec, x_title="time", y_title=axis_title(spec))
        layout["hovermode"] = "x unified"

    elif kind == "profile":
        column = spec["columns"][0]
        for i, phase in enumerate(["ascent", "descent"]):
            part = df[df["phase"] == phase]
            fig.add_trace(go.Scatter(
                x=part[column], y=part["altitude_m"], name=phase, mode="markers",
                marker=dict(size=4, color=SERIES[i]),
                hovertemplate="%{x} " + spec["unit"] + " at %{y} m<extra>" + phase + "</extra>",
            ))
        layout = base_layout(spec, x_title=axis_title(spec), y_title="altitude (m)")

    elif kind == "spectrum_heatmap":
        columns = spectrum_columns(df)
        small = downsample(df, HEATMAP_MAX_COLUMNS)
        fig.add_trace(go.Heatmap(
            z=[small[c].tolist() for c in columns], x=small["time"],
            y=[c[len("spectrum_"):] for c in columns],
            colorscale=SEQUENTIAL, colorbar=dict(title=spec["unit"], thickness=10),
            hovertemplate="%{y}: %{z:.2f} " + spec["unit"] + "<extra></extra>",
        ))
        layout = base_layout(spec, x_title="time", y_title="wavelength")

    elif kind == "spectrum_mean":
        columns = spectrum_columns(df)
        fig.add_trace(go.Bar(
            x=[c[len("spectrum_"):] for c in columns], y=[df[c].mean() for c in columns],
            marker=dict(color=SERIES[0]), name="mean",
            hovertemplate="%{x}: %{y:.2f} " + spec["unit"] + "<extra></extra>",
        ))
        layout = base_layout(spec, x_title="wavelength", y_title=axis_title(spec))
        layout["bargap"] = 0.15

    elif kind == "availability_bars":
        rows = sensor_availability(df)
        fig.add_trace(go.Bar(
            x=[100 - r["ok_pct"] for r in rows], y=[r["sensor"] for r in rows], orientation="h",
            marker=dict(color=SERIES[0]),
            hovertemplate="%{y}: %{x:.1f} % failed<extra></extra>",
        ))
        layout = base_layout(spec, x_title="failed readings (%)", y_title="")
        layout["xaxis"]["rangemode"] = "tozero"

    elif kind == "availability_heatmap":
        sensors, labels, matrix = availability_matrix(df)
        fig.add_trace(go.Heatmap(
            z=matrix, x=labels, y=sensors, zmin=0, zmax=100, colorscale=SEQUENTIAL,
            colorbar=dict(title="% failed", thickness=10),
            hovertemplate="%{y}: %{z:.0f} % failed<extra></extra>",
        ))
        layout = base_layout(spec, x_title="time", y_title="")

    else:
        raise ValueError(f"unknown chart kind {kind}")

    fig.update_layout(**layout)
    return fig


def axis_title(spec):
    return f"{spec['title'].split(' vs ')[0].lower()} ({spec['unit']})" if spec["unit"] else spec["title"].lower()


def base_layout(spec, x_title, y_title):
    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="outside",
                tickcolor=AXIS, tickfont=dict(color=MUTED, size=11),
                title=dict(font=dict(color=INK_SECONDARY, size=12)))
    return dict(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_SECONDARY, size=12),
        title=dict(text=spec["title"], x=0, xanchor="left", font=dict(color=INK, size=15)),
        margin=dict(l=60, r=20, t=56, b=48), height=340,
        xaxis=dict(axis, title=dict(axis["title"], text=x_title)),
        yaxis=dict(axis, title=dict(axis["title"], text=y_title)),
        legend=dict(orientation="h", x=0, y=1.12, font=dict(color=INK_SECONDARY)),
        showlegend=len(spec.get("columns", [])) > 1 or spec["kind"] == "profile",
    )


# ===========================================================================
# 4b. renderer: matplotlib (static PNG files)
# ===========================================================================

def save_png(spec, df, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    kind = spec["kind"]
    ramp = LinearSegmentedColormap.from_list("sequential", SEQUENTIAL)

    if kind == "lines":
        for i, (column, label) in enumerate(zip(spec["columns"], spec["labels"])):
            # One line per file, so no false line is drawn across a restart.
            for number, (_, group) in enumerate(df.groupby("restart_no", sort=True)):
                style = "." if spec.get("markers") else "-"
                ax.plot(group["time"], group[column], style, markersize=3, linewidth=1.5,
                        color=SERIES[i], label=label if number == 0 else None)
        ax.set_xlabel("time")
        ax.set_ylabel(axis_title(spec))
        fig.autofmt_xdate()

    elif kind == "profile":
        column = spec["columns"][0]
        for i, phase in enumerate(["ascent", "descent"]):
            part = df[df["phase"] == phase]
            ax.plot(part[column], part["altitude_m"], ".", markersize=3, color=SERIES[i], label=phase)
        ax.set_xlabel(axis_title(spec))
        ax.set_ylabel("altitude (m)")

    elif kind == "spectrum_heatmap":
        columns = spectrum_columns(df)
        small = downsample(df, HEATMAP_MAX_COLUMNS)
        image = ax.imshow([small[c].tolist() for c in columns], aspect="auto", cmap=ramp,
                          origin="lower", interpolation="nearest")
        ax.set_yticks(range(len(columns)))
        ax.set_yticklabels([c[len("spectrum_"):] for c in columns], fontsize=7)
        ax.set_xlabel("measurement (in time order)")
        ax.set_ylabel("wavelength")
        fig.colorbar(image, ax=ax, label=spec["unit"])

    elif kind == "spectrum_mean":
        columns = spectrum_columns(df)
        ax.bar([c[len("spectrum_"):] for c in columns], [df[c].mean() for c in columns],
               color=SERIES[0], width=0.8)
        ax.set_xlabel("wavelength")
        ax.set_ylabel(axis_title(spec))
        ax.tick_params(axis="x", labelsize=8)

    elif kind == "availability_bars":
        rows = sensor_availability(df)
        ax.barh([r["sensor"] for r in rows], [100 - r["ok_pct"] for r in rows], color=SERIES[0])
        ax.set_xlim(left=0)
        ax.set_xlabel("failed readings (%)")

    elif kind == "availability_heatmap":
        sensors, labels, matrix = availability_matrix(df)
        image = ax.imshow(matrix, aspect="auto", cmap=ramp, vmin=0, vmax=100, interpolation="nearest")
        ax.set_yticks(range(len(sensors)))
        ax.set_yticklabels(sensors)
        ax.set_xlabel("time window (flight split into equal parts)")
        fig.colorbar(image, ax=ax, label="% failed")

    ax.set_title(spec["title"], loc="left", color=INK, fontsize=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED)
    ax.grid(not kind.endswith("heatmap"), color=GRID, linewidth=0.6)   # no grid over heatmaps
    ax.set_axisbelow(True)
    if len(spec.get("columns", [])) > 1 or kind == "profile":
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ===========================================================================
# 5. dashboard HTML
# ===========================================================================

CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #f9f9f7; color: #0b0b0b; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 36px 0 12px; color: #0b0b0b; }
.subtitle { color: #52514e; margin: 0 0 20px; font-size: 14px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.tile { background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 8px; padding: 14px 16px; }
.tile .label { font-size: 12px; color: #52514e; text-transform: uppercase; letter-spacing: 0.04em; }
.tile .value { font-size: 30px; color: #0b0b0b; margin: 4px 0 2px; line-height: 1.1; }
.tile .unit { font-size: 14px; color: #52514e; margin-left: 4px; }
.tile .note { font-size: 12px; color: #898781; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(460px, 100%), 1fr)); gap: 16px; }
.card { background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 8px; padding: 6px 8px 10px; min-width: 0; overflow: hidden; }
.card .note { font-size: 12px; color: #52514e; margin: 0 10px 4px; }
.table-wrap { overflow-x: auto; }
.subtitle code { word-break: break-all; }
table { border-collapse: collapse; font-size: 13px; background: #fcfcfb; width: 100%; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #e1e0d9; }
th { color: #52514e; font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.meter { height: 6px; background: #e1e0d9; border-radius: 3px; overflow: hidden; }
.meter > div { height: 100%; background: #2a78d6; }
footer { margin-top: 40px; color: #898781; font-size: 12px; }
@media (max-width: 600px) { .charts { grid-template-columns: 1fr; } }
"""


def build_dashboard(df, files, stats, specs, data_dir, use_cdn):
    import plotly
    import plotly.offline

    parts = ["<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>Weather balloon flight dashboard</title>",
             f"<style>{CSS}</style>"]
    if use_cdn:
        version = plotly.offline.get_plotlyjs_version()
        parts.append(f"<script src='https://cdn.plot.ly/plotly-{version}.min.js'></script>")
    else:
        parts.append(f"<script>{plotly.offline.get_plotlyjs()}</script>")
    parts.append("</head><body><main>")

    parts.append("<h1>Weather balloon flight dashboard</h1>")
    parts.append(f"<p class='subtitle'>Data from <code>{html.escape(os.path.abspath(data_dir))}</code>, "
                 f"generated {datetime.datetime.now():%d.%m.%Y %H:%M}</p>")

    # --- key numbers
    parts.append("<div class='tiles'>")
    for s in stats:
        unit = f"<span class='unit'>{html.escape(s['unit'])}</span>" if s["unit"] else ""
        note = f"<div class='note'>{html.escape(s['note'])}</div>" if s["note"] else ""
        parts.append(f"<div class='tile'><div class='label'>{html.escape(s['label'])}</div>"
                     f"<div class='value'>{html.escape(str(s['value']))}{unit}</div>{note}</div>")
    parts.append("</div>")

    # --- charts, grouped by section
    config = {"displaylogo": False, "responsive": True, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
    current_section = None
    for spec in specs:
        if spec["section"] != current_section:
            if current_section is not None:
                parts.append("</div>")
            current_section = spec["section"]
            parts.append(f"<h2>{html.escape(current_section)}</h2><div class='charts'>")
        fig = plotly_figure(spec, df)
        chart_html = fig.to_html(full_html=False, include_plotlyjs=False, config=config)
        parts.append(f"<div class='card'>{chart_html}<p class='note'>{html.escape(spec['note'])}</p></div>")
    if current_section is not None:
        parts.append("</div>")

    # --- tables
    parts.append("<h2>Sensor availability</h2><div class='table-wrap'><table><tr><th>sensor</th><th class='num'>readings ok</th>"
                 "<th class='num'>failed</th><th style='width:40%'></th></tr>")
    for r in sensor_availability(df):
        parts.append(f"<tr><td>{r['sensor']}</td><td class='num'>{r['ok_pct']:.1f} %</td>"
                     f"<td class='num'>{r['failed']}</td>"
                     f"<td><div class='meter'><div style='width:{r['ok_pct']:.0f}%'></div></div></td></tr>")
    parts.append("</table></div>")

    parts.append("<h2>Files</h2><div class='table-wrap'><table><tr><th>file</th><th class='num'>rows</th>"
                 "<th class='num'>cut-off rows</th><th>first row</th><th>last row</th></tr>")
    for f in files:
        parts.append(f"<tr><td>{html.escape(f['name'])}</td><td class='num'>{f['rows']}</td>"
                     f"<td class='num'>{f['broken_rows']}</td><td>{html.escape(f['first_time'])}</td>"
                     f"<td>{html.escape(f['last_time'])}</td></tr>")
    parts.append("</table></div>")

    parts.append("<h2>All values (table view)</h2><div class='table-wrap'><table><tr><th>column</th><th class='num'>count</th>"
                 "<th class='num'>min</th><th class='num'>max</th><th class='num'>mean</th>"
                 "<th class='num'>first</th><th class='num'>last</th></tr>")
    for _, r in summary_table(df).iterrows():
        parts.append(f"<tr><td>{r['column']}</td><td class='num'>{r['count']}</td><td class='num'>{r['min']}</td>"
                     f"<td class='num'>{r['max']}</td><td class='num'>{r['mean']}</td>"
                     f"<td class='num'>{r['first']}</td><td class='num'>{r['last']}</td></tr>")
    parts.append("</table></div>")

    parts.append("<footer>Altitude is estimated from air pressure with the international standard atmosphere "
                 "and is only a rough guide. Drag on a chart to zoom, double-click to reset.</footer>")
    parts.append("</main></body></html>")
    return "\n".join(parts)


# ===========================================================================
# main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Create plots and a dashboard from the flight data")
    parser.add_argument("--data", default="data", help="directory with the flight_*.csv files")
    parser.add_argument("--prefix", default="flight", help="file name prefix (default: flight)")
    parser.add_argument("--out", default="analysis_output", help="output directory")
    parser.add_argument("--cdn", action="store_true",
                        help="load plotly.js from the internet instead of embedding it (smaller file)")
    parser.add_argument("--no-png", action="store_true", help="do not create PNG plots")
    args = parser.parse_args()

    if not os.path.isdir(args.data):
        print(f"Directory not found: {args.data}")
        return 1

    print(f"Loading {args.data} ...")
    df, files = load_dataframe(args.data, args.prefix)
    print(f"  {len(df)} rows from {len(files)} file(s), "
          f"{sum(f['broken_rows'] for f in files)} cut-off row(s) skipped")

    os.makedirs(args.out, exist_ok=True)
    stats = compute_stats(df, files)
    specs = chart_specs(df)

    summary_path = os.path.join(args.out, "summary.csv")
    summary_table(df).to_csv(summary_path, index=False)
    print(f"  wrote {summary_path}")

    dashboard_path = os.path.join(args.out, "dashboard.html")
    with open(dashboard_path, "w", encoding="utf-8") as file:
        file.write(build_dashboard(df, files, stats, specs, args.data, args.cdn))
    print(f"  wrote {dashboard_path}  <- open this in a browser")

    if not args.no_png:
        plots_dir = os.path.join(args.out, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        for number, spec in enumerate(specs, start=1):
            name = "".join(ch if ch.isalnum() else "_" for ch in spec["title"].lower()).strip("_")
            path = os.path.join(plots_dir, f"{number:02d}_{name}.png")
            save_png(spec, df, path)
        print(f"  wrote {len(specs)} PNG plots to {plots_dir}")

    print("\nKey numbers:")
    for s in stats:
        print(f"  {s['label']:<22} {s['value']} {s['unit']}  {s['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
