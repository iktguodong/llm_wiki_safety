import { Bot, MessageSquare, Search, Database, GraduationCap, Settings } from 'lucide-react';
import LogoMark from './LogoMark';

type PageType = 'chat' | 'assistant' | 'search' | 'knowledge' | 'training' | 'settings';

interface SidebarProps {
  currentPage: PageType;
  onPageChange: (page: PageType) => void;
}

const navItems = [
  { id: 'chat' as const, icon: MessageSquare, label: '对话' },
  { id: 'assistant' as const, icon: Bot, label: '专业助手' },
  { id: 'search' as const, icon: Search, label: '原文检索' },
  { id: 'knowledge' as const, icon: Database, label: '知识库管理' },
  { id: 'training' as const, icon: GraduationCap, label: 'PPT生成' },
];

const bottomItems = [
  { id: 'settings' as const, icon: Settings, label: '设置' },
];

function NavButton({
  item,
  isActive,
  onClick,
}: {
  item: { id: string; icon: React.ElementType; label: string };
  isActive: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={onClick}
      className="w-full h-9 px-3 mb-0.5 flex items-center gap-2.5 rounded-lg text-sm transition-colors"
      style={{
        background: isActive ? '#EEF2FF' : 'transparent',
        color: isActive ? '#4338CA' : '#64748B',
        boxShadow: isActive ? 'inset 2px 0 0 #4F46E5' : 'none',
        fontWeight: isActive ? 500 : 400,
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = '#F8FAFC';
          e.currentTarget.style.color = '#334155';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.color = '#64748B';
        }
      }}
    >
      <Icon
        className="flex-shrink-0"
        style={{
          width: '15px',
          height: '15px',
          color: isActive ? '#4F46E5' : '#94A3B8',
        }}
      />
      <span>{item.label}</span>
    </button>
  );
}

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  return (
    <div
      className="w-[210px] flex-shrink-0 flex flex-col"
      style={{
        background: '#FFFFFF',
        borderRight: '1px solid #E8ECF2',
      }}
    >
      {/* Logo */}
      <div
        className="h-16 flex items-center px-5"
        style={{ borderBottom: '1px solid #F0F3F7' }}
      >
        <div className="flex items-center gap-3">
          <LogoMark
            className="w-10 h-10 rounded-xl bg-white border border-slate-200 shadow-sm overflow-hidden flex items-center justify-center flex-shrink-0"
            imageClassName="w-full h-full object-contain scale-110"
          />
          <div>
            <div style={{ color: '#0F172A', fontSize: '14px', fontWeight: 600, letterSpacing: '0.01em' }}>
              安牛
            </div>
            <div style={{ color: '#000000', fontSize: '11px' }}>个人知识助手</div>
          </div>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 py-3 px-3">
        {navItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            isActive={currentPage === item.id}
            onClick={() => onPageChange(item.id)}
          />
        ))}
      </nav>

      {/* Bottom section */}
      <div className="px-3 pb-3" style={{ borderTop: '1px solid #F0F3F7' }}>
        <div className="pt-3">
          {bottomItems.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              isActive={currentPage === item.id}
              onClick={() => onPageChange(item.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
