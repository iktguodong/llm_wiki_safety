import { useState } from 'react';
import Sidebar from './components/Sidebar';
import StatusBar from './components/StatusBar';
import ChatPage from './components/pages/ChatPage';
import SearchPage from './components/pages/SearchPage';
import KnowledgeBasePage from './components/pages/KnowledgeBasePage';
import TrainingPage from './components/pages/TrainingPage';
import SettingsPage from './components/pages/SettingsPage';

type PageType = 'chat' | 'search' | 'knowledge' | 'training' | 'settings';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageType>('chat');
  const [currentKnowledgeBase, setCurrentKnowledgeBase] = useState('港口安全知识库');
  const [currentModel, setCurrentModel] = useState('V3 Flash');

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
      <StatusBar
        currentKnowledgeBase={currentKnowledgeBase}
        currentModel={currentModel}
        onKnowledgeBaseChange={setCurrentKnowledgeBase}
        onModelChange={setCurrentModel}
      />
    </div>
  );
}
