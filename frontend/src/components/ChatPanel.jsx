import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Loader, Bot, User, ChevronDown, ChevronUp, Code, Trash2, PlusCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { sendChat, getChatHistory, clearChatHistory, addFilesToSession } from "../utils/api";
import ChartPanel from "./ChartPanel";
import { useDropzone } from "react-dropzone";

const SUGGESTED_PROMPTS = [
  "Profile all tables and show data quality",
  "Find anomalies and outliers across all tables",
  "Detect relationships between tables",
  "Suggest what BI metrics we should build from this data",
  "Show the distribution of numeric columns",
  "Compare tables and flag differences",
];

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
  "application/octet-stream": [".parquet"],
  "application/json": [".json"],
};

// ── Add files mini-dropzone ───────────────────────────────────────────────────

function AddFilesDropzone({ sessionId, onFilesAdded }) {
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (!acceptedFiles.length) return;
    setLoading(true);
    try {
      const result = await addFilesToSession(sessionId, acceptedFiles);
      onFilesAdded(result);
      setShow(false);
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to add files");
    } finally {
      setLoading(false);
    }
  }, [sessionId, onFilesAdded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: ACCEPTED, multiple: true,
  });

  if (!show) {
    return (
      <button className="add-files-btn" onClick={() => setShow(true)}>
        <PlusCircle size={13} /> Add more files
      </button>
    );
  }

  return (
    <div className="add-files-zone">
      <div
        {...getRootProps()}
        className={`add-dropzone ${isDragActive ? "add-dropzone--active" : ""}`}
      >
        <input {...getInputProps()} />
        {loading
          ? <span><Loader size={12} className="spin" /> Adding files...</span>
          : <span>{isDragActive ? "Drop files here" : "Drop files or click to browse"}</span>
        }
      </div>
      <button className="add-files-cancel" onClick={() => setShow(false)}>Cancel</button>
    </div>
  );
}

// ── Single message ────────────────────────────────────────────────────────────

