import { createContext, useContext, useEffect } from 'react';

export const HeaderBackContext = createContext(null);

// Pages can preserve save-before-return behavior in the shared header.
export function useHeaderBack({ to, label, onClick, disabled = false }) {
  const setBack = useContext(HeaderBackContext);
  useEffect(() => {
    setBack({ to, label, onClick, disabled });
    return () => setBack(null);
  }, [setBack, to, label, onClick, disabled]);
}
