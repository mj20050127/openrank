import { useEffect, useState } from 'react';
import './ChartFullscreenButton.css';

function ExpandIcon({ active }) {
  return active
    ? <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" /></svg>
    : <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7 3H3v4M13 3h4v4M7 17H3v-4M13 17h4v-4" /></svg>;
}

export default function ChartFullscreenButton({ targetRef }) {
  const [active, setActive] = useState(false);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setActive(document.fullscreenElement === targetRef.current);
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
      });
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, [targetRef]);

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement === targetRef.current) {
        await document.exitFullscreen?.();
        return;
      }
      await targetRef.current?.requestFullscreen?.();
    } catch {
      setActive(false);
    }
  };

  return <button
    type="button"
    className="chart-fullscreen-button"
    onClick={() => void toggleFullscreen()}
    title={active ? '退出全屏' : '放大图表'}
    aria-label={active ? '退出全屏' : '放大图表'}
  >
    <ExpandIcon active={active} />
    <span>{active ? '退出' : '放大'}</span>
  </button>;
}
