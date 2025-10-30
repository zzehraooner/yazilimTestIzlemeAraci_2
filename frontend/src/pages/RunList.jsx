import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchRuns } from "../api.js";

const tableWrapperStyle = {
  backgroundColor: "#fff",
  borderRadius: "0.75rem",
  boxShadow: "0 10px 25px rgba(31, 41, 51, 0.08)",
  padding: "1.5rem",
};

export default function RunList() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const data = await fetchRuns();
        if (mounted) {
          setRuns(data);
        }
      } catch (err) {
        setError("Koşular yüklenemedi.");
        console.error(err);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <div>Yükleniyor...</div>;
  }

  if (error) {
    return <div>{error}</div>;
  }

  return (
    <div style={tableWrapperStyle}>
      <h2 style={{ marginTop: 0 }}>Son Koşular</h2>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Komut</th>
              <th>Başlangıç</th>
              <th>Durum</th>
              <th>Süre (s)</th>
              <th>Ort. CPU (%)</th>
              <th>P95 CPU (%)</th>
              <th>Ort. RAM (MB)</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                style={{ cursor: "pointer" }}
                onClick={() => navigate(`/runs/${run.id}`)}
              >
                <td>{run.id}</td>
                <td style={{ maxWidth: "260px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {run.command}
                </td>
                <td>{formatDate(run.started_at)}</td>
                <td>{statusLabel(run.status)}</td>
                <td>{run.stats?.duration_s ? run.stats.duration_s.toFixed(1) : "-"}</td>
                <td>{run.stats?.avg_cpu ? run.stats.avg_cpu.toFixed(1) : "-"}</td>
                <td>{run.stats?.p95_cpu ? run.stats.p95_cpu.toFixed(1) : "-"}</td>
                <td>{run.stats?.avg_rss_mb ? run.stats.avg_rss_mb.toFixed(1) : "-"}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={8}>Henüz koşu bulunmuyor.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function statusLabel(status) {
  switch (status) {
    case "completed":
      return "Tamamlandı";
    case "failed":
      return "Hatalı";
    case "running":
      return "Çalışıyor";
    default:
      return status;
  }
}
