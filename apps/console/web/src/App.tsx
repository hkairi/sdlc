export default function App() {
  return (
    <main className="shell">
      <header>
        <p className="eyebrow">Console SDLC · L0</p>
        <h1>Console SDLC</h1>
        <p className="sub">
          Squelette local : backend FastAPI, frontend React, SQLite et CLI.
          Le tableau de bord complet arrive avec les lots suivants.
        </p>
      </header>

      <section className="card">
        <h2>État du socle</h2>
        <ul>
          <li>Backend FastAPI : <strong>squelette</strong></li>
          <li>Frontend React + Vite : <strong>squelette</strong></li>
          <li>Base SQLite : <strong>à venir (tâche 1.3)</strong></li>
          <li>Écoute : <code>127.0.0.2:8765</code>, sans authentification</li>
        </ul>
      </section>
    </main>
  );
}
