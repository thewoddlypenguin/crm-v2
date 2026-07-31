import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import SegmentsSettingsPanel from '../components/SegmentsSettingsPanel';
import EmailSettingsPanel from '../components/EmailSettingsPanel';
import GmailSettingsPanel from '../components/GmailSettingsPanel';
import OrgMembersPanel from '../components/OrgMembersPanel';

type SettingsTab = 'segments' | 'email' | 'gmail' | 'members';

export default function SettingsPage() {
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab') as SettingsTab | null;
  const [activeTab, setActiveTab] = useState<SettingsTab>(tabParam || 'segments');

  useEffect(() => {
    if (tabParam && ['segments', 'email', 'gmail', 'members'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

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
          <button
            type="button"
            className={`settings-nav-item${activeTab === 'gmail' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('gmail')}
          >
            Gmail
          </button>
          <button
            type="button"
            className={`settings-nav-item${activeTab === 'members' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('members')}
          >
            Members
          </button>
        </aside>

        <main className="settings-panel">
          {activeTab === 'segments' && <SegmentsSettingsPanel />}
          {activeTab === 'email' && <EmailSettingsPanel />}
          {activeTab === 'gmail' && <GmailSettingsPanel />}
          {activeTab === 'members' && <OrgMembersPanel />}
        </main>
      </div>
    </div>
  );
}
