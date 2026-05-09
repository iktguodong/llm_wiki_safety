import { MessageSquare, Search, Database, GraduationCap, Settings } from 'lucide-react';

type PageType = 'chat' | 'search' | 'knowledge' | 'training' | 'settings';

interface SidebarProps {
  currentPage: PageType;
  onPageChange: (page: PageType) => void;
}

const navItems = [
  { id: 'chat' as const, icon: MessageSquare, label: '对话' },
  { id: 'search' as const, icon: Search, label: '检索' },
  { id: 'knowledge' as const, icon: Database, label: '知识库' },
  { id: 'training' as const, icon: GraduationCap, label: '培训' },
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
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-white flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
              fontSize: '13px',
              fontWeight: 700,
            }}
          >
            安
          </div>
          <div>
            <div style={{ color: '#0F172A', fontSize: '14px', fontWeight: 600, letterSpacing: '0.01em' }}>
              安牛
            </div>
            <div style={{ color: '#CBD5E1', fontSize: '11px' }}>v1.0.0</div>
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

        {/* User */}
        <div
          className="mt-2 flex items-center gap-2.5 px-3 py-2 rounded-lg"
          style={{ background: '#F8FAFC' }}
        >
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: '#EEF2FF', color: '#6366F1', fontSize: '11px', fontWeight: 500 }}
          >
            用
          </div>
          <span style={{ color: '#94A3B8', fontSize: '13px' }}>用户</span>
        </div>
      </div>
    </div>
  );
}
