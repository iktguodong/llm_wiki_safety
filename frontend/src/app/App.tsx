import { useState } from 'react';
import { AppProvider } from '../lib/context';
import Sidebar from './components/Sidebar';
import StatusBar from './components/StatusBar';
import ChatPage from './components/pages/ChatPage';
import SearchPage from './components/pages/SearchPage';
import KnowledgeBasePage from './components/pages/KnowledgeBasePage';
import TrainingPage from './components/pages/TrainingPage';
import SettingsPage from './components/pages/SettingsPage';

type PageType = 'chat' | 'search' | 'knowledge' | 'training' | 'settings';

function AppInner() {
  const [currentPage, setCurrentPage] = useState<PageType>('chat');

  const renderPage = () => {
    switch (currentPage) {
      case 'chat':      return <ChatPage />;
      case 'search':    return <SearchPage />;
      case 'knowledge': return <KnowledgeBasePage />;
      case 'training':  return <TrainingPage />;
      case 'settings':  return <SettingsPage />;
      default:          return <ChatPage />;
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      <div className="flex-1 flex overflow-hidden">
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
        <main className="flex-1 overflow-hidden">
          {renderPage()}
        </main>
      </div>
      <StatusBar />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppInner />
    </AppProvider>
  );
}