import { JI_PATH, ZI_PATH } from './brand.js';

export default function BrandMark() {
  return (
    <span className="brand-mark">
      <svg viewBox="0 0 1000 500" fill="none" aria-hidden="true">
        <path d={ZI_PATH} fill="currentColor" />
        <g clipPath="url(#brand-ji)">
          <path d={JI_PATH} fill="currentColor" />
        </g>
        <defs>
          <clipPath id="brand-ji">
            <rect width="500" height="500" transform="translate(500)" />
          </clipPath>
        </defs>
      </svg>
    </span>
  );
}
