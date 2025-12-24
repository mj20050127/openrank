import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import "./App.css";

async function etlFetch(repo, metrics = ["openrank", "activity"]) {
  const url = `/api/etl/fetch?repo=${encodeURIComponent(repo)}&metrics=${encodeURIComponent(metrics.join(","))}`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(`ETL失败 HTTP ${res.status}`);
  return res.json();
}

async function trend(repo, metric) {
  const url = `/api/metrics/trend?repo=${encodeURIComponent(repo)}&metric=${encodeURIComponent(metric)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`查询失败 HTTP ${res.status}`);
  return res.json(); // {repo, metric, points:[{dt,value}]}
}

function latest(points) {
  if (!points || points.length === 0) return null;
  return points[points.length - 1];
}

export default function App() {
  const [repo, setRepo] = useState("ossf/scorecard");
  const [status, setStatus] = useState("就绪");
  const [openrankPoints, setOpenrankPoints] = useState([]);
  const [activityPoints, setActivityPoints] = useState([]);
  const [embedUrl, setEmbedUrl] = useState("");
  const [embedStatus, setEmbedStatus] = useState("等待触发");

  const openrankLast = useMemo(() => latest(openrankPoints), [openrankPoints]);
  const activityLast = useMemo(() => latest(activityPoints), [activityPoints]);

  const openrankOption = useMemo(() => ({
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: openrankPoints.map(p => p.dt) },
    yAxis: { type: "value" },
    series: [{ type: "line", smooth: true, data: openrankPoints.map(p => p.value) }]
  }), [openrankPoints]);

  const activityOption = useMemo(() => ({
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: activityPoints.map(p => p.dt) },
    yAxis: { type: "value" },
    series: [{ type: "line", smooth: true, data: activityPoints.map(p => p.value) }]
  }), [activityPoints]);

  async function queryOnly() {
    setStatus("查询中...");
    const [o, a] = await Promise.all([trend(repo, "openrank"), trend(repo, "activity")]);
    setOpenrankPoints(o.points || []);
    setActivityPoints(a.points || []);
    setStatus("完成 ✅");
  }

  async function fetchAndShow() {
    if (!repo.includes("/")) {
      setStatus("失败 ❌ repo 格式应为 owner/repo");
      return;
    }
    try {
      setStatus("ETL抓取并入库中...");
      await etlFetch(repo, ["openrank", "activity"]);
      await queryOnly();
    } catch (e) {
      console.error(e);
      setStatus("失败 ❌ " + e.message);
    }
  }

  async function bootstrapDashboard() {
    if (!repo.includes("/")) {
      setEmbedStatus("失败 ❌ repo 格式应为 owner/repo");
      return;
    }
    try {
      setEmbedStatus("Agent 正在调用 DataEase 接口...");
      const res = await fetch("/api/dataease/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo })
      });
      if (!res.ok) throw new Error(`后端返回 ${res.status}`);
      const data = await res.json();
      setEmbedUrl(data.embed_url || "");
      setEmbedStatus(data.created ? "完成 ✅ 已新建" : "复用 ✅ 已存在");
    } catch (e) {
      console.error(e);
      setEmbedStatus("失败 ❌ " + e.message);
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui" }}>
      <h2>React 端到端 MVP（OpenDigger → ETL → DB → API → UI）</h2>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div>
          <div style={{ color: "#666", fontSize: 13 }}>仓库（owner/repo）</div>
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            style={{ padding: "10px 12px", minWidth: 280, borderRadius: 10, border: "1px solid #ccc" }}
          />
        </div>
        <button onClick={fetchAndShow} style={{ padding: "10px 14px", borderRadius: 10, border: 0, background: "#111", color: "#fff" }}>
          抓取并展示
        </button>
        <button onClick={queryOnly} style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
          只查询
        </button>
        <div style={{ color: "#666" }}>状态：{status}</div>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14, minWidth: 240 }}>
          <div style={{ color: "#666", fontSize: 13 }}>OpenRank 最新值</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{openrankLast ? openrankLast.value : "-"}</div>
          <div style={{ color: "#666", fontSize: 13 }}>dt: {openrankLast ? openrankLast.dt : "-"}</div>
        </div>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14, minWidth: 240 }}>
          <div style={{ color: "#666", fontSize: 13 }}>Activity 最新值</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{activityLast ? activityLast.value : "-"}</div>
          <div style={{ color: "#666", fontSize: 13 }}>dt: {activityLast ? activityLast.dt : "-"}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14 }}>
          <div style={{ color: "#666", fontSize: 13 }}>OpenRank 趋势</div>
          <ReactECharts option={openrankOption} style={{ height: 360 }} />
        </div>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14 }}>
          <div style={{ color: "#666", fontSize: 13 }}>Activity 趋势</div>
          <ReactECharts option={activityOption} style={{ height: 360 }} />
        </div>
      </div>

      <div style={{ marginTop: 24, border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>DataEase 健康总览大屏（DIV 嵌入）</div>
            <div style={{ color: "#666", fontSize: 13 }}>自动创建数据源/数据集/大屏，返回可嵌入链接</div>
          </div>
          <button onClick={bootstrapDashboard} style={{ padding: "10px 14px", borderRadius: 10, border: 0, background: "#111", color: "#fff" }}>
            一键生成/复用大屏
          </button>
          <div style={{ color: "#666" }}>状态：{embedStatus}</div>
        </div>
        {embedUrl ? (
          <div style={{ marginTop: 12, border: "1px solid #ccc", borderRadius: 10, overflow: "hidden" }}>
            <iframe src={embedUrl} title="DataEase-Health" style={{ width: "100%", height: 520, border: "none" }} allowFullScreen />
          </div>
        ) : (
          <div style={{ marginTop: 12, color: "#888" }}>还没有可嵌入链接，点击上方按钮自动生成</div>
        )}
      </div>
    </div>
  );
}
