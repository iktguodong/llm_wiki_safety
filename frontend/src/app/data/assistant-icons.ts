export interface AssistantIconOption {
  id: string;
  name: string;
  src: string;
}

export const assistantIconPresets = {
  default: '/assistant-icons/1F4A1.svg',
  incidentReview: '/assistant-icons/1F4C8.svg',
  officialWriting: '/assistant-icons/1F4DD.svg',
  emergencyPlan: '/assistant-icons/1F6E1.svg',
  trainingPpt: '/assistant-icons/1F4DA.svg',
} as const;

export const assistantIcons: AssistantIconOption[] = [
  // 通用 / 科技
  { id: '1F4A1', name: '灵感灯泡', src: '/assistant-icons/1F4A1.svg' },
  { id: '1F9E0', name: '思考大脑', src: '/assistant-icons/1F9E0.svg' },
  { id: '1F680', name: '火箭', src: '/assistant-icons/1F680.svg' },
  { id: '1F6E1', name: '安全盾牌', src: '/assistant-icons/1F6E1.svg' },
  { id: '1F4DA', name: '书本', src: '/assistant-icons/1F4DA.svg' },
  { id: '1F4C8', name: '趋势图', src: '/assistant-icons/1F4C8.svg' },
  { id: '1F50D', name: '搜索', src: '/assistant-icons/1F50D.svg' },
  { id: '1F527', name: '扳手', src: '/assistant-icons/1F527.svg' },
  { id: '1F528', name: '锤子', src: '/assistant-icons/1F528.svg' },
  { id: '1F9F0', name: '工具箱', src: '/assistant-icons/1F9F0.svg' },
  { id: '1F4BB', name: '电脑', src: '/assistant-icons/1F4BB.svg' },
  { id: '1F4E1', name: '天线', src: '/assistant-icons/1F4E1.svg' },
  { id: '1F4AC', name: '对话气泡', src: '/assistant-icons/1F4AC.svg' },
  { id: '1F4E3', name: '扩音器', src: '/assistant-icons/1F4E3.svg' },
  { id: '1F52E', name: '水晶球', src: '/assistant-icons/1F52E.svg' },
  { id: '1F3AF', name: '命中靶心', src: '/assistant-icons/1F3AF.svg' },
  { id: '1F30D', name: '地球', src: '/assistant-icons/1F30D.svg' },
  { id: '2699', name: '齿轮', src: '/assistant-icons/2699.svg' },
  // 安全 / 风险
  { id: '1F6A8', name: '警报灯', src: '/assistant-icons/1F6A8.svg' },
  { id: '26A0', name: '警告', src: '/assistant-icons/26A0.svg' },
  { id: '1F6A7', name: '施工', src: '/assistant-icons/1F6A7.svg' },
  { id: '1F525', name: '火焰', src: '/assistant-icons/1F525.svg' },
  { id: '1F9EF', name: '灭火器', src: '/assistant-icons/1F9EF.svg' },
  { id: '1F512', name: '锁定', src: '/assistant-icons/1F512.svg' },
  { id: '1F513', name: '解锁', src: '/assistant-icons/1F513.svg' },
  { id: '1F511', name: '钥匙', src: '/assistant-icons/1F511.svg' },
  { id: '1F4CC', name: '图钉', src: '/assistant-icons/1F4CC.svg' },
  { id: '1F3C1', name: '旗帜', src: '/assistant-icons/1F3C1.svg' },
  // 文书 / 归档
  { id: '1F4DD', name: '备忘录', src: '/assistant-icons/1F4DD.svg' },
  { id: '1F4BC', name: '公文包', src: '/assistant-icons/1F4BC.svg' },
  { id: '1F4D1', name: '标签页', src: '/assistant-icons/1F4D1.svg' },
  { id: '1F4D2', name: '账本', src: '/assistant-icons/1F4D2.svg' },
  { id: '1F4D6', name: '开本书', src: '/assistant-icons/1F4D6.svg' },
  { id: '1F4D5', name: '闭本书', src: '/assistant-icons/1F4D5.svg' },
  { id: '1F4C4', name: '文档页', src: '/assistant-icons/1F4C4.svg' },
  { id: '1F4C3', name: '卷边文档', src: '/assistant-icons/1F4C3.svg' },
  { id: '1F4C1', name: '文件夹', src: '/assistant-icons/1F4C1.svg' },
  { id: '1F4CE', name: '回形针', src: '/assistant-icons/1F4CE.svg' },
  { id: '1F4E5', name: '收件箱', src: '/assistant-icons/1F4E5.svg' },
  { id: '1F4E4', name: '发件箱', src: '/assistant-icons/1F4E4.svg' },
  { id: '1F4F0', name: '新闻稿', src: '/assistant-icons/1F4F0.svg' },
  { id: '1F3ED', name: '工厂', src: '/assistant-icons/1F3ED.svg' },
  // 培训 / 汇报
  { id: '1F3EB', name: '培训教室', src: '/assistant-icons/1F3EB.svg' },
  { id: '1F3A8', name: '调色板', src: '/assistant-icons/1F3A8.svg' },
  { id: '1F9EA', name: '试管', src: '/assistant-icons/1F9EA.svg' },
  { id: '1F4E6', name: '包裹', src: '/assistant-icons/1F4E6.svg' },
  { id: '1F9F1', name: '砖块', src: '/assistant-icons/1F9F1.svg' },
  { id: '1F9F9', name: '拖把', src: '/assistant-icons/1F9F9.svg' },
  { id: '1F4E2', name: '喇叭', src: '/assistant-icons/1F4E2.svg' },
  { id: '1F3E2', name: '办公楼', src: '/assistant-icons/1F3E2.svg' },
];

export const DEFAULT_ASSISTANT_ICON = assistantIconPresets.default;
