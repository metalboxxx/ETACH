/**
 * The unsaved-text guard (step 22.1.5, R22.1.5.6). A panel with unsaved typing registers a check;
 * the shell asks before Back, Esc, opening another thread or a new thread when one says "dirty".
 */
import { createContext, useContext, useEffect, useRef } from "react";

export type LeaveCheck = () => boolean;
export type RegisterLeaveCheck = (check: LeaveCheck) => () => void;

export const LeaveGuardContext = createContext<RegisterLeaveCheck>(() => () => {});

/** Registers "I have unsaved changes" for as long as the component is mounted. */
export function useLeaveGuard(dirty: boolean): void {
  const register = useContext(LeaveGuardContext);
  const latest = useRef(dirty);
  useEffect(() => {
    latest.current = dirty;
  });
  useEffect(() => register(() => latest.current), [register]);
}
