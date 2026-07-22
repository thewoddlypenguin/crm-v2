import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { User } from "../types";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  Users,
  GitBranch,
  Upload,
  Download,
  LogOut,
  Menu,
  X,
  Plus,
  Settings,
} from "lucide-react";

interface LayoutProps {
  user: User;
  onLogout: () => void;
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/pipeline", label: "Pipeline", icon: GitBranch },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/export", label: "Export", icon: Download },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Layout({ user, onLogout, children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 bg-card border-r border-border transform transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2 px-4 py-4 border-b border-border">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">
            L
          </div>
          <span className="font-semibold text-foreground">Leverage CRM</span>
        </div>

        <nav className="flex flex-col gap-1 p-3">
          <Link to="/leads/new">
            <Button className="w-full gap-2" size="sm">
              <Plus className="h-4 w-4" />
              New Lead
            </Button>
          </Link>

          <div className="mt-3 space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = location.pathname === item.href || (item.href !== "/dashboard" && location.pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                    active
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground truncate">
              {user.email}
            </div>
            <Button variant="ghost" size="sm" onClick={() => { onLogout(); navigate("/login"); }}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 lg:pl-60">
        <header className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:px-6">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          <h1 className="text-lg font-semibold text-foreground">
            {NAV_ITEMS.find((i) => location.pathname.startsWith(i.href))?.label || "Leverage CRM"}
          </h1>
        </header>
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
