import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { fetchComparison, fetchRun, fetchSamples } from "../api.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Legend, Tooltip);

const wrapperStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

const cardGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "1rem",
};

const cardStyle = {
  backgroundColor: "#fff",
  padding: "1rem 1.25rem",
  borderRadius: "0.75rem",
  boxShadow: "0 10px 25px rgba(31, 41, 51, 0.08)",
};

export default function RunDetail() {
  const { id } = useParams();
  const [run, setRun] = useState(null);
  const [samples, setSamples] = useState([]);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [runDetail, sampleResponse] = await Promise.all([fetchRun(id), fetchSamples(id)]);
        if (mounted) {
          setRun(runDetail);
          setSamples(sampleResponse.samples);
        }
      } catch (err) {
        console.error(err);
        if (mounted) {
          setError("Koşu detayları alınamadı.");
        }
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [id]);

  useEffect(() => {
    let mounted = true;
    async function loadComparison() {
      try {
        const comparison = await fetchComparison(id, "latest-success");
        if (mounted) {
          setMessages(comparison.messages || []);
        }
      } catch (err) {
        console.warn("Karşılaştırma bilgisi alınamadı:", err?.response?.data || err.message);
        if (mounted) {
          setMessages([]);
        }
      }
    }
    loadComparison();
    return () => {
      mounted = false;
    };
  }, [id]);

  const cpuChartData = useMemo(() => buildChartData(samples, "cpu_percent", "CPU %"), [samples]);
  const ramChartData = useMemo(() => buildChartData(samples, "rss_mb", "RAM (MB)"), [samples]);

  if (error) {
    return <div>{error}</div>;
  }

  if (!run) {
    return <div>Yükleniyor...</div>;
  }

  const stats = run.stats || {};

  return (
    <div style={wrapperStyle}>
      <div>
        <h2 style={{ marginBottom: "0.5rem" }}>Koşu #{run.id}</h2>
        <div style={{ color: "#52606d" }}>{run.command}</div>
      </div>
      <div style={cardGridStyle}>
        <StatCard label="Süre (s)" value={formatNumber(stats.duration_s)} />
        <StatCard label="Ort. CPU (%)" value={formatNumber(stats.avg_cpu)} />
        <StatCard label="P95 CPU (%)" value={formatNumber(stats.p95_cpu)} />
        <StatCard label="Max CPU (%)" value={formatNumber(stats.max_cpu)} />
        <StatCard label="Ort. RAM (MB)" value={formatNumber(stats.avg_rss_mb)} />
        <StatCard label="P95 RAM (MB)" value={formatNumber(stats.p95_rss_mb)} />
        <StatCard label="Max RAM (MB)" value={formatNumber(stats.max_rss_mb)} />
      </div>
      <div style={{ display: "grid", gap: "1.5rem", gridTemplateColumns: "2fr 1fr" }}>
        <div style={{ display: "grid", gap: "1.5rem" }}>
          <ChartCard title="CPU Kullanımı">
            <Line data={cpuChartData} options={lineOptions("CPU %")} />
          </ChartCard>
          <ChartCard title="RAM Kullanımı">
            <Line data={ramChartData} options={lineOptions("RAM (MB)")} />
          </ChartCard>
        </div>
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>AI Yorumu</h3>
          {messages.length === 0 ? (
            <p>Karşılaştırma verisi bulunamadı.</p>
          ) : (
            <ul style={{ paddingLeft: "1rem" }}>
              {messages.map((msg, index) => (
                <li
                  key={index}
                  style={{ marginBottom: "0.5rem" }}
                  dangerouslySetInnerHTML={{ __html: formatMessage(msg) }}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div style={cardStyle}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <div style={{ height: "280px" }}>{children}</div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: "0.9rem", color: "#52606d" }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 600, marginTop: "0.5rem" }}>{value ?? "-"}</div>
    </div>
  );
}

function buildChartData(samples, key, label) {
  const labels = samples.map((sample) => new Date(sample.ts * 1000).toLocaleTimeString());
  const dataset = samples.map((sample) => sample[key]);
  return {
    labels,
    datasets: [
      {
        label,
        data: dataset,
        borderColor: key === "cpu_percent" ? "#2563eb" : "#f97316",
        backgroundColor: "rgba(37, 99, 235, 0.1)",
        tension: 0.25,
        fill: false,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };
}

function lineOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        ticks: { color: "#334155" },
      },
      y: {
        title: { display: true, text: yLabel },
        ticks: { color: "#334155" },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        mode: "index",
        intersect: false,
      },
    },
  };
}

function formatNumber(value) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(1);
}

function formatMessage(message) {
  if (!message) {
    return "";
  }
  return message.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
}
