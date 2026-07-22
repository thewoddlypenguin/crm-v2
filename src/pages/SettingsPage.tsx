import { useState } from 'react';
import SegmentsSettingsPanel from '../components/SegmentsSettingsPanel';
import EmailSettingsPanel from '../components/EmailSettingsPanel';

type SettingsTab = 'segments' | 'email';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('segments');

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure CRM behavior and admin tools.</p>
      </div>

      <div className="settings-layout">
        <aside className="settings-nav">
          <button
            type="button"
            className={`settings-nav-item${activeTab === 'segments' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('segments')}
          >
            Segments
          </button>
          <button
            type="button"
            className={`settings-nav-item${activeTab === 'email' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('email')}
          >
            Email
          </button>
        </aside>

        <main className="settings-panel">
          {activeTab === 'segments' && <SegmentsSettingsPanel />}
          {activeTab === 'email' && <EmailSettingsPanel />}
        </main>
      </div>
    </div>
  );
}