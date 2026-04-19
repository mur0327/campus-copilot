import { BrowserRouter, Route, Routes } from "react-router-dom";

import AdminPage from "./pages/AdminPage";
import KioskPage from "./pages/KioskPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<KioskPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  );
}
