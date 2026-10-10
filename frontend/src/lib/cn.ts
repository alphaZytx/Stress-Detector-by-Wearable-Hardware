import clsx, { type ClassValue } from "clsx";

/** Conditional className join. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