function Message({ msg }) {
  const [showSql, setShowSql] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="msg-avatar"><User size={14} /></div>
        <div className="msg-bubble msg-bubble-user">{msg.content}</div>
      </div>
    );
  }

  // System message (file added notification)
  if (msg.role === "system") {
    return (
      <div className="msg-system">
        <PlusCircle size={12} /> {msg.content}
      </div>
    );
  }

  return (
    <div className="msg msg-assistant">
      <div className="msg-avatar msg-avatar-bot"><Bot size={14} /></div>
      <div className="msg-content">

        {msg.narrative && (
          <div className="msg-narrative">
            <ReactMarkdown>{msg.narrative}</ReactMarkdown>
          </div>
        )}

        {msg.charts?.length > 0 && (
          <div className="msg-charts">
            {msg.charts.map((chartJson, i) => (
              <ChartPanel key={i} chartJson={chartJson} />
            ))}
          </div>
        )}

        {msg.anomalies && Object.entries(msg.anomalies).map(([table, result]) =>
          result.anomaly_count > 0 ? (
            <div key={table} className="anomaly-table">
              <p className="anomaly-table-name">⚠️ {table}: {result.anomaly_count} anomalies</p>
              {result.anomalies.map((a, i) => (
                <div key={i} className="anomaly-item">
                  <span className="anomaly-type">{a.type}</span>
                  <span className="anomaly-col">{a.column}</span>
                  <span className="anomaly-count">{a.count} rows</span>
                </div>
              ))}
            </div>
          ) : null
        )}

        {msg.metric_suggestions?.suggestions?.length > 0 && (
          <div className="metrics-list">
            <p className="metrics-title">📊 Suggested Metrics</p>
            {msg.metric_suggestions.suggestions.map((s, i) => (
              <div key={i} className="metric-item">
                <p className="metric-name">{s.metric}</p>
                <p className="metric-desc">{s.description}</p>
              </div>
            ))}
          </div>
        )}

        {msg.sql_result?.success && msg.sql_result.data?.length > 0 && (
          <div className="sql-result-table">
            <table>
              <thead>
                <tr>{msg.sql_result.columns?.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {msg.sql_result.data.slice(0, 10).map((row, i) => (
                  <tr key={i}>
                    {msg.sql_result.columns?.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            {msg.sql_result.row_count > 10 && (
              <p className="table-note">Showing 10 of {msg.sql_result.row_count} rows</p>
            )}
          </div>
        )}

        {msg.generated_sql && (
          <div className="code-block">
            <button className="code-toggle" onClick={() => setShowSql(!showSql)}>
              <Code size={12} /> SQL Query
              {showSql ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showSql && (
              <SyntaxHighlighter language="sql" style={oneLight} customStyle={{ fontSize: 11, margin: 0 }}>
                {msg.generated_sql}
              </SyntaxHighlighter>
            )}
          </div>
        )}

        {msg.error && <div className="msg-error">⚠️ {msg.error}</div>}
      </div>
    </div>
  );
}

// ── Main ChatPanel ────────────────────────────────────────────────────────────

export default function ChatPanel({ sessionId, tables, onTablesUpdated }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const bottomRef = useRef(null);

  // Load history on mount
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const data = await getChatHistory(sessionId);
        if (data.messages.length > 0) {
          setMessages(data.messages);
        } else {
          setMessages([{
            role: "assistant",
            narrative: "ATLAS EDA is ready. Your data has been loaded and profiled. Ask me anything about your data — I can find anomalies, detect relationships, generate charts, suggest metrics, and more.",
          }]);
        }
      } catch {
        setMessages([{
          role: "assistant",
          narrative: "ATLAS EDA is ready. Ask me anything about your data.",
        }]);
      } finally {
        setHistoryLoading(false);
      }
    };
    loadHistory();
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (prompt) => {
    if (!prompt.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setInput("");
    setLoading(true);
    try {
      const result = await sendChat(sessionId, prompt);
      setMessages((prev) => [...prev, { role: "assistant", ...result }]);
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: "assistant",
        error: e.response?.data?.detail || "Something went wrong.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm("Clear all chat history for this session?")) return;
    await clearChatHistory(sessionId);
    setMessages([{
      role: "assistant",
      narrative: "Chat history cleared. Ask me anything about your data.",
    }]);
  };

  const handleFilesAdded = (result) => {
    // Notify parent to update table chips
    if (onTablesUpdated) onTablesUpdated(result);
    // Add system message to chat
    setMessages((prev) => [...prev, {
      role: "system",
      content: `Added ${result.new_tables.length} new table(s): ${result.new_tables.map(t => t.table_name).join(", ")}. You can now ask questions about these tables.`,
    }]);
  };

  if (historyLoading) {
    return (
      <div className="chat-panel" style={{ alignItems: "center", justifyContent: "center" }}>
        <Loader size={20} className="spin" />
        <span style={{ color: "var(--muted)", marginTop: 8, fontSize: 12 }}>Loading history...</span>
      </div>
    );
  }

  return (
    <div className="chat-panel">

      {/* Toolbar */}
      <div className="chat-toolbar">
        <AddFilesDropzone sessionId={sessionId} onFilesAdded={handleFilesAdded} />
        <button className="chat-tool-btn" onClick={handleClearHistory} title="Clear history">
          <Trash2 size={13} /> Clear history
        </button>
      </div>

      {/* Suggested prompts — only show if only welcome message */}
      {messages.length === 1 && (
        <div className="suggested-prompts">
          {SUGGESTED_PROMPTS.map((p) => (
            <button key={p} className="prompt-chip" onClick={() => send(p)}>{p}</button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}
        {loading && (
          <div className="msg msg-assistant">
            <div className="msg-avatar msg-avatar-bot"><Bot size={14} /></div>
            <div className="msg-thinking">
              <Loader size={14} className="spin" />
              <span>ATLAS is thinking...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-row">
        <input
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
          placeholder="Ask about your data..."
          disabled={loading}
        />
        <button className="btn btn-send" onClick={() => send(input)} disabled={loading || !input.trim()}>
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
