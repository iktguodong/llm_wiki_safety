import { useState } from 'react';
import { AppProvider } from '../lib/context';
import Sidebar from './components/Sidebar';
import StatusBar from './components/StatusBar';
import ChatPage from './components/pages/ChatPage';
import SearchPage from './components/pages/SearchPage';
import KnowledgeBasePage from './components/pages/KnowledgeBasePage';
import TrainingPage from './components/pages/TrainingPage';
import SettingsPage from './components/pages/SettingsPage';
import ReaderPage from './components/pages/ReaderPage';
import AssistantPage from './components/pages/AssistantPage';
import type { AssistantDefinition } from './data/assistants';

type PageType = 'chat' | 'assistant' | 'search' | 'knowledge' | 'training' | 'settings';

interface ReaderContext {
  kbId: string;
  docId: string;
  docName: string;
  page?: number;
}

function AppInner() {
  const [currentPage, setCurrentPage] = useState<PageType>('chat');
  const [readerCtx, setReaderCtx] = useState<ReaderContext | null>(null);
  const [activeAssistant, setActiveAssistant] = useState<AssistantDefinition | null>(null);

  /** 展开阅读器 */
  const openReader = (kbId: string, docId: string, docName: string, page = 1) => {
    setReaderCtx({ kbId, docId, docName, page });
  };

  /** 关闭阅读器，返回之前页面 */
  const closeReader = () => {
    setReaderCtx(null);
  };

  const renderPage = () => {
    // 阅读器优先展示
    if (readerCtx) {
      return (
        <ReaderPage
          kbId={readerCtx.kbId}
          docId={readerCtx.docId}
          docName={readerCtx.docName}
          initialPage={readerCtx.page ?? 1}
          onBack={closeReader}
        />
      );
    }
    switch (currentPage) {
      case 'chat':      return <ChatPage activeAssistant={activeAssistant} />;
      case 'assistant': return (
        <AssistantPage
          activeAssistantId={activeAssistant?.id}
          onStartChat={setActiveAssistant}
        />
      );
      case 'search':    return <SearchPage openReader={openReader} />;
      case 'knowledge': return <KnowledgeBasePage openReader={openReader} />;
      case 'training':  return <TrainingPage />;
      case 'settings':  return <SettingsPage />;
      default:          return <ChatPage />;
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      <div className="flex-1 flex overflow-hidden">
        <Sidebar currentPage={currentPage} onPageChange={(p) => { closeReader(); setCurrentPage(p); }} />
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
