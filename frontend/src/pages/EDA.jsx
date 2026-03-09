import { useState } from "react";
import { Database, MessageSquare, RefreshCw } from "lucide-react";
import FileUpload from "../components/FileUpload";
import SchemaCards from "../components/SchemaCards";
import ChatPanel from "../components/ChatPanel";
import { closeSession } from "../utils/api";

export default function EDAPage() {
  const [sessionData, setSessionData] = useState(null);
  const [activeTab, setActiveTab] = useState("profile");

  const handleUploadSuccess = (data) => {
    setSessionData(data);
    setActiveTab("profile");
  };

  const handleReset = async () => {
    if (sessionData?.session_id) {
      try { await closeSession(sessionData.session_id); } catch (_) {}
    }
    setSessionData(null);
  };

  return (
    <div className="eda-page">
      {/* Top bar */}
      <div className="topbar">
        <div className="topbar-left">
          <div className="atlas-logo">ATLAS</div>
          <span className="topbar-module">EDA Module</span>
        </div>
        {sessionData && (
          <button className="btn btn-ghost" onClick={handleReset}>
            <RefreshCw size={13} /> New Session
          </button>
        )}
      </div>

      {/* Upload screen */}
      {!sessionData && (
        <div className="upload-screen">
          <div className="upload-hero">
            <h1>Explore your logistics data</h1>
            <p>
              Upload one file or an entire folder. ATLAS will automatically
              profile your data, detect relationships, surface anomalies,
              and let you chat with an AI agent to explore further.
            </p>
          </div>
          <FileUpload onUploadSuccess={handleUploadSuccess} />
          <div className="upload-formats">
            Supported formats: CSV · Excel (.xlsx) · Parquet · JSON
          </div>
        </div>
      )}

      {/* Main workspace */}
      {sessionData && (
        <div className="workspace">
          {/* Session summary bar */}
          <div className="session-bar">
            {sessionData.tables.map((t) => (
              <div key={t.table_name} className="session-table-chip">
                <Database size={11} />
                <span>{t.table_name}</span>
                <span className="chip-meta">
                  {t.row_count.toLocaleString()} rows
                </span>
              </div>
            ))}
            {sessionData.errors?.length > 0 && (
              <span className="session-errors">
                ⚠️ {sessionData.errors.length} file(s) failed to load
              </span>
            )}
          </div>

          {/* Tabs */}
          <div className="tabs">
            <button
              className={`tab ${activeTab === "profile" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("profile")}
            >
              <Database size={13} /> Data Profile
            </button>
            <button
              className={`tab ${activeTab === "chat" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("chat")}
            >
              <MessageSquare size={13} /> AI Chat
            </button>
          </div>

          {/* Tab content */}
          <div className="tab-content">
            {activeTab === "profile" && (
              <SchemaCards
                profiles={sessionData.profiles}
                relationships={sessionData.relationships}
              />
            )}
            {activeTab === "chat" && (
              <ChatPanel
                sessionId={sessionData.session_id}
                tables={sessionData.tables}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
