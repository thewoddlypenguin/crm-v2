import SegmentsSettingsPanel from '../components/SegmentsSettingsPanel';

export default function SettingsPage() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure CRM behavior and admin tools.</p>
      </div>

      <div className="settings-layout">
        <aside className="settings-nav">
          <button type="button" className="settings-nav-item is-active">
            Segments
          </button>
        </aside>

        <main className="settings-panel">
          <SegmentsSettingsPanel />
        </main>
      </div>
    </div>
  );
}