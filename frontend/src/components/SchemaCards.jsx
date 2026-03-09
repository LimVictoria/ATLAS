import { Database, AlertTriangle, CheckCircle, Info } from "lucide-react";

function QualityBadge({ pct }) {
  if (pct === 0) return <span className="badge badge-green">No nulls</span>;
  if (pct < 5)   return <span className="badge badge-yellow">{pct}% nulls</span>;
  return           <span className="badge badge-red">{pct}% nulls</span>;
}

function ColumnRow({ name, info }) {
  return (
    <tr className="col-row">
      <td className="col-name">{name}</td>
      <td className="col-dtype">{info.dtype}</td>
      <td><QualityBadge pct={info.null_pct} /></td>
      <td className="col-unique">{info.unique_count?.toLocaleString()}</td>
      <td className="col-sample">
        {(info.sample_values || []).slice(0, 2).map(String).join(", ")}
      </td>
    </tr>
  );
}

function TableCard({ tableName, profile }) {
  const dupPct = profile.duplicate_rows
    ? ((profile.duplicate_rows / profile.row_count) * 100).toFixed(1)
    : 0;

  const totalNullCols = Object.values(profile.columns || {}).filter(
    (c) => c.null_pct > 0
  ).length;

  const totalOutlierCols = Object.values(profile.columns || {}).filter(
    (c) => c.outlier_count > 0
  ).length;

  return (
    <div className="table-card">
      {/* Header */}
      <div className="table-card-header">
        <div className="table-card-title">
          <Database size={16} />
          <span>{tableName}</span>
        </div>
        <div className="table-card-meta">
          <span>{profile.row_count?.toLocaleString()} rows</span>
          <span>·</span>
          <span>{profile.column_count} columns</span>
        </div>
      </div>

      {/* Quality summary */}
      <div className="quality-row">
        {profile.duplicate_rows > 0 ? (
          <div className="quality-item quality-warn">
            <AlertTriangle size={12} />
            {profile.duplicate_rows} duplicates ({dupPct}%)
          </div>
        ) : (
          <div className="quality-item quality-ok">
            <CheckCircle size={12} />
            No duplicates
          </div>
        )}
        {totalNullCols > 0 ? (
          <div className="quality-item quality-warn">
            <AlertTriangle size={12} />
            {totalNullCols} columns with nulls
          </div>
        ) : (
          <div className="quality-item quality-ok">
            <CheckCircle size={12} />
            No nulls
          </div>
        )}
        {totalOutlierCols > 0 && (
          <div className="quality-item quality-warn">
            <Info size={12} />
            {totalOutlierCols} columns with outliers
          </div>
        )}
      </div>

      {/* Column table */}
      <div className="col-table-wrap">
        <table className="col-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>Type</th>
              <th>Nulls</th>
              <th>Unique</th>
              <th>Sample</th>
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

export default function SchemaCards({ profiles, relationships }) {
  if (!profiles) return null;

  return (
    <div className="schema-section">
      <h2 className="section-title">
        <Database size={16} />
        Data Profile
      </h2>

      {/* Relationships */}
      {relationships?.relationships?.length > 0 && (
        <div className="relationships-box">
          <p className="rel-title">🔗 Relationships Detected</p>
          {relationships.relationships.map((r, i) => (
            <div key={i} className="rel-item">
              <span className="rel-tables">
                {r.from_table} → {r.to_table}
              </span>
              <span className="rel-col">via {r.join_column}</span>
              <span className={`badge ${r.match_pct > 90 ? "badge-green" : "badge-yellow"}`}>
                {r.match_pct}% match
              </span>
              {r.orphaned_in_t1 > 0 && (
                <span className="badge badge-red">
                  {r.orphaned_in_t1} orphaned
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Table cards */}
      {Object.entries(profiles).map(([name, profile]) => (
        <TableCard key={name} tableName={name} profile={profile} />
      ))}
    </div>
  );
}
