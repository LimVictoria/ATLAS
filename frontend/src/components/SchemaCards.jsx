import { useState, useEffect, useCallback } from "react";
import { Database, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, BarChart2, Loader } from "lucide-react";
import Plot from "react-plotly.js";
import { getTableCharts } from "../utils/api";

// ── Cardinality config + legend ───────────────────────────────────────────────

const CARDINALITY = {
  id:          { icon: "🔑", label: "ID",         color: "#7c3aed", bg: "rgba(124,58,237,0.08)", tip: "Unique identifier — avoid aggregating" },
  numeric:     { icon: "📊", label: "Numeric",     color: "#0284c7", bg: "rgba(2,132,199,0.08)",  tip: "Continuous number — good for SUM, AVG" },
  categorical: { icon: "📦", label: "Categorical", color: "#059669", bg: "rgba(5,150,105,0.08)",  tip: "Low cardinality — good for GROUP BY, filters" },
  freetext:    { icon: "📝", label: "Free text",   color: "#d97706", bg: "rgba(217,119,6,0.08)",  tip: "High cardinality text — low analytical value" },
  date:        { icon: "📅", label: "Date",        color: "#db2777", bg: "rgba(219,39,119,0.08)", tip: "Datetime — defines your time dimension" },
};

const LEGEND_ITEMS = Object.entries(CARDINALITY);

// ── Plotly wrapper ────────────────────────────────────────────────────────────

