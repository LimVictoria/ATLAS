import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, X, Loader } from "lucide-react";
import { uploadFiles } from "../utils/api";

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
  "application/octet-stream": [".parquet"],
  "application/json": [".json"],
};

export default function FileUpload({ onUploadSuccess }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const onDrop = useCallback((accepted) => {
    setFiles((prev) => [...prev, ...accepted]);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
  });

  const removeFile = (name) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadFiles(files);
      onUploadSuccess(result);
    } catch (e) {
      setError(e.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-container">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? "dropzone--active" : ""}`}
      >
        <input {...getInputProps()} />
        <Upload size={40} className="dropzone-icon" />
        <p className="dropzone-title">
          {isDragActive ? "Drop files here" : "Upload your data files"}
        </p>
        <p className="dropzone-sub">
          Drag & drop a folder or individual files · CSV, Excel, Parquet, JSON
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="file-list">
          {files.map((f) => (
            <div key={f.name} className="file-item">
              <FileText size={14} />
              <span className="file-name">{f.name}</span>
              <span className="file-size">
                {(f.size / 1024).toFixed(1)} KB
              </span>
              <button
                className="file-remove"
                onClick={() => removeFile(f.name)}
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && <div className="upload-error">{error}</div>}

      {/* Upload button */}
      {files.length > 0 && (
        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader size={14} className="spin" />
              Analysing {files.length} file{files.length > 1 ? "s" : ""}...
            </>
          ) : (
            <>
              <Upload size={14} />
              Analyse {files.length} file{files.length > 1 ? "s" : ""}
            </>
          )}
        </button>
      )}
    </div>
  );
}
