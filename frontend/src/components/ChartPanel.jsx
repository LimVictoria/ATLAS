import { useState } from "react";
import Plot from "react-plotly.js";
import { Maximize2 } from "lucide-react";

export default function ChartPanel({ chartJson }) {
  const [expanded, setExpanded] = useState(false);

  if (!chartJson) return null;

  let chartData = null;
  try {
    chartData = typeof chartJson === "string" ? JSON.parse(chartJson) : chartJson;
  } catch {
    return <div className="chart-error">Failed to render chart</div>;
  }

  if (chartData.error) {
    return <div className="chart-error">Chart error: {chartData.error}</div>;
  }

  const layout = {
    ...(chartData.layout || {}),
    paper_bgcolor: "#ffffff",
    plot_bgcolor:  "#f8fafc",
    font: { color: "#0f172a", family: "IBM Plex Sans, sans-serif", size: 11 },
    margin: { t: 40, r: 20, b: 60, l: 60 },
    autosize: true,
    xaxis: { ...(chartData.layout?.xaxis || {}), gridcolor: "#e2e8f0", linecolor: "#cbd5e1" },
    yaxis: { ...(chartData.layout?.yaxis || {}), gridcolor: "#e2e8f0", linecolor: "#cbd5e1" },
  };

  return (
    <div className={`chart-panel ${expanded ? "chart-panel--expanded" : ""}`}>
      <div className="chart-toolbar">
        <button className="chart-btn" onClick={() => setExpanded(!expanded)}>
          <Maximize2 size={12} />
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>
      <Plot
        data={chartData.data || []}
        layout={layout}
        config={{ responsive: true, displayModeBar: true, displaylogo: false }}
        style={{ width: "100%", height: expanded ? 500 : 320 }}
      />
    </div>
  );
}
