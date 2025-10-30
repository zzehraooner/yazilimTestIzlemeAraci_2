import { NavLink, Route, Routes } from "react-router-dom";
import RunList from "./pages/RunList.jsx";
import RunDetail from "./pages/RunDetail.jsx";
import Compare from "./pages/Compare.jsx";

const layoutStyles = {
  header: {
    backgroundColor: "#1f2933",
    color: "#fff",
    padding: "1rem 1.5rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  brand: {
    fontSize: "1.25rem",
    fontWeight: 600,
  },
  nav: {
    display: "flex",
    gap: "1rem",
  },
  link: {
    color: "#cbd2d9",
    fontWeight: 500,
  },
  activeLink: {
    color: "#fff",
    borderBottom: "2px solid #fff",
    paddingBottom: "0.25rem",
  },
  main: {
    padding: "1.5rem",
    maxWidth: "1200px",
    margin: "0 auto",
  },
};

export default function App() {
  return (
    <div>
      <header style={layoutStyles.header}>
        <div style={layoutStyles.brand}>Bizim Performans Aracı</div>
        <nav style={layoutStyles.nav}>
          <NavLink
            to="/"
            style={({ isActive }) => (isActive ? layoutStyles.activeLink : layoutStyles.link)}
            end
          >
            Koşular
          </NavLink>
          <NavLink
            to="/compare"
            style={({ isActive }) => (isActive ? layoutStyles.activeLink : layoutStyles.link)}
          >
            Karşılaştır
          </NavLink>
        </nav>
      </header>
      <main style={layoutStyles.main}>
        <Routes>
          <Route path="/" element={<RunList />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </main>
    </div>
  );
}
