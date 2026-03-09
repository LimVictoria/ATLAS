import { useState, useRef, useEffect } from "react";
import { Send, Loader, Bot, User, ChevronDown, ChevronUp, Code } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { sendChat } from "../utils/api";
import ChartPanel from "./ChartPanel";

const SUGGESTED_PROMPTS = [
  "Profile all tables and show data quality",
  "Find anomalies and outliers across all tables",
  "Detect relationships between tables",
  "Suggest what BI metrics we should build from this data",
  "Show the distribution of numeric columns",
  "Compare tables and flag differences",
];

function Message({ msg }) {
  const [showCode, setShowCode] = useState(false);
  const [showSql, setShowSql] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="msg-avatar"><User size={14} /></div>
        <div className="msg-bubble msg-bubble-user">{msg.content}</div>
      </div>
    );
  }

  return (
    <div className="msg msg-assistant">
      <div className="msg-avatar msg-avatar-bot"><Bot size={14} /></div>
      <div className="msg-content">

        {/* Narrative */}
        {msg.narrative && (
          <div className="msg-narrative">
            <ReactMarkdown>{msg.narrative}</ReactMarkdown>
          </div>
        )}

        {/* Charts */}
        {msg.charts?.length > 0 && (
          <div className="msg-charts">
            {msg.charts.map((chartJson, i) => (
              <ChartPanel key={i} chartJson={chartJson} />
            ))}
          </div>
        )}

        {/* Anomalies summary */}
        {msg.anomalies && (
          <div className="anomaly-summary">
            {Object.entries(msg.anomalies).map(([table, result]) =>
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
          </div>
        )}

        {/* Metric suggestions */}
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

        {/* SQL result table */}
        {msg.sql_result?.success && msg.sql_result.data?.length > 0 && (
          <div className="sql-result-table">
            <table>
              <thead>
                <tr>{msg.sql_result.columns?.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {msg.sql_result.data.slice(0, 10).map((row, i) => (
                  <tr key={i}>
                    {msg.sql_result.columns?.map((c) => (
                      <td key={c}>{String(row[c] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {msg.sql_result.row_count > 10 && (
              <p className="table-note">Showing 10 of {msg.sql_result.row_count} rows</p>
            )}
          </div>
        )}

        {/* Collapsible SQL */}
        {msg.generated_sql && (
          <div className="code-block">
            <button className="code-toggle" onClick={() => setShowSql(!showSql)}>
              <Code size={12} />
              SQL Query
              {showSql ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showSql && (
              <SyntaxHighlighter language="sql" style={oneDark} customStyle={{ fontSize: 11, margin: 0 }}>
                {msg.generated_sql}
              </SyntaxHighlighter>
            )}
          </div>
        )}

        {/* Error */}
        {msg.error && (
          <div className="msg-error">⚠️ {msg.error}</div>
        )}
      </div>
    </div>
  );
}

export default function ChatPanel({ sessionId, tables }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      narrative: "ATLAS EDA is ready. Your data has been loaded and profiled. Ask me anything about your data — I can find anomalies, detect relationships, generate charts, suggest metrics, and more.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (prompt) => {
    if (!prompt.trim() || loading) return;
    const userMsg = { role: "user", content: prompt };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendChat(sessionId, prompt);
      setMessages((prev) => [...prev, { role: "assistant", ...result }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", error: e.response?.data?.detail || "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-panel">
      {/* Suggested prompts */}
      {messages.length === 1 && (
        <div className="suggested-prompts">
          {SUGGESTED_PROMPTS.map((p) => (
            <button key={p} className="prompt-chip" onClick={() => send(p)}>
              {p}
            </button>
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
          placeholder="Ask about your data... (e.g. 'find anomalies in shipments table')"
          disabled={loading}
        />
        <button
          className="btn btn-send"
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
