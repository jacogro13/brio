import { useEffect, useState } from "react";

const MOBILE_BREAKPOINT = 640;

function getMobileFromWidth() {
  // Use outerWidth — unlike innerWidth, it doesn't change when the soft keyboard opens.
  return window.outerWidth <= MOBILE_BREAKPOINT;
}

/** The `mobile` flag (structural differences only, see index.css) and the
 * sidebar's open state, which follows width changes. */
export function useMobileLayout() {
  const [mobile, setMobile] = useState(() => getMobileFromWidth());
  const [sidebarOpen, setSidebarOpen] = useState(() => !getMobileFromWidth());

  useEffect(() => {
    let lastWidth = window.outerWidth;
    const onResize = () => {
      const currentWidth = window.outerWidth;
      if (currentWidth === lastWidth) return; // height-only change (keyboard open/close)
      lastWidth = currentWidth;
      const nowMobile = currentWidth <= MOBILE_BREAKPOINT;
      setMobile(nowMobile);
      if (!nowMobile) setSidebarOpen(true);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const closeSidebarOnMobile = () => {
    if (mobile) setSidebarOpen(false);
  };

  return { mobile, sidebarOpen, setSidebarOpen, closeSidebarOnMobile };
}
