import { Link, Route, Routes } from 'react-router-dom'
import Feed from './pages/Feed.jsx'
import InstructionPage from './pages/InstructionPage.jsx'
import EditionPage from './pages/EditionPage.jsx'

export default function App() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">מה השתנה בהוראות תכ"ם</Link>
        <span className="tagline">עדכונים מהמהדורות האחרונות, בלי להוריד ולהשוות קבצים</span>
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/instructions/:code" element={<InstructionPage />} />
          <Route path="/instructions/:code/editions/:version" element={<EditionPage />} />
          <Route path="*" element={<p>הדף לא נמצא. <Link to="/">חזרה לעדכונים</Link></p>} />
        </Routes>
      </main>
    </>
  )
}