function InlineChart({ chartJson, height = 240 }) {
  if (!chartJson) return null;
  try {
    const data = typeof chartJson === "string" ? JSON.parse(chartJson) : chartJson;
    if (data.error) return null;
    return (
      <Plot
        data={data.data || []}
        layout={{
          ...(data.layout || {}),
          paper_bgcolor: "#ffffff", plot_bgcolor: "#f8fafc",
          font: { color: "#0f172a", family: "IBM Plex Sans, sans-serif", size: 11 },
          margin: { t: 36, r: 16, b: 48, l: 52 },
          height, autosize: true,
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    );
  } catch { return null; }
}

// ── Frequency bar ─────────────────────────────────────────────────────────────

function FrequencyBars({ frequencies }) {
  if (!frequencies?.length) return null;
  return (
    <div className="freq-list">
      {frequencies.map((f) => (
        <div key={f.value} className="freq-row">
          <span className="freq-label" title={f.value}>{f.value}</span>
          <div className="freq-bar-wrap">
            <div className="freq-bar" style={{ width: `${f.pct}%` }} />
          </div>
          <span className="freq-pct">{f.pct}%</span>
        </div>
      ))}
    </div>
  );
}

// ── Column row ────────────────────────────────────────────────────────────────

function ColumnRow({ name, info, onChartRequest, isSelected }) {
  const card = CARDINALITY[info.cardinality] || CARDINALITY.freetext;
  const hasFreq = info.frequencies?.length > 0;
  const hasNumeric = info.min !== undefined;
  const hasDate = info.min_date !== undefined;
  const isChartable = info.cardinality === "numeric" || info.cardinality === "categorical";

  return (
    <>
      <tr
        className={`col-row ${isChartable ? "col-row--expandable" : ""} ${isSelected ? "col-row--selected" : ""}`}
        onClick={() => isChartable && onChartRequest(name)}
        title={isChartable ? `Click to chart ${name}` : ""}
      >
        <td className="col-name">
          {name}
          {isChartable && <BarChart2 size={10} className="col-chart-hint" />}
        </td>
        <td>
          <span className="cardinality-badge" style={{ color: card.color, background: card.bg }} title={card.tip}>
            {card.icon} {card.label}
          </span>
        </td>
        <td className="col-dtype">{info.dtype}</td>
        <td>
          {info.null_pct === 0
            ? <span className="badge badge-green">No nulls</span>
            : info.null_pct < 5
              ? <span className="badge badge-yellow">{info.null_pct}% nulls</span>
              : <span className="badge badge-red">{info.null_pct}% nulls</span>}
        </td>
        <td className="col-unique">{info.unique_count?.toLocaleString()}</td>
        <td className="col-extra">
          {hasNumeric && <span className="col-stat">μ {info.mean}</span>}
          {info.outlier_count > 0 && <span className="badge badge-yellow">{info.outlier_count} outliers</span>}
          {hasDate && <span className="col-stat">{info.min_date?.slice(0,10)} → {info.max_date?.slice(0,10)}</span>}
          {isChartable && <ChevronDown size={11} className="col-chevron" />}
        </td>
      </tr>

      {/* Inline frequency bars — always visible for categorical, no click needed */}
      {hasFreq && (
        <tr className="col-freq-row">
          <td colSpan={6}>
            <FrequencyBars frequencies={info.frequencies} />
          </td>
        </tr>
      )}

      {/* Numeric stats inline */}
      {hasNumeric && (
        <tr className="col-freq-row">
          <td colSpan={6}>
            <div className="num-stats">
              <span>Min <strong>{info.min}</strong></span>
              <span>Max <strong>{info.max}</strong></span>
              <span>Mean <strong>{info.mean}</strong></span>
              <span>Median <strong>{info.median}</strong></span>
              <span>Std <strong>{info.std}</strong></span>
              {info.outlier_count > 0 && <span className="outlier-note">⚠️ {info.outlier_count} outliers detected (3σ)</span>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Table card ────────────────────────────────────────────────────────────────

function TableCard({ tableName, profile, sessionId }) {
  const [charts, setCharts]           = useState({});
  const [loadingChart, setLoading]    = useState(false);
  const [selectedCol, setSelectedCol] = useState(null);
  const [showCorr, setShowCorr]       = useState(false);
  const [showNull, setShowNull]       = useState(false);
  const [chartsLoaded, setChartsLoaded] = useState(false);

  // Load default charts on first expand
  const loadDefaultCharts = useCallback(async () => {
    if (chartsLoaded) return;
    setLoading(true);
    try {
      const result = await getTableCharts(sessionId, tableName);
      setCharts(result.charts || {});
      setChartsLoaded(true);
    } catch (e) {
      console.error("Chart load failed", e);
    } finally {
      setLoading(false);
    }
  }, [sessionId, tableName, chartsLoaded]);

  // Load chart for specific column
  const handleChartRequest = async (colName) => {
    if (selectedCol === colName) {
      setSelectedCol(null);
      return;
    }
    setSelectedCol(colName);
    setLoading(true);
    try {
      const result = await getTableCharts(sessionId, tableName, colName);
      setCharts((prev) => ({ ...prev, selected: result.charts?.selected, ...(!chartsLoaded ? result.charts : {}) }));
      setChartsLoaded(true);
    } catch (e) {
      console.error("Chart load failed", e);
    } finally {
      setLoading(false);
    }
  };

  // Load default charts on mount
  useEffect(() => { loadDefaultCharts(); }, [loadDefaultCharts]);

  const dupPct = profile.duplicate_rows
    ? ((profile.duplicate_rows / profile.row_count) * 100).toFixed(1) : 0;
  const nullCols = Object.values(profile.columns || {}).filter(c => c.null_pct > 0).length;
  const outlierCols = Object.values(profile.columns || {}).filter(c => c.outlier_count > 0).length;

  // Which chart to show in main slot
  const mainChart = selectedCol ? charts.selected : (charts.auto);
  const hasCorr = !!charts.correlation;
  const hasNull = !!charts.nullmap;

  return (
    <div className="table-card">

      {/* Header */}
      <div className="table-card-header">
        <div className="table-card-title"><Database size={15} /><span>{tableName}</span></div>
        <div className="table-card-meta">
          {profile.row_count?.toLocaleString()} rows &nbsp;·&nbsp; {profile.column_count} columns
        </div>
      </div>

      {/* Quality strip */}
      <div className="quality-row">
        {profile.duplicate_rows > 0
          ? <div className="quality-item quality-warn"><AlertTriangle size={11} /> {profile.duplicate_rows} duplicates ({dupPct}%)</div>
          : <div className="quality-item quality-ok"><CheckCircle size={11} /> No duplicates</div>}
        {nullCols > 0
          ? <div className="quality-item quality-warn"><AlertTriangle size={11} /> {nullCols} columns with nulls</div>
          : <div className="quality-item quality-ok"><CheckCircle size={11} /> No nulls</div>}
        {outlierCols > 0 && (
          <div className="quality-item quality-warn"><AlertTriangle size={11} /> {outlierCols} columns with outliers</div>)}
      </div>

      {/* Main chart area */}
      <div className="chart-section">
        {loadingChart && (
          <div className="chart-loading">
            <Loader size={16} className="spin" />
            <span>Loading chart{selectedCol ? ` for ${selectedCol}` : ""}...</span>
          </div>
        )}
        {!loadingChart && mainChart && (
          <>
            {selectedCol && (
              <div className="chart-col-label">
                Showing: <strong>{selectedCol}</strong>
                <button className="chart-reset-btn" onClick={() => setSelectedCol(null)}>Reset to default</button>
              </div>
            )}
            <InlineChart chartJson={mainChart} height={240} />
          </>
        )}
        {!loadingChart && !mainChart && chartsLoaded && (
          <div className="chart-empty">Click any 📊 Numeric or 📦 Categorical column to generate a chart</div>
        )}
      </div>

      {/* Heatmap toggles */}
      {(hasCorr || hasNull) && (
        <div className="heatmap-toggles">
          {hasCorr && (
            <button className={`heatmap-btn ${showCorr ? "heatmap-btn--active" : ""}`}
              onClick={() => setShowCorr(!showCorr)}>
              {showCorr ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Correlation Heatmap
            </button>
          )}
          {hasNull && (
            <button className={`heatmap-btn ${showNull ? "heatmap-btn--active" : ""}`}
              onClick={() => setShowNull(!showNull)}>
              {showNull ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Missing Value Map
            </button>
          )}
          {!hasCorr && chartsLoaded && (
            <span className="heatmap-na">Correlation heatmap needs 2+ numeric columns</span>
          )}
          {!hasNull && chartsLoaded && (
            <span className="heatmap-na">No missing values detected ✅</span>
          )}
        </div>
      )}

      {showCorr && <div className="chart-section"><InlineChart chartJson={charts.correlation} height={Math.max(240, Object.keys(profile.columns).length * 40 + 80)} /></div>}
      {showNull && <div className="chart-section"><InlineChart chartJson={charts.nullmap} height={260} /></div>}

      {/* Column table */}
      <div className="col-table-wrap">
        <table className="col-table">
          <thead>
            <tr>
              <th>Column <span className="th-hint">click 📊/📦 to chart</span></th>
              <th>Kind</th>
              <th>Type</th>
              <th>Nulls</th>
              <th>Unique</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(profile.columns || {}).map(([name, info]) => (
              <ColumnRow
                key={name} name={name} info={info}
                onChartRequest={handleChartRequest}
                isSelected={selectedCol === name}
              />
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}

// ── Cardinality Legend ────────────────────────────────────────────────────────

function CardinalityLegend() {
  const [open, setOpen] = useState(false);
  return (
    <div className="legend-box">
      <button className="legend-toggle" onClick={() => setOpen(!open)}>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        Column Kind Legend — what do these labels mean?
      </button>
      {open && (
        <div className="legend-grid">
          {LEGEND_ITEMS.map(([key, cfg]) => (
            <div key={key} className="legend-item">
              <span className="cardinality-badge" style={{ color: cfg.color, background: cfg.bg }}>
                {cfg.icon} {cfg.label}
              </span>
              <span className="legend-tip">{cfg.tip}</span>
            </div>
          ))}
          <div className="legend-rules">
            <strong>Rules of thumb:</strong>
            <ul>
              <li>🔑 ID columns — never aggregate, use only for joins or filters</li>
              <li>📊 Numeric — SUM, AVG, MIN, MAX, COUNT — your core KPI columns</li>
              <li>📦 Categorical — GROUP BY, WHERE, filters, breakdowns</li>
              <li>📝 Free text — skip for BI, useful only for search or NLP</li>
              <li>📅 Date — always your time axis for trend analysis</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function SchemaCards({ profiles, relationships, sessionId }) {
  if (!profiles) return null;

  return (
    <div className="schema-section">
      <h2 className="section-title"><Database size={14} /> Data Profile</h2>

      <CardinalityLegend />

      {/* Relationships */}
      {relationships?.relationships?.length > 0 && (
        <div className="relationships-box">
          <p className="rel-title">🔗 Relationships Detected</p>
          {relationships.relationships.map((r, i) => (
            <div key={i} className="rel-item">
              <span className="rel-tables">{r.from_table} → {r.to_table}</span>
              <span className="rel-col">via {r.join_column}</span>
              <span className={`badge ${r.match_pct > 90 ? "badge-green" : "badge-yellow"}`}>{r.match_pct}% match</span>
              {(r.orphaned_in_t1 > 0 || r.orphaned_in_t2 > 0) && (
                <span className="badge badge-red">{r.orphaned_in_t1 + r.orphaned_in_t2} orphaned</span>)}
              <span className="rel-join">{r.suggested_join}</span>
            </div>
          ))}
        </div>
      )}

      {Object.entries(profiles).map(([name, profile]) => (
        <TableCard key={name} tableName={name} profile={profile} sessionId={sessionId} />
      ))}
    </div>
  );
}
