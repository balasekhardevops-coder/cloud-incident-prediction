from pathlib import Path

import numpy as np
import pandas as pd

# 1. Reproducible random numbers
rng = np.random.default_rng(42)

# 2. Create 1000 measurements, one every minute
rows = 1000
prediction_window = 30
timestamps = pd.date_range(start="2026-01-01", periods=rows, freq="min")
time = np.arange(rows)

# 3. Generate normal infrastructure behavior
cpu = 35 + 5 * np.sin(time / 30) + rng.normal(0, 3, rows)
memory = 45 + 4 * np.sin(time / 70) + rng.normal(0, 2.5, rows)
error_rate = rng.normal(0.6, 0.25, rows)
latency = 200 + 2 * cpu + rng.normal(0, 25, rows)
pod_restarts = rng.poisson(lam=0.15, size=rows)

# 4. Simulate incidents AND the deterioration leading to them
incident_event = np.zeros(rows, dtype=int)
incident_times = [150, 350, 550, 750, 950]
lead_time = 45

for incident_time in incident_times:
    incident_event[incident_time] = 1
    start = incident_time - lead_time
    period = slice(start, incident_time)
    ramp = np.linspace(0, 1, lead_time, endpoint=False)

    cpu[period] += 35 * ramp
    memory[period] += 25 * ramp
    error_rate[period] += 4 * ramp**2
    latency[period] += 1000 * ramp**2
    pod_restarts[period] += rng.poisson(lam=1.5 * ramp**2)

# 5. Add harmless CPU spikes so high CPU alone isn't always an incident
for start in [250, 640, 860]:
    cpu[start:start + 8] += 20

# 6. Constrain values to physically sensible ranges
cpu = np.clip(cpu, 0, 100)
memory = np.clip(memory, 0, 100)
error_rate = np.clip(error_rate, 0, 100)
latency = np.maximum(latency, 0)

# 7. A label of 1 means an incident in the NEXT 30 minutes
# Exclude the final 30 rows: their full future window isn't available
usable_rows = rows - prediction_window
labels = np.array([
    int(incident_event[i + 1:i + prediction_window + 1].any())
    for i in range(usable_rows)
])

# 8. Build the dataset without the internal incident_event array
# (incident_event is simulated ground truth, not an input feature)
df = pd.DataFrame({
    "timestamp": timestamps[:usable_rows],
    "cpu_usage_pct": cpu[:usable_rows],
    "memory_usage_pct": memory[:usable_rows],
    "error_rate_pct": error_rate[:usable_rows],
    "p95_latency_ms": latency[:usable_rows],
    "pod_restarts": pod_restarts[:usable_rows],
    "incident_next_30m": labels,
})

# 9. Save beside this script, independently of terminal working directory
output_path = Path(__file__).resolve().parent / "telemetry.csv"
df.to_csv(output_path, index=False)

print("Dataset generated successfully!")
print(f"CSV file: {output_path}")
print(f"Shape: {df.shape}")
print("Incident labels:", df["incident_next_30m"].value_counts().sort_index().to_dict())
print("Mean metrics by label:")
print(df.groupby("incident_next_30m")[
    ["cpu_usage_pct", "memory_usage_pct", "error_rate_pct", "p95_latency_ms", "pod_restarts"]
].mean().round(2).to_string())
