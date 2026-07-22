export default function NetworkEncodingLegend() {
  return <aside className="network-encoding-legend" aria-label="关系强度与社区密度图例">
    <strong>关系编码</strong>
    <div className="network-legend-section">
      <span><i className="edge high" />高贡献</span>
      <span><i className="edge medium" />中贡献</span>
      <span><i className="edge low" />低贡献</span>
    </div>
    <div className="network-legend-section density">
      <span><i className="density high" />高密度</span>
      <span><i className="density medium" />中密度</span>
      <span><i className="density low" />低密度</span>
    </div>
  </aside>;
}
