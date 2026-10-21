import React from 'react';
import logoUrl from '../../assets/logo.svg';

/**
 * MailMind Brand Logo
 * Loads the user-supplied assest/logo.svg directly as a bundled vector asset.
 * This ensures exact rendering fidelity, prevents SVG gradient ID collisions in the DOM,
 * and renders identically across dev, preview, and production.
 */
export function MailMindLogo({ size = 28, isScanning = false, className = '', alt = 'MailMind logo' }) {
  return (
    <img
      src={logoUrl}
      alt={alt}
      width={size}
      height={size}
      className={`mailmind-logo ${className} ${isScanning ? 'logo-scanning' : ''}`.trim()}
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        flexShrink: 0,
        width: `${size}px`,
        height: `${size}px`,
        minWidth: `${size}px`,
        minHeight: `${size}px`,
        borderRadius: `${Math.round(size * 0.22)}px`,
        objectFit: 'contain',
      }}
    />
  );
}

export default MailMindLogo;
