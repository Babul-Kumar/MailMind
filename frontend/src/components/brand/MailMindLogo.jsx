import React from 'react';

/**
 * MailMind Brand Mark
 * Concept: Envelope (Mail) + Stylized "M" + Central Intelligent Signal
 * Works crisply at 20px, 24px, 32px, 48px in both dark and light modes.
 */
export function MailMindLogo({ size = 24, isScanning = false, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`mailmind-logo ${className} ${isScanning ? 'logo-scanning' : ''}`.trim()}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
      aria-label="MailMind logo"
    >
      <defs>
        <linearGradient id="mailmind-accent-grad" x1="2" y1="4" x2="30" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
      </defs>

      {/* Envelope Outer Shell */}
      <rect
        x="3"
        y="6"
        width="26"
        height="20"
        rx="3.5"
        stroke="url(#mailmind-accent-grad)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="rgba(99, 102, 241, 0.08)"
      />

      {/* Stylized "M" Flap Fold Lines */}
      <path
        d="M4 8.5L16 18.5L28 8.5"
        stroke="url(#mailmind-accent-grad)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Bottom Fold Lines creating Envelope Depth */}
      <path
        d="M4.5 24.5L11.5 17.5"
        stroke="url(#mailmind-accent-grad)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />
      <path
        d="M27.5 24.5L20.5 17.5"
        stroke="url(#mailmind-accent-grad)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />

      {/* Intelligent Central Signal Node */}
      <circle
        cx="16"
        cy="18.5"
        r="2.2"
        fill="#818cf8"
        stroke="var(--bg-surface, #0f172a)"
        strokeWidth="1"
      />
    </svg>
  );
}

export default MailMindLogo;
