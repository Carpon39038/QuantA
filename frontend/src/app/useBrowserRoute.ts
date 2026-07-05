import { useCallback, useEffect, useState } from 'react';

function currentPathname(): string {
  return window.location.pathname || '/';
}

export function useBrowserRoute() {
  const [pathname, setPathname] = useState(currentPathname);

  useEffect(() => {
    const handlePopState = () => setPathname(currentPathname());
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useCallback((path: string) => {
    if (path !== currentPathname()) {
      window.history.pushState(null, '', path);
    }
    setPathname(currentPathname());
  }, []);

  return { pathname, navigate };
}
