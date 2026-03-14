import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PenangLens Admin",
  description: "PenangLens Content & System Administration",
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`admin-layout ${inter.className}`}>
      <Sidebar />
      <main className="admin-content">
        {children}
      </main>
    </div>
  );
}
