import React from "react";

const markPaths = (
  <>
    <path
      d="M 26 4 H 8 C 4.686 4 2 6.686 2 10 V 48 C 2 51.314 4.686 54 8 54 H 34 C 37.314 54 40 51.314 40 48 V 18"
      stroke="#4A5D23"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M 26 4 L 40 18 H 26 V 4 Z"
      fill="#87AB72"
      fillOpacity="0.3"
      stroke="#4A5D23"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path
      d="M 32 13 C 41 4 52 6 52 6 C 52 6 52 17 41 23 C 35.5 26 32 20 32 13 Z"
      stroke="#87AB72"
      strokeWidth="2.5"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M 33 17 Q 41 12 49 7" stroke="#87AB72" strokeWidth="2" strokeLinecap="round" />
    <line x1="8" y1="13" x2="20" y2="13" stroke="#4A5D23" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="8" y1="20" x2="28" y2="20" stroke="#4A5D23" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="8" y1="27" x2="28" y2="27" stroke="#4A5D23" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="8" y1="34" x2="28" y2="34" stroke="#4A5D23" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="8" y1="41" x2="18" y2="41" stroke="#4A5D23" strokeWidth="2.5" strokeLinecap="round" />
    <path
      d="M 24 42 C 24 38.686 26.686 36 30 36 C 33.314 36 36 38.686 36 42 C 36 45.314 33.314 48 30 48 C 28.5 48 27.2 47.4 26.2 46.5 L 23 48.5 L 24.3 45.5 C 24.1 44.4 24 43.2 24 42 Z"
      stroke="#4A5D23"
      strokeWidth="2"
      fill="#F6F7F4"
      strokeLinejoin="round"
    />
    <circle cx="27.5" cy="42" r="1" fill="#4A5D23" />
    <circle cx="30" cy="42" r="1" fill="#4A5D23" />
    <circle cx="32.5" cy="42" r="1" fill="#4A5D23" />
  </>
);

/** Icon-only mark. Scales from its own viewBox — never cropped. */
export function LogoMark({ className = "h-7 w-auto" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 56 60"
      className={className}
      fill="none"
      role="img"
      aria-label="DocuSage"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="translate(2, 2)">{markPaths}</g>
    </svg>
  );
}

/** Full lockup: mark + wordmark. */
export function Logo({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 258 62"
      className={className}
      fill="none"
      role="img"
      aria-label="DocuSage"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="translate(2, 3)">{markPaths}</g>
      <text x="66" y="42" fontFamily="var(--font-jakarta)" fontSize="32" letterSpacing="-0.5">
        <tspan fontWeight="700" fill="#1C241F">
          Docu
        </tspan>
        <tspan fontWeight="500" fill="#4A5D23">
          Sage
        </tspan>
      </text>
    </svg>
  );
}
