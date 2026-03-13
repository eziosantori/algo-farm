import { useState } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { WizardPage } from "./components/Wizard/WizardPage.tsx";
import { StrategiesPage } from "./components/Strategies/StrategiesPage.tsx";
import { LabPage } from "./components/Lab/LabPage.tsx";
import { DashboardPage } from "./components/Dashboard/DashboardPage.tsx";

function useDarkMode() {
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains("dark")
  );

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return { dark, toggle };
}

export function App() {
  const { dark, toggle } = useDarkMode();

  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        {/* Nav */}
        <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/90 backdrop-blur dark:border-gray-800 dark:bg-gray-950/90">
          <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
            {/* Brand */}
            <span className="mr-auto text-lg font-bold tracking-tight text-gray-900 dark:text-white">
              🌾 <span className="text-blue-600 dark:text-blue-400">Algo</span>Farm
            </span>

            {/* Nav links */}
            <nav className="flex items-center gap-1">
              {[
                { to: "/wizard", label: "Wizard" },
                { to: "/strategies", label: "Strategies" },
                { to: "/lab", label: "Lab" },
                { to: "/dashboard", label: "Dashboard" },
              ].map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* Dark mode toggle */}
            <button
              onClick={toggle}
              aria-label="Toggle dark mode"
              className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white transition-colors"
            >
              {dark ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} stroke="currentColor" fill="none"/>
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
                </svg>
              )}
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
          <Routes>
            <Route path="/" element={<WizardPage />} />
            <Route path="/wizard" element={<WizardPage />} />
            <Route path="/strategies" element={<StrategiesPage />} />
            <Route path="/lab" element={<LabPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
