"use client";

/**
 * Pre-paint theme init: must run before React hydration to avoid a flash.
 * Reads localStorage.theme and creates the theme-color meta (matching --surface-page; ThemeToggle keeps it current). Defaults to system (honors prefers-color-scheme).
 */
const themeScript = `(function(){try{var t=localStorage.getItem('theme');var d=t==='dark'||((!t||t==='system')&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);var m=document.querySelector('meta[name=theme-color]');if(!m){m=document.createElement('meta');m.name='theme-color';document.head.appendChild(m);}m.content=d?'#000000':'#fafafa';}catch(e){}})();`;


/**
 * Rendered as a script on the server only. When the client renders this tree itself (a `notFound()` after the
 * loading shell has streamed replaces the document), React 19 would log "Encountered a script tag while rendering
 * React component" for it, and the server-side script has already run (or, there, never ran) by then.
 */
export function ThemeScript() {
  if (typeof window !== "undefined") return null;
  return <script dangerouslySetInnerHTML={{ __html: themeScript }} />;
}
