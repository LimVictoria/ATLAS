import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileText, Loader, AlertCircle } from "lucide-react";
import { uploadFiles } from "../utils/api";

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
  "application/octet-stream": [".parquet"],
  "application/json": [".json"],
};

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export default function FileUpload({ onUploadSuccess }) {
  const [files, setFiles]         = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [progress, setProgress]   = useState(0);
  const [statusMsg, setStatusMsg] = useState("");

  const onDrop = useCallback((accepted) => {
    setError(null);
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      const newFiles = accepted.filter((f) => !existing.has(f.name));
      return [...prev, ...newFiles];
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
  });

  const removeFile = (name) => setFiles((prev) => prev.filter((f) => f.name !== name));

  const handleUpload = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setProgress(0);
    setStatusMsg(`Uploading ${files.length} file${files.length > 1 ? "s" : ""}...`);

    try {
      const result = await uploadFiles(files, (pct) => {
        setProgress(pct);
        if (pct === 100) setStatusMsg("Processing files on server...");
      });

      if (result.errors?.length > 0 && result.tables?.length === 0) {
        setError(`All files failed: ${result.errors.map(e => e.error).join(", ")}`);
        return;
      }

      if (result.errors?.length > 0) {
        setStatusMsg(`Loaded ${result.tables.length} file(s). ${result.errors.length} skipped.`);
      }

      onUploadSuccess(result);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || "Upload failed";
      setError(msg);
    } finally {
      setLoading(false);
      setProgress(0);
    }
  };

  return (
    <div className="upload-screen">
      <div className="upload-hero">
        <h1>ATLAS <span>EDA</span></h1>
        <p>Upload your logistics data files to begin exploration.<br />
          Supports CSV, Excel, Parquet, and JSON. Multiple files welcome.</p>
        <p className="upload-formats">CSV · XLSX · XLS · PARQUET · JSON</p>
      </div>

      <div className="upload-container">
        <div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? "dropzone--active" : ""}`}
        >
          <input {...getInputProps()} />
          <Upload size={32} className="dropzone-icon" />
          <p className="dropzone-title">
            {isDragActive ? "Drop files here" : "Drag & drop files or click to browse"}
          </p>
          <p className="dropzone-sub">Select one file or up to 20 files at once</p>
        </div>

        {files.length > 0 && (
          <div className="file-list">
            {files.map((f) => (
              <div key={f.name} className="file-item">
                <FileText size={13} color="var(--accent)" />
                <span className="file-name">{f.name}</span>
                <span className="file-size">{formatBytes(f.size)}</span>
                {!loading && (
                  <button className="file-remove" onClick={() => removeFile(f.name)}>
                    <X size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Progress bar */}
        {loading && (
          <div className="upload-progress-wrap">
            <div className="upload-progress-bar">
              <div
                className="upload-progress-fill"
                style={{ width: progress > 0 ? `${progress}%` : "100%" }}
              />
            </div>
            <div className="upload-status">
              <Loader size={12} className="spin" />
              <span>{statusMsg}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="upload-error">
            <AlertCircle size={13} /> {error}
          </div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!files.length || loading}
        >
          {loading
            ? <><Loader size={14} className="spin" /> Processing...</>
            : <><Upload size={14} /> Analyse {files.length > 0 ? `${files.length} file${files.length > 1 ? "s" : ""}` : "files"}</>
          }
        </button>
      </div>
    </div>
  );
}
