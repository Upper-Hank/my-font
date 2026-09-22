import { useEffect, useLayoutEffect, useState } from 'react';
import MonitorIcon from '@uplus-icon/react/icons/monitor';
import MoonIcon from '@uplus-icon/react/icons/moon';
import SunIcon from '@uplus-icon/react/icons/sun';
import { iconProps } from './ui.jsx';
import { syncFavicon } from './brand.js';

const KEY = 'handfont-theme';

function resolve(preference) {
  if (preference === 'light' || preference === 'dark') return preference;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function apply(preference) {
  const theme = resolve(preference);
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#11110f' : '#ffffff');
  syncFavicon(theme);
}

const OPTIONS = [
  { value: 'system', label: '跟随系统', Icon: MonitorIcon },
  { value: 'light', label: '亮色', Icon: SunIcon },
  { value: 'dark', label: '暗色', Icon: MoonIcon },
];

export default function ThemeToggle() {
  const [preference, setPreference] = useState(() => {
    const saved = localStorage.getItem(KEY);
    return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system';
  });

  useLayoutEffect(() => {
    apply(preference);
    localStorage.setItem(KEY, preference);
  }, [preference]);

  useEffect(() => {
    if (preference !== 'system') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const sync = () => apply('system');
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, [preference]);

  function cycle() {
    const order = ['system', 'light', 'dark'];
    setPreference(order[(order.indexOf(preference) + 1) % order.length]);
  }

  const current = OPTIONS.find((item) => item.value === preference) || OPTIONS[0];
  const CurrentIcon = current.Icon;

  return (
    <>
      <div className="segmented-control" role="group" aria-label="外观">
        {OPTIONS.map((item) => {
          const ItemIcon = item.Icon;
          return (
            <button
              key={item.value}
              type="button"
              className={item.value === preference ? 'is-active' : ''}
              aria-pressed={item.value === preference}
              aria-label={item.label}
              title={item.label}
              onClick={() => setPreference(item.value)}
            >
              <ItemIcon {...iconProps} />
            </button>
          );
        })}
      </div>
      <button
        className="header-tool-compact"
        type="button"
        aria-label={`外观：${current.label}，点击切换`}
        title={current.label}
        onClick={cycle}
      >
        <CurrentIcon {...iconProps} />
      </button>
    </>
  );
}
