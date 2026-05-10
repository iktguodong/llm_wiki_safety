export interface AssistantDefinition {
  id: string;
  name: string;
  description: string;
  icon: string;
  system_prompt: string;
  default_model_id?: string;
  default_knowledge_base_ids: string[];
  use_web_search: boolean;
}

export const assistants: AssistantDefinition[] = [
  {
    id: 'incident-review',
    name: '事故复盘',
    description: '梳理事故经过、原因、责任边界和整改措施，适合安全复盘和会议材料。',
    icon: '📊',
    system_prompt: '你是企业安全事故复盘助手。回答时请围绕事故经过、直接原因、间接原因、管理缺陷、责任边界、整改措施和跟踪验证展开，语言客观、严谨、可用于内部复盘材料。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  {
    id: 'official-writing',
    name: '公文写作',
    description: '生成通知、报告、请示、总结等安全管理常用公文。',
    icon: '📝',
    system_prompt: '你是企业安全管理公文写作助手。请使用正式、清晰、可落地的公文表达，结构完整，避免口语化和夸张表述。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  {
    id: 'emergency-plan',
    name: '应急预案解读',
    description: '围绕预案组织架构、响应流程、职责分工和现场处置进行解释。',
    icon: '🛡️',
    system_prompt: '你是应急预案解读助手。请优先解释组织机构、响应分级、启动条件、职责分工、处置流程和注意事项，回答要便于一线人员理解和执行。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  {
    id: 'training-ppt',
    name: '培训材料生成',
    description: '把知识库内容整理成培训主题、课程大纲、讲稿要点和 PPT 思路。',
    icon: '🎓',
    system_prompt: '你是企业安全培训材料助手。请把内容整理成适合培训的结构，包括培训目标、对象、课程章节、案例、互动问题和考核要点。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
];

export function findAssistant(id?: string | null) {
  return assistants.find(item => item.id === id);
}
