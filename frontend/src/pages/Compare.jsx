import { useEffect, useMemo, useState } from "react";
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
import { fetchComparison, fetchRun, fetchRuns, fetchSamples } from "../api.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Legend, Tooltip);

const containerStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

const panelStyle = {
  backgroundColor: "#fff",
  borderRadius: "0.75rem",
  boxShadow: "0 10px 25px rgba(31, 41, 51, 0.08)",
  padding: "1.5rem",
};

export default function Compare() {
  const [runs, setRuns] = useState([]);
  const [currentId, setCurrentId] = useState("");
  const [baselineId, setBaselineId] = useState("");
  const [currentRun, setCurrentRun] = useState(null);
  const [baselineRun, setBaselineRun] = useState(null);
  const [currentSamples, setCurrentSamples] = useState([]);
  const [baselineSamples, setBaselineSamples] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadRuns() {
      const latestRuns = await fetchRuns();
      if (!mounted) return;
      setRuns(latestRuns);
      if (latestRuns.length > 0) {
        setCurrentId(String(latestRuns[0].id));
        setBaselineId(String(latestRuns[Math.min(1, latestRuns.length - 1)].id));
      }
      setLoading(false);
    }
    loadRuns().catch((err) => {
      console.error(err);
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!currentId || !baselineId) {
      return;
    }
    let cancelled = false;
    async function loadDetails() {
      try {
        const [currentDetail, baselineDetail, currentSample, baselineSample] = await Promise.all([
          fetchRun(currentId),
          fetchRun(baselineId),
          fetchSamples(currentId, { downsample: true, step: 2 }),
          fetchSamples(baselineId, { downsample: true, step: 2 }),
        ]);
        if (!cancelled) {
          setCurrentRun(currentDetail);
          setBaselineRun(baselineDetail);
          setCurrentSamples(currentSample.samples);
          setBaselineSamples(baselineSample.samples);
        }
      } catch (err) {
        console.error("Karşılaştırma detayları alınamadı", err);
      }
    }
    loadDetails();
    return () => {
      cancelled = true;
    };
  }, [currentId, baselineId]);

  useEffect(() => {
    if (!currentId || !baselineId) {
      return;
    }
    let cancelled = false;
    async function loadMessages() {
      try {
        const comparison = await fetchComparison(currentId, baselineId);
        if (!cancelled) {
          setMessages(comparison.messages || []);
        }
      } catch (err) {
        console.warn("Karşılaştırma API hatası", err);
        if (!cancelled) {
          setMessages([]);
        }
      }
    }
    loadMessages();
    return () => {
      cancelled = true;
    };
  }, [currentId, baselineId]);

  const cpuChart = useMemo(
    () => buildComparisonChart(currentSamples, baselineSamples, "cpu_percent", "% CPU"),
    [currentSamples, baselineSamples]
  );
  const ramChart = useMemo(
    () => buildComparisonChart(currentSamples, baselineSamples, "rss_mb", "RAM (MB)", "#f97316"),
    [currentSamples, baselineSamples]
  );

  if (loading) {
    return <div>Yükleniyor...</div>;
  }

  return (
    <div style={containerStyle}>
      <div style={panelStyle}>
        <h2 style={{ marginTop: 0 }}>Koşuları Karşılaştır</h2>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <Select
            label="Güncel koşu"
            value={currentId}
            options={runs}
            onChange={(event) => setCurrentId(event.target.value)}
          />
          <Select
            label="Baz koşu"
            value={baselineId}
            options={runs}
            onChange={(event) => setBaselineId(event.target.value)}
          />
        </div>
      </div>

      <div style={{ display: "grid", gap: "1.5rem", gridTemplateColumns: "2fr 1fr" }}>
        <div style={{ display: "grid", gap: "1.5rem" }}>
          <div style={panelStyle}>
            <h3 style={{ marginTop: 0 }}>CPU Kullanımı</h3>
            <div style={{ height: "280px" }}>
              <Line data={cpuChart.data} options={cpuChart.options} />
            </div>
          </div>
          <div style={panelStyle}>
            <h3 style={{ marginTop: 0 }}>RAM Kullanımı</h3>
            <div style={{ height: "280px" }}>
              <Line data={ramChart.data} options={ramChart.options} />
            </div>
          </div>
        </div>
        <div style={panelStyle}>
          <h3 style={{ marginTop: 0 }}>Metrik Özetleri</h3>
          <MetricSummary current={currentRun} baseline={baselineRun} />
          <h4>AI Yorumları</h4>
          {messages.length === 0 ? (
            <p>Karşılaştırma için yeterli veri bulunamadı.</p>
          ) : (
            <ul>
              {messages.map((msg, index) => (
                <li key={index} dangerouslySetInnerHTML={{ __html: formatMessage(msg) }} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Select({ label, value, options, onChange }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <span style={{ fontWeight: 600 }}>{label}</span>
      <select value={value} onChange={onChange} style={{ padding: "0.5rem", borderRadius: "0.5rem" }}>
        {options.map((run) => (
          <option key={run.id} value={run.id}>
            #{run.id} — {run.command.slice(0, 40)}
          </option>
        ))}
      </select>
    </label>
  );
}

function MetricSummary({ current, baseline }) {
  if (!current || !baseline) {
    return <p>Koşu verileri bekleniyor...</p>;
  }
  const metrics = [
    { key: "avg_cpu", label: "Ort. CPU (%)" },
    { key: "p95_cpu", label: "P95 CPU (%)" },
    { key: "max_cpu", label: "Max CPU (%)" },
    { key: "avg_rss_mb", label: "Ort. RAM (MB)" },
    { key: "p95_rss_mb", label: "P95 RAM (MB)" },
  ];
  return (
    <table>
      <thead>
        <tr>
          <th>Metri̇k</th>
          <th>Güncel</th>
          <th>Baz</th>
          <th>Fark</th>
        </tr>
      </thead>
      <tbody>
        {metrics.map((metric) => {
          const curValue = current.stats?.[metric.key];
          const baseValue = baseline.stats?.[metric.key];
          return (
            <tr key={metric.key}>
              <td>{metric.label}</td>
              <td>{formatNumber(curValue)}</td>
              <td>{formatNumber(baseValue)}</td>
              <td>{formatDelta(curValue, baseValue)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function buildComparisonChart(currentSamples, baselineSamples, key, label, baselineColor = "#10b981") {
  const maxLength = Math.max(currentSamples.length, baselineSamples.length);
  const labels = Array.from({ length: maxLength }, (_, index) => index.toString());
  return {
    data: {
      labels,
      datasets: [
        {
          label: `Güncel ${label}`,
          data: mapToLength(currentSamples, key, maxLength),
          borderColor: "#2563eb",
          tension: 0.25,
          fill: false,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: `Baz ${label}`,
          data: mapToLength(baselineSamples, key, maxLength),
          borderColor: baselineColor,
          tension: 0.25,
          fill: false,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: "Örnek" },
          ticks: { color: "#334155" },
        },
        y: {
          title: { display: true, text: label },
          ticks: { color: "#334155" },
        },
      },
      plugins: {
        legend: {
          position: "bottom",
        },
        tooltip: {
          mode: "index",
          intersect: false,
        },
      },
    },
  };
}

function mapToLength(samples, key, length) {
  const data = new Array(length).fill(null);
  samples.forEach((sample, index) => {
    data[index] = sample[key];
  });
  return data;
}

function formatNumber(value) {
  if (value === undefined || value === null) {
    return "-";
  }
  return Number(value).toFixed(1);
}

function formatDelta(cur, base) {
  if (cur === undefined || cur === null || base === undefined || base === null) {
    return "-";
  }
  const delta = Number(cur) - Number(base);
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}`;
}

function formatMessage(message) {
  if (!message) {
    return "";
  }
  return message.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
}
