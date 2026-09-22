import type { NavItem } from "@/layouts/navConfig";

const paths: Record<NavItem["icon"], string> = {
  home: "M3 11l9-8 9 8M5 10v10h14V10",
  dues: "M4 6h16M4 12h16M4 18h10",
  complaint: "M12 9v4m0 4h.01M10.29 3.86l-8.18 14.18A1 1 0 003 20h18a1 1 0 00.89-1.46L13.71 3.86a1 1 0 00-1.72 0z",
  visitor: "M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75",
  notice: "M3 5h18M3 12h18M3 19h12",
  amenity: "M12 2l3 7h7l-5.5 4.5L18 21l-6-4.5L6 21l1.5-7.5L2 9h7z",
  proposal: "M9 12l2 2 4-4M7 4h10a2 2 0 012 2v14l-4-2-3 2-3-2-4 2V6a2 2 0 012-2z",
  expense: "M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  people: "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75",
  wallet: "M3 7a2 2 0 012-2h13a1 1 0 011 1v3M3 7v10a2 2 0 002 2h15a1 1 0 001-1v-6a1 1 0 00-1-1h-5a2 2 0 100 4h5",
  todo: "M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
  society: "M3 21h18M5 21V7l7-4 7 4v14M9 9h1m4 0h1m-6 4h1m4 0h1m-6 4h1m4 0h1",
};

export function Icon({ name, className = "w-5 h-5" }: { name: NavItem["icon"]; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}
