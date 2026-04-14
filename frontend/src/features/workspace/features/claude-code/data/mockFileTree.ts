export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
  content?: string;
}

export const MOCK_FILE_TREE: FileNode[] = [
  {
    id: 'conversation-skills',
    name: 'conversation',
    path: 'conversation',
    type: 'directory',
    children: [
      {
        id: 'conversation/escalation.md',
        name: 'escalation.md',
        path: 'conversation/escalation.md',
        type: 'file',
        content: `# 客服升級處理流程

## 偵測條件
- 連續三次未能解決使用者需求
- 回覆時間超過 SLA 門檻
- 使用者提出退款或法律相關要求

## 推薦用語
- 「我會立即請資深夥伴協助處理,請稍候。」
- 「我們將升級處理優先度,確保儘快給您答覆。」

## 進階指示
1. 收集關鍵對話節錄
2. 標註使用者痛點與關鍵事件
3. 建立後續跟進提醒`,
      },
      {
        id: 'conversation/fallback.ts',
        name: 'fallback.ts',
        path: 'conversation/fallback.ts',
        type: 'file',
        content: `export default defineSkill({
  id: 'conversation/fallback',
  title: 'Fallback handling',
  triggers: ['fallback_detected'],
  handler: async ({ prompt, tools }) => {
    const summary = await tools.memory.summarize(prompt.conversation, { sentences: 2 });

    return tools.actions.composeResponse({
      tone: 'reassuring',
      message: [
        '我理解目前的情境可能有點複雜,讓我整理一下...',
        summary,
        '我會同步檢查有無適合的解決方案或請相關同仁協助。'
      ].join('\\n\\n'),
    });
  },
});`,
      },
    ],
  },
  {
    id: 'analysis',
    name: 'analysis',
    path: 'analysis',
    type: 'directory',
    children: [
      {
        id: 'analysis/root-cause.md',
        name: 'root-cause.md',
        path: 'analysis/root-cause.md',
        type: 'file',
        content: `# 根因分析模板

1. **情境整理**
   - 使用者敘述：
   - 系統日誌：

2. **假設與驗證**
   - 假設一：
   - 驗證方式：

3. **解決方案**
   - 短期緩解：
   - 長期修正：`,
      },
      {
        id: 'analysis/summarize.ts',
        name: 'summarize.ts',
        path: 'analysis/summarize.ts',
        type: 'file',
        content: `export default defineSkill({
  id: 'analysis/summarize',
  title: '對話摘要',
  triggers: ['session_ended'],
  handler: async ({ prompt, tools }) => {
    const summary = await tools.llm.complete({
      prompt: [
        '請條列式整理以下對話的摘要與待辦事項：',
        prompt.conversation.join('\\n'),
      ].join('\\n\\n'),
    });

    await tools.memory.save({
      category: 'summary',
      content: summary,
    });

    return summary;
  },
});`,
      },
    ],
  },
  {
    id: 'integrations',
    name: 'integrations',
    path: 'integrations',
    type: 'directory',
    children: [
      {
        id: 'integrations/crmSync.yaml',
        name: 'crmSync.yaml',
        path: 'integrations/crmSync.yaml',
        type: 'file',
        content: `pipeline:
  name: CRM同步
  on: ticket.resolved
  steps:
    - name: 尋找CRM紀錄
      action: crm.findTicket
      with:
        ticketId: \${context.ticket.id}
    - name: 更新處理摘要
      action: crm.updateTicket
      with:
        ticketId: \${steps.尋找CRM紀錄.result.id}
        resolution: \${context.summary}`,
      },
    ],
  },
];

export const isMarkdownFile = (filename: string) => filename.toLowerCase().endsWith('.md');

export const flattenFileTree = (nodes: FileNode[]): FileNode[] => {
  const result: FileNode[] = [];
  const walk = (node: FileNode) => {
    if (node.type === 'file') {
      result.push(node);
    }
    node.children?.forEach(walk);
  };
  nodes.forEach(walk);
  return result;
};

export const findFileNode = (nodes: FileNode[], path: string): FileNode | null => {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }
    if (node.children) {
      const found = findFileNode(node.children, path);
      if (found) {
        return found;
      }
    }
  }
  return null;
};
