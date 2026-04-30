import React from 'react';
import ClaudeToolWidget, { ClaudeToolType, ToolResultBlock, PermissionScope } from '@/features/agent-tools/components/ClaudeToolWidget';
import { Card } from '@/shared/components/ui/card';

/**
 * ClaudeToolWidgetDemo
 * 
 * 參考 workspace-runtime/complete_claude_tools_test_final.json 中的工具調用範例
 * 展示各種 Claude Code 工具的 Widget 呈現
 */
const ClaudeToolWidgetDemo: React.FC = () => {
  return (
    <div className="h-full w-full overflow-y-auto bg-gray-50">
      <div className="max-w-4xl mx-auto space-y-12 p-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold text-gray-900">Claude Tool Widget Demo</h1>
        <p className="text-gray-600">
          基於 <code>workspace-runtime/complete_claude_tools_test_final.json</code> 的真實工具調用範例展示，並補齊所有共用元件的演示。
        </p>

        {/* 狀態燈號說明 */}
        <div className="flex items-center gap-4 text-sm bg-white p-3 rounded-lg border border-gray-200 w-fit">
          <span className="font-semibold text-gray-700">狀態說明:</span>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
            <span className="text-gray-600">Completed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-gray-600">In Progress</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
            <span className="text-gray-600">Error</span>
          </div>
        </div>
      </div>

      {/* 1. TodoWrite (更新狀態) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">1. TodoWrite (更新任務狀態)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於管理和更新任務清單的狀態。
            <br />
            <strong>Input:</strong> <code>todos</code> (Array of {'{ status, content, activeForm }'})
          </p>
          <ClaudeToolWidget
            toolType="TodoWrite"
            status="completed"
            input={{
              "todos": [
                {
                  "status": "completed",
                  "content": "測試文件讀取工具 (Read)",
                  "activeForm": "測試文件讀取工具 (Read)"
                },
                {
                  "status": "in_progress",
                  "content": "測試命令執行工具 (Bash)",
                  "activeForm": "測試命令執行工具 (Bash)"
                },
                {
                  "status": "pending",
                  "content": "測試網頁搜索工具 (WebSearch)",
                  "activeForm": "測試網頁搜索工具 (WebSearch)"
                }
              ]
            }}
          />
        </div>
      </section>

      {/* 2. Write (寫入文件) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">2. Write (寫入文件)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於創建或覆蓋文件內容。
            <br />
            <strong>Input:</strong> <code>file_path</code>, <code>content</code>
          </p>
          <ClaudeToolWidget
            toolType="Write"
            status="completed"
            input={{
              "content": "這是一個測試文件，用於驗證 Claude Code 的 Write 工具功能。\n\n創建時間：2025-06-17\n測試內容：\n1. 中文文字支持\n2. 英文文字 support\n3. 數字：12345\n4. 符號：!@#$%^&*()\n\n這個文件將被後續的 Read 和 Edit 工具使用進行測試。",
              "file_path": "/tmp/claude_test_file.txt"
            }}
            output="Successfully wrote to /tmp/claude_test_file.txt"
          />
        </div>
      </section>

      {/* 3. Bash (執行命令) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">3. Bash (執行命令)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            執行 Shell 命令。
            <br />
            <strong>Input:</strong> <code>command</code>, <code>description</code>
          </p>
          
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-700">範例 A: List Files</h3>
            <ClaudeToolWidget
              toolType="Bash"
              status="completed"
              input={{
                "command": "ls -la",
                "description": "List files in current directory"
              }}
              output={`total 24
drwxr-xr-x  4 user  staff  128 Dec  6 07:58 .
drwxr-xr-x  6 user  staff  192 Dec  6 07:58 ..
-rw-r--r--  1 user  staff  102 Dec  6 07:58 test_write.txt
drwxr-xr-x  2 user  staff   64 Dec  6 07:58 test_files`}
            />

            <h3 className="text-sm font-medium text-gray-700">範例 B: Check Working Directory</h3>
            <ClaudeToolWidget
              toolType="Bash"
              status="completed"
              input={{
                "command": "pwd",
                "description": "Check current working directory"
              }}
              output="/workspace-runtime"
            />
          </div>
        </div>
      </section>

      {/* 4. Glob (文件搜索) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">4. Glob (文件搜索)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            使用 Glob 模式搜索文件。
            <br />
            <strong>Input:</strong> <code>pattern</code>
          </p>
          <ClaudeToolWidget
            toolType="Glob"
            status="completed"
            input={{
              "pattern": "**/*.py"
            }}
            output={`app/__init__.py
app/main.py
app/database/__init__.py
app/models/user.py
app/utils/helpers.py`}
          />
        </div>
      </section>

      {/* 5. Grep (內容搜索) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">5. Grep (內容搜索)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            搜索文件內容。
            <br />
            <strong>Input:</strong> <code>pattern</code>, <code>glob</code> (optional), <code>output_mode</code> (optional)
          </p>
          <ClaudeToolWidget
            toolType="Grep"
            status="completed"
            input={{
              "pattern": "Claude",
              "head_limit": 10,
              "output_mode": "content"
            }}
            output={`app/main.py:10:    print("Hello Claude")
docs/README.md:5: This project uses Claude for AI assistance.`}
          />
        </div>
      </section>

      {/* 6. Read (讀取文件) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">6. Read (讀取文件)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            讀取文件內容。
            <br />
            <strong>Input:</strong> <code>file_path</code>, <code>limit</code> (optional)
          </p>
          <ClaudeToolWidget
            toolType="Read"
            status="completed"
            input={{
              "file_path": "/workspace-runtime/pyproject.toml",
              "limit": 10
            }}
            output={`1→[tool.poetry]
2→name = "workspace-runtime"
3→version = "0.1.0"
4→description = ""
5→authors = ["Your Name <you@example.com>"]
6→
7→[tool.poetry.dependencies]
8→python = "^3.10"
9→fastapi = "^0.109.0"
10→uvicorn = "^0.27.0"`}
          />
        </div>
      </section>

      {/* 7. WebSearch (網頁搜索) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">7. WebSearch (網頁搜索)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            執行網絡搜索。
            <br />
            <strong>Input:</strong> <code>query</code>
          </p>
          <ClaudeToolWidget
            toolType="WebSearch"
            status="completed"
            input={{
              "query": "Gemini CLI documentation"
            }}
            output={[
              {
                "title": "Gemini API Overview | Google AI for Developers",
                "url": "https://ai.google.dev/gemini-api/docs",
                "snippet": "Build with the Gemini API. Get started with the Gemini API to build AI-powered applications."
              },
              {
                "title": "Gemini - Google DeepMind",
                "url": "https://deepmind.google/technologies/gemini/",
                "snippet": "Gemini is our most capable and general model, built to be multimodal and efficient."
              }
            ]}
          />
        </div>
      </section>

      {/* 新增的元件演示 */}

      {/* 8. Edit (編輯文件) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">8. Edit (編輯文件)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於修改文件內容，顯示修改前後的差異。
            <br />
            <strong>Input:</strong> <code>file_path</code>, <code>old_string</code>, <code>new_string</code>
          </p>
          <ClaudeToolWidget
            toolType="Edit"
            status="completed"
            input={{
              "file_path": "/workspace-runtime/test_files/test_edit.txt",
              "old_string": "Hello World!\nThis is the original content.",
              "new_string": "Hello Gemini!\nThis is the modified content."
            }}
            output="Successfully edited /workspace-runtime/test_files/test_edit.txt"
          />
        </div>
      </section>

      {/* 9. LS (列出目錄) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">9. LS (列出目錄)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            列出指定路徑下的文件和目錄。
            <br />
            <strong>Input:</strong> <code>path</code>
          </p>
          <ClaudeToolWidget
            toolType="LS"
            status="completed"
            input={{
              "path": "/workspace-runtime/"
            }}
            output={`- app/
- docs/
- tests/
- pyproject.toml
- README.md
- main.py
NOTE: The above is a simplified representation.`}
          />
        </div>
      </section>

      {/* 10. Task (代理任務) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">10. Task (代理任務)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於委派子代理執行複雜任務。
            <br />
            <strong>Input:</strong> <code>prompt</code>, <code>description</code>, <code>subagent_type</code>
          </p>
          <ClaudeToolWidget
            toolType="Task"
            status="completed"
            input={{
              "prompt": "請搜索當前工作目錄，找到所有的 Python 測試文件（test_*.py），並報告找到的文件數量和它們的路徑。請使用 Glob 工具來完成這個任務。",
              "description": "測試搜索當前目錄",
              "subagent_type": "general-purpose"
            }}
            output="Subagent completed the task. Found 3 Python test files."
          />
        </div>
      </section>

      {/* 11. WebFetch (網頁抓取) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">11. WebFetch (網頁抓取)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            從指定 URL 抓取網頁內容。
            <br />
            <strong>Input:</strong> <code>url</code>
          </p>
          <ClaudeToolWidget
            toolType="WebFetch"
            status="completed"
            input={{
              "url": "https://www.anthropic.com/news/claude-3-5-sonnet"
            }}
            output={`# Claude 3.5 Sonnet is here!

Today, we're excited to announce Claude 3.5 Sonnet, our newest, most intelligent model. It's the fastest and most cost-effective model in the Claude 3.5 family, outperforming all other models across various benchmarks.

## Key Features

*   **Speed:** Up to 2x faster than Claude 3 Opus.
*   **Cost-effectiveness:** 5x cheaper than Claude 3 Opus.
*   **Performance:** Achieves new state-of-the-art results in vision, coding, and mathematical reasoning.`}
          />
        </div>
      </section>

      {/* 12. PermissionRequest (權限請求) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">12. PermissionRequest (權限請求)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            模擬代理請求用戶批准執行某個操作，支援四種 Agent SDK：
            <br />
            <strong>Agent SDK：</strong> Claude Code、Codex (OpenAI)、Gemini (Google)、OpenCode
            <br />
            <strong>狀態：</strong> 等待中 (isWaiting)、待批准 (pending)、已批准 (approved)、已拒絕 (denied)
          </p>

          <div className="space-y-6">
            {/* Claude Code 權限請求 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">A. Claude Code - 權限範圍選擇</h3>
              <p className="text-xs text-gray-500 mb-2">支援 ONCE / SESSION / PROJECT / USER / LOCAL 範圍</p>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="in_progress"
                agentTool="claude-code"
                input={{
                  "tool_name": "Bash",
                  "tool_input": {
                    "command": "rm -rf ./temp/*",
                    "description": "清理暫存檔案"
                  },
                  "reason": "代理需要執行命令來清理暫存目錄中的檔案。",
                  "message_id": "msg_claude_001",
                  "permission_status": "pending"
                }}
                requested_at={new Date().toISOString()}
                onApprove={(msgId, scope) => console.log(`Claude Code Approved: ${msgId}, Scope: ${scope}`)}
                onDeny={(msgId) => console.log(`Denied: ${msgId}`)}
              />
            </div>

            {/* Codex 權限請求 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">B. Codex (OpenAI) - Sandbox + Approval Policy</h3>
              <p className="text-xs text-gray-500 mb-2">雙重設定：Sandbox 模式 (read-only/workspace-write/full-access) + 批准政策 (untrusted/on-request/on-failure/never)</p>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="in_progress"
                agentTool="codex"
                input={{
                  "tool_name": "Write",
                  "tool_input": {
                    "file_path": "/workspace/src/config.ts",
                    "content": "export const config = { apiKey: 'xxx' };"
                  },
                  "reason": "代理需要寫入設定檔案。",
                  "message_id": "msg_codex_001",
                  "permission_status": "pending"
                }}
                requested_at={new Date().toISOString()}
                onCodexApprove={(msgId, sandbox, approval) => console.log(`Codex Approved: ${msgId}, Sandbox: ${sandbox}, Approval: ${approval}`)}
                onDeny={(msgId) => console.log(`Denied: ${msgId}`)}
              />
            </div>

            {/* Gemini 權限請求 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">C. Gemini (Google) - 批准模式</h3>
              <p className="text-xs text-gray-500 mb-2">支援 default / autoEdit / yolo 模式</p>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="in_progress"
                agentTool="gemini"
                input={{
                  "tool_name": "mcp__git__commit",
                  "tool_input": {
                    "message": "feat: add new feature",
                    "files": ["src/index.ts", "src/utils.ts"]
                  },
                  "reason": "代理需要提交程式碼變更到 Git 儲存庫。",
                  "message_id": "msg_gemini_001",
                  "permission_status": "pending"
                }}
                requested_at={new Date().toISOString()}
                onGeminiApprove={(msgId, mode) => console.log(`Gemini Approved: ${msgId}, Mode: ${mode}`)}
                onDeny={(msgId) => console.log(`Denied: ${msgId}`)}
              />
            </div>

            {/* OpenCode 權限請求 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">D. OpenCode - 批准模式</h3>
              <p className="text-xs text-gray-500 mb-2">支援 default / acceptEdits / bypassPermissions 模式</p>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="in_progress"
                agentTool="opencode"
                input={{
                  "tool_name": "Edit",
                  "tool_input": {
                    "file_path": "/workspace/package.json",
                    "old_string": "\"version\": \"1.0.0\"",
                    "new_string": "\"version\": \"1.1.0\""
                  },
                  "reason": "代理需要更新 package.json 的版本號。",
                  "message_id": "msg_opencode_001",
                  "permission_status": "pending"
                }}
                requested_at={new Date().toISOString()}
                onOpenCodeApprove={(msgId, mode) => console.log(`OpenCode Approved: ${msgId}, Mode: ${mode}`)}
                onDeny={(msgId) => console.log(`Denied: ${msgId}`)}
              />
            </div>

            {/* 狀態範例：等待中 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">E. 狀態範例 - 等待中 (Waiting)</h3>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="pending"
                agentTool="claude-code"
                isWaiting={true}
                input={{
                  "tool_name": "Write",
                  "tool_input": {
                    "file_path": "/etc/config.json",
                    "content": "{ \"key\": \"value\" }"
                  },
                  "reason": "代理需要寫入設定檔案。",
                  "message_id": "msg_waiting_001",
                  "permission_status": "pending"
                }}
              />
            </div>

            {/* 狀態範例：已批准 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">F. 狀態範例 - 已批准 (Approved)</h3>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="completed"
                agentTool="gemini"
                input={{
                  "tool_name": "Read",
                  "tool_input": {
                    "file_path": "/workspace/src/main.ts"
                  },
                  "message_id": "msg_approved_001",
                  "permission_status": "approved",
                  "approved_at": new Date(Date.now() - 60000).toISOString()
                }}
              />
            </div>

            {/* 狀態範例：已拒絕 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">G. 狀態範例 - 已拒絕 (Denied)</h3>
              <ClaudeToolWidget
                toolType="PermissionRequest"
                status="error"
                agentTool="codex"
                input={{
                  "tool_name": "Bash",
                  "tool_input": {
                    "command": "sudo rm -rf /",
                    "description": "危險操作"
                  },
                  "message_id": "msg_denied_001",
                  "permission_status": "denied",
                  "denied_at": new Date(Date.now() - 120000).toISOString()
                }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* 13. Thinking (思考過程) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">13. Thinking (思考過程)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            顯示代理的思考過程，通常以 Markdown 格式呈現。
            <br />
            <strong>Input:</strong> <code>thinking</code>
          </p>
          <ClaudeToolWidget
            toolType="Thinking"
            status="in_progress"
            input={{
              "thinking": "我正在分析當前檔案結構，準備定位與使用者請求相關的文件。\n\n**步驟:**\n1. 讀取 `README.md` 以了解專案概況。\n2. `Glob` 搜尋所有 `.js` 和 `.ts` 檔案。\n3. 分析 `package.json` 以識別依賴。"
            }}
          />
        </div>
      </section>

      {/* 14. SystemInit (系統初始化) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">14. SystemInit (系統初始化)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            顯示會話的初始化信息，包括會話ID、模型、當前工作目錄和可用工具列表。
            <br />
            <strong>Input:</strong> <code>sessionId</code>, <code>model</code>, <code>cwd</code>, <code>tools</code>
          </p>
          <ClaudeToolWidget
            toolType="SystemInit"
            status="completed"
            input={{
              "sessionId": "sess_example_12345",
              "model": "claude-3-opus-20240229",
              "cwd": "/Users/chenshengyang/Documents/aileron/workspace-runtime",
              "tools": [
                "Read", "Write", "Edit", "Bash", "Glob", "Grep", "TodoWrite", "Task", "WebSearch", "WebFetch",
                "mcp__git__clone", "mcp__git__status"
              ]
            }}
          />
        </div>
      </section>

      {/* 15. MCP (Managed Code Plugin) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">15. MCP (Managed Code Plugin)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於展示通過 MCP 調用的工具，格式為 <code>mcp__namespace__method</code>。
            <br />
            <strong>Input:</strong> 任意 JSON 結構，取決於具體 MCP 工具。
          </p>
          <ClaudeToolWidget
            toolType="mcp__git__status"
            status="completed"
            input={{
              "path": "/workspace/my-repo"
            }}
            output={`On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean`}
          />
          <div className="mt-4">
            <ClaudeToolWidget
              toolType="mcp__docker__build_image"
              status="error"
              input={{
                "path": "./app",
                "tag": "my-app:latest"
              }}
              error="Error: Docker daemon not running."
            />
          </div>
        </div>
      </section>

      {/* 16. AskUserQuestion (用戶問題詢問) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">16. AskUserQuestion (用戶問題詢問)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於向用戶詢問問題並收集回答，支援單選和多選模式。
            <br />
            <strong>Input:</strong> <code>questions</code> (Array of {'{ header, question, options[], multiSelect }'})
          </p>

          <div className="space-y-6">
            {/* 單選問題範例 - 待回答 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">A. 單選問題 - 待回答狀態</h3>
              <ClaudeToolWidget
                toolType="AskUserQuestion"
                status="in_progress"
                input={{
                  "questions": [
                    {
                      "header": "任務類型",
                      "question": "您希望我執行什麼類型的任務？",
                      "options": [
                        {
                          "label": "探索程式碼庫",
                          "description": "搜尋和了解現有的程式碼結構和架構"
                        },
                        {
                          "label": "實作新功能",
                          "description": "添加新的功能或模組到專案中"
                        },
                        {
                          "label": "修復錯誤",
                          "description": "識別和修復程式碼中的問題"
                        },
                        {
                          "label": "重構程式碼",
                          "description": "改善現有程式碼的結構和效能"
                        }
                      ],
                      "multiSelect": false
                    }
                  ]
                }}
                onAskUserQuestionSubmit={(answers) => console.log('Single select submitted:', answers)}
                onAskUserQuestionCancel={() => console.log('Cancelled')}
              />
            </div>

            {/* 多選問題範例 - 待回答 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">B. 多選問題 - 待回答狀態</h3>
              <ClaudeToolWidget
                toolType="AskUserQuestion"
                status="in_progress"
                input={{
                  "questions": [
                    {
                      "header": "功能選擇",
                      "question": "您想要啟用哪些功能？（可多選）",
                      "options": [
                        {
                          "label": "自動格式化",
                          "description": "在儲存時自動格式化程式碼"
                        },
                        {
                          "label": "語法檢查",
                          "description": "即時檢查程式碼語法錯誤"
                        },
                        {
                          "label": "自動補全",
                          "description": "提供智能程式碼建議"
                        }
                      ],
                      "multiSelect": true
                    }
                  ]
                }}
                onAskUserQuestionSubmit={(answers) => console.log('Multi select submitted:', answers)}
              />
            </div>

            {/* 多個問題範例 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">C. 多個問題 - 待回答狀態</h3>
              <ClaudeToolWidget
                toolType="AskUserQuestion"
                status="in_progress"
                input={{
                  "questions": [
                    {
                      "header": "框架選擇",
                      "question": "您想使用哪個 UI 框架？",
                      "options": [
                        {
                          "label": "React",
                          "description": "使用 React 進行前端開發"
                        },
                        {
                          "label": "Vue",
                          "description": "使用 Vue.js 進行前端開發"
                        }
                      ],
                      "multiSelect": false
                    },
                    {
                      "header": "樣式方案",
                      "question": "您偏好哪種樣式方案？",
                      "options": [
                        {
                          "label": "Tailwind CSS",
                          "description": "使用 utility-first 的 CSS 框架"
                        },
                        {
                          "label": "CSS Modules",
                          "description": "使用模組化的 CSS"
                        },
                        {
                          "label": "Styled Components",
                          "description": "使用 CSS-in-JS 方案"
                        }
                      ],
                      "multiSelect": false
                    }
                  ]
                }}
                onAskUserQuestionSubmit={(answers) => console.log('Multiple questions submitted:', answers)}
              />
            </div>

            {/* 已完成狀態 */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">D. 已完成狀態</h3>
              <ClaudeToolWidget
                toolType="AskUserQuestion"
                status="completed"
                input={{
                  "questions": [
                    {
                      "header": "確認",
                      "question": "您確定要執行此操作嗎？",
                      "options": [
                        {
                          "label": "是，繼續",
                          "description": "執行操作並繼續"
                        },
                        {
                          "label": "否，取消",
                          "description": "取消操作"
                        }
                      ],
                      "multiSelect": false
                    }
                  ]
                }}
                output="使用者已回答問題"
                isAskUserQuestionSubmitted={true}
                askUserQuestionAnswers={{ "q0": "是，繼續" }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* 17. Generic Tool (未知或通用工具) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-800 border-b pb-2">17. Generic Tool (未知或通用工具)</h2>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-4">
            用於展示任何未明確定義 Widget 的工具，會將 Input 和 Output 作為 JSON 顯示。
            <br />
            <strong>Input:</strong> 任意 JSON
            <br />
            <strong>Output:</strong> 任意 JSON
          </p>
          <ClaudeToolWidget
            toolType="CustomTool"
            status="completed"
            input={{
              "action": "process_data",
              "data_id": "abc-123",
              "options": {
                "verbose": true,
                "timeout": 60
              }
            }}
            output={{
              "status": "success",
              "processed_records": 1500,
              "duration_ms": 1200
            }}
          />
        </div>
      </section>
      </div>
    </div>
  );
};

export default ClaudeToolWidgetDemo;
