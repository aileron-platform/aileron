---
sidebar_position: 8
title: Question Form
---

# Question Form

`<question-form>` is an interactive form block that agents and skills can use in chat for structured choices. It is intended for collecting a small number of explicit answers so users do not need to type option text manually and workflows can parse the response reliably.

## When To Use It

Prefer `<question-form>` when the question meets these conditions:

- The user needs to choose one or more answers from a small fixed option set.
- The answer directly affects a workflow branch, setting, or output format.
- The options can be described clearly with short user-facing text.
- The user has not already provided a clear answer earlier in the conversation.

Common use cases:

- Flow selection, such as `詳細 flow` / `快速 flow`.
- Preview mode, such as `SVG 快速預覽` / `imagegen 高擬真預覽`.
- Output format, such as `.pptx` / `HTML 簡報` / `兩者都要`.
- Authorization, such as whether to allow subagents or parallel agents.
- A small fixed set of page, mode, or strategy choices.

## When Not To Use It

Do not turn every question into a form. Use normal chat, review pages, or another dedicated interface for:

- Free-form requirements, background, or brainstorming.
- Slide review, page annotations, region marking, or visual feedback.
- Review payloads or copied feedback content returned by the user.
- Debugging, error analysis, technical explanation, or iterative discussion.
- Cases where the user has already answered clearly and the agent should continue.

## Output Rules

When an agent chooses to use `<question-form>`, the reply for that turn should contain only the form block. Do not add prose before or after it.

```xml
<question-form id="ppt-output-format" title="請選擇輸出格式">
{
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [".pptx", "HTML 簡報", "兩者都要"],
      "required": true
    }
  ]
}
</question-form>
```

## Field Guidance

| Field | Description |
| --- | --- |
| `id` | Stable form identifier used when parsing the answer. Use snake_case or kebab-case. |
| `title` | User-facing form title that describes the choice. |
| `questions[].id` | Stable question identifier that maps to the workflow setting or branch. |
| `questions[].label` | Short question label. |
| `questions[].type` | Common values include `radio`, `select`, `checkbox`, `textarea`, `text`, and `direction-cards`. |
| `questions[].options` | Fixed options. Option text should be suitable for direct display to users. |
| `questions[].required` | Set to `true` for required questions. |

## PPT Skill Examples

### Flow Selection

```xml
<question-form id="ppt-flow-choice" title="請選擇簡報製作流程">
{
  "questions": [
    {
      "id": "flow",
      "label": "流程模式",
      "type": "radio",
      "options": ["詳細 flow", "快速 flow"],
      "required": true
    }
  ]
}
</question-form>
```

### Preview Mode

```xml
<question-form id="ppt-preview-mode" title="請選擇風格預覽方式">
{
  "questions": [
    {
      "id": "preview_mode",
      "label": "預覽方式",
      "type": "radio",
      "options": ["SVG 快速預覽", "imagegen 高擬真預覽"],
      "required": true
    }
  ]
}
</question-form>
```

### Output Format

```xml
<question-form id="ppt-output-format" title="請選擇輸出格式">
{
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [".pptx", "HTML 簡報", "兩者都要"],
      "required": true
    }
  ]
}
</question-form>
```

## Design Principle

`<question-form>` should make choices easier for the user, not expose internal workflow details. Form text should describe what the user can see, choose, or act on. Do not put tool names, file paths, runtime state, manifests, worker metadata, or other implementation details in the form.
