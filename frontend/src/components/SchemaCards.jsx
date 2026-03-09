import { useState } from "react";
import { Database, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from "lucide-react";
import Plot from "react-plotly.js";

// ── Cardinality config ────────────────────────────────────────────────────────

const CARDINALITY = {
  id:          { icon: "🔑", label: "ID",          color: "#7c3aed", bg: "rgba(124,58,237,0.08)"  },
  numeric:     { icon: "📊", label: "Numeric",      color: "#0284c7", bg: "rgba(2,132,199,0.08)"   },
  categorical: { icon: "📦", label: "Categorical",  color: "#059669", bg: "rgba(5,150,105,0.08)"   },
  freetext:    { icon: "📝", label: "Free text",    color: "#d97706", bg: "rgba(217,119,6,0.08)"   },
  date:        { icon: "📅", label: "Date",         color: "#db2777", bg: "rgba(219,39,119,0.08)"  },
};

// ── Plotly chart wrapper ──────────────────────────────────────────────────────

function InlineChart({ chartJson, height = 220 }) {
  if (!chartJson) return null;
  try {
    const data = typeof chartJson === "string" ? JSON.parse(chartJson) : chartJson;
    if (data.error) return null;
    return (
      <Plot
        data={data.data || []}
        layout={{
          ...(data.layout || {}),
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#f8fafc",
          font: { color: "#0f172a", family: "IBM Plex Sans, sans-serif", size: 11 },
          margin: { t: 36, r: 16, b: 48, l: 52 },
          height,
          autosize: true,
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    );
  } catch {
    return null;
  }
}

// ── Frequency bar ─────────────────────────────────────────────────────────────

function FrequencyBar({ value, pct }) {
  return (
    <div className="freq-row">
      <span className="freq-label">{value}</span>
      <div className="freq-bar-wrap">
        <div className="freq-bar" style={{ width: `${pct}%` }} />
      </div>
      <span className="freq-pct">{pct}%</span>
    </div>
  );
}

// ── Column row ────────────────────────────────────────────────────────────────

function ColumnRow({ name, info }) {
  const [expanded, setExpanded] = useState(false);
  const card = CARDINALITY[info.cardinality] || CARDINALITY.freetext;
  const hasFreq = info.frequencies?.length > 0;
  const hasNumeric = info.min !== undefined;
  const hasDate = info.min_date !== undefined;
  const canExpand = hasFreq || hasNumeric || hasDate;

  return (
    <>
      <tr
        className={`col-row ${canExpand ? "col-row--expandable" : ""}`}
        onClick={() => canExpand && setExpanded(!expanded)}
      >
        <td className="col-name">{name}</td>
        <td>
          <span className="cardinality-badge" style={{ color: card.color, background: card.bg }}>
            {card.icon} {card.label}
          </span>
        </td>
        <td className="col-dtype">{info.dtype}</td>
        <td>
          {info.null_pct === 0
            ? <span className="badge badge-green">No nulls</span>
            : info.null_pct < 5
              ? <span className="badge badge-yellow">{info.null_pct}% nulls</span>
              : <span className="badge badge-red">{info.null_pct}% nulls</span>
          }
        </td>
        <td className="col-unique">{info.unique_count?.toLocaleString()}</td>
        <td className="col-extra">
          {hasNumeric && <span className="col-stat">μ {info.mean}</span>}
          {info.outlier_count > 0 && <span className="badge badge-yellow">{info.outlier_count} outliers</span>}
          {hasDate && <span className="col-stat">{info.min_date?.slice(0,10)} → {info.max_date?.slice(0,10)}</span>}
          {canExpand && (
            <span className="expand-icon">
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </span>
          )}
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && canExpand && (
        <tr className="col-detail-row">
          <td colSpan={6}>
            <div className="col-detail">
              {/* Frequency bars */}
              {hasFreq && (
                <div className="freq-list">
                  {info.frequencies.map((f) => (
                    <FrequencyBar key={f.value} value={f.value} pct={f.pct} />
                  ))}
                </div>
              )}
              {/* Numeric stats */}
              {hasNumeric && (
                <div className="num-stats">
                  <span>Min <strong>{info.min}</strong></span>
                  <span>Max <strong>{info.max}</strong></span>
                  <span>Mean <strong>{info.mean}</strong></span>
                  <span>Median <strong>{info.median}</strong></span>
                  <span>Std <strong>{info.std}</strong></span>
                </div>
              )}
              {/* Date info */}
              {hasDate && (
                <div className="num-stats">
                  <span>From <strong>{info.min_date?.slice(0,10)}</strong></span>
                  <span>To <strong>{info.max_date?.slice(0,10)}</strong></span>
                  <span>Span <strong>{info.date_range_days} days</strong></span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Table card ────────────────────────────────────────────────────────────────

function TableCard({ tableName, profile }) {
  const [showCorr, setShowCorr] = useState(false);
  const [showNull, setShowNull] = useState(false);

  const dupPct = profile.duplicate_rows
    ? ((profile.duplicate_rows / profile.row_count) * 100).toFixed(1)
    : 0;

  const nullCols = Object.values(profile.columns || {}).filter(c => c.null_pct > 0).length;
  const outlierCols = Object.values(profile.columns || {}).filter(c => c.outlier_count > 0).length;

  return (
    <div className="table-card">

      {/* Header */}
      <div className="table-card-header">
        <div className="table-card-title">
          <Database size={15} />
          <span>{tableName}</span>
        </div>
        <div className="table-card-meta">
          {profile.row_count?.toLocaleString()} rows &nbsp;·&nbsp; {profile.column_count} columns
        </div>
      </div>

      {/* Quality strip */}
      <div className="quality-row">
        {profile.duplicate_rows > 0
          ? <div className="quality-item quality-warn"><AlertTriangle size={11} /> {profile.duplicate_rows} duplicates ({dupPct}%)</div>
          : <div className="quality-item quality-ok"><CheckCircle size={11} /> No duplicates</div>
        }
        {nullCols > 0
          ? <div className="quality-item quality-warn"><AlertTriangle size={11} /> {nullCols} columns with nulls</div>
          : <div className="quality-item quality-ok"><CheckCircle size={11} /> No nulls</div>
        }
        {outlierCols > 0 && (
          <div className="quality-item quality-warn"><AlertTriangle size={11} /> {outlierCols} columns with outliers</div>
        )}
      </div>

      {/* Auto chart */}
      {profile.charts?.auto && (
        <div className="chart-section">
          <InlineChart chartJson={profile.charts.auto} height={220} />
        </div>
      )}

      {/* Heatmap toggles */}
      {(profile.charts?.correlation || profile.charts?.nullmap) && (
        <div className="heatmap-toggles">
          {profile.charts?.correlation && (
            <button
              className={`heatmap-btn ${showCorr ? "heatmap-btn--active" : ""}`}
              onClick={() => setShowCorr(!showCorr)}
            >
              {showCorr ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Correlation Matrix
            </button>
          )}
          {profile.charts?.nullmap && (
            <button
              className={`heatmap-btn ${showNull ? "heatmap-btn--active" : ""}`}
              onClick={() => setShowNull(!showNull)}
            >
              {showNull ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Missing Value Map
            </button>
          )}
        </div>
      )}

      {showCorr && profile.charts?.correlation && (
        <div className="chart-section">
          <InlineChart chartJson={profile.charts.correlation} height={Math.max(220, Object.keys(profile.columns).length * 40 + 80)} />
        </div>
      )}

      {showNull && profile.charts?.nullmap && (
        <div className="chart-section">
          <InlineChart chartJson={profile.charts.nullmap} height={240} />
        </div>
      )}

      {/* Column table */}
      <div className="col-table-wrap">
        <table className="col-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>Kind</th>
              <th>Type</th>
              <th>Nulls</th>
              <th>Unique</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(profile.columns || {}).map(([name, info]) => (
              <ColumnRow key={name} name={name} info={info} />
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function SchemaCards({ profiles, relationships }) {
  if (!profiles) return null;

  return (
    <div className="schema-section">
      <h2 className="section-title"><Database size={14} /> Data Profile</h2>

      {/* Relationships */}
      {relationships?.relationships?.length > 0 && (
        <div className="relationships-box">
          <p className="rel-title">🔗 Relationships Detected</p>
          {relationships.relationships.map((r, i) => (
            <div key={i} className="rel-item">
              <span className="rel-tables">{r.from_table} → {r.to_table}</span>
              <span className="rel-col">via {r.join_column}</span>
              <span className={`badge ${r.match_pct > 90 ? "badge-green" : "badge-yellow"}`}>
                {r.match_pct}% match
              </span>
              {(r.orphaned_in_t1 > 0 || r.orphaned_in_t2 > 0) && (
                <span className="badge badge-red">
                  {r.orphaned_in_t1 + r.orphaned_in_t2} orphaned
                </span>
              )}
              <span className="rel-join">{r.suggested_join}</span>
            </div>
          ))}
        </div>
      )}

      {Object.entries(profiles).map(([name, profile]) => (
        <TableCard key={name} tableName={name} profile={profile} />
      ))}
    </div>
  );
}
