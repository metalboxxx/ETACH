/**
 * The thread's top bar is one compact line on the Key tab (step 22.4.5, comment 11), so the key
 * photos keep their size; since step 22.4.8 (answer 7) on every workspace tab. The banner
 * provides it; `ThreadRunCard` reads it.
 */
import { createContext, useContext } from "react";

export const CompactBarContext = createContext(false);

export function useCompactBar(): boolean {
  return useContext(CompactBarContext);
}
