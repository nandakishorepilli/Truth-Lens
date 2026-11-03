import { useState, type ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopNav from "./TopNav";
import type { Page } from "../types/navigation";

interface Props {
  page: Page;
  navigate: (p: Page) => void;
  onRefreshCurrent?: () => void;
  children: ReactNode;
}

export default function Layout({
  page,
  navigate,
  onRefreshCurrent,
  children,
}: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-text-primary selection:bg-accent/30 selection:text-white">
      {/* Mobile Drawer Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/70 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-bg-card transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          page={page}
          navigate={navigate}
          onClose={() => setSidebarOpen(false)}
        />
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <TopNav
          page={page}
          onMenuClick={() => setSidebarOpen(true)}
          onRefreshCurrent={onRefreshCurrent}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
