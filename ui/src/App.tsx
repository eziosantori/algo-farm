import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { WizardPage } from "./components/Wizard/WizardPage.tsx";
import { StrategiesPage } from "./components/Strategies/StrategiesPage.tsx";

export function App() {
  return (
    <BrowserRouter>
      <nav style={styles.nav}>
        <span style={styles.brand}>🌾 Algo Farm</span>
        <NavLink to="/wizard" style={navLinkStyle}>
          Wizard
        </NavLink>
        <NavLink to="/strategies" style={navLinkStyle}>
          Strategies
        </NavLink>
      </nav>

      <main style={styles.main}>
        <Routes>
          <Route path="/" element={<WizardPage />} />
          <Route path="/wizard" element={<WizardPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

function navLinkStyle({ isActive }: { isActive: boolean }) {
  return {
    ...styles.link,
    fontWeight: isActive ? "bold" : "normal",
    textDecoration: isActive ? "underline" : "none",
  };
}

const styles = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: "1.5rem",
    padding: "0.75rem 1.5rem",
    borderBottom: "1px solid #e5e7eb",
    backgroundColor: "#f9fafb",
  },
  brand: {
    fontWeight: "bold",
    fontSize: "1.1rem",
    marginRight: "auto",
  },
  link: {
    color: "#111827",
    textDecoration: "none",
  } as React.CSSProperties,
  main: {
    maxWidth: "900px",
    margin: "0 auto",
    padding: "2rem 1.5rem",
  },
};
