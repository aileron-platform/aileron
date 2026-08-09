---
title: Aileron MCP Tools
---

# Aileron MCP Tools

Aileron currently provides two built-in MCP tools for agents. Both are registered by `workspace-runtime/app/modules/thread/mcp/server.py`:

| Tool | Purpose | Pauses the turn? |
| --- | --- | --- |
| `mcp__aileron__ask_user_question` | Present a structured option form and collect the user's answers | Yes; the turn must end immediately after the call |
| `mcp__aileron__show_canvas_artifact` | Display a card notifying the user that a Canvas artifact has been produced | No; output may continue after the call |

For when and why to use `ask_user_question`, see [Question Form](/features/workspace/ai-agent/ai-chat). This page documents the complete invocation rules and JSON schemas for both tools.

## ask_user_question

### ask_user_question Invocation Rules

When an agent decides to use a form, it should call:

```text
mcp__aileron__ask_user_question
```

The agent must end the turn immediately after the call and must not output any additional assistant text. After the user submits the form, the platform resumes the agent with a subsequent user message.

`questions` must contain at least one and at most five items. Before calling the tool, the agent should remove questions that do not change the result and provide a `default` whenever the brief supports a reasonable inference.

Example arguments:

```json
{
  "id": "ppt-output-format",
  "title": "Choose an output format",
  "questions": [
    {
      "id": "output_formats",
      "label": "Output format",
      "type": "radio",
      "options": [
        ".pptx",
        "HTML presentation",
        "Both"
      ],
      "default": ".pptx",
      "required": true
    }
  ]
}
```

### Field Guidance

| Field | Description |
| --- | --- |
| `id` | Stable identifier used to parse the answer later. Use snake_case or kebab-case. |
| `title` | Form title. Describe the choice in terms the user can understand. |
| `questions[].id` | Question identifier. It should map to a setting or branch needed by the workflow. |
| `questions[].label` | Question label. Keep it concise. |
| `questions[].type` | Supported types: `radio`, `checkbox`, `select`, `text`, `textarea`, `number`, `date`, `yes-no`, `option-cards`, and `color`. |
| `questions[].options` | Fixed options for `radio` / `checkbox` / `select`. The text should be ready to present directly to the user. |
| `questions[].default` | Optional prefilled answer. Use a string for single-value and text fields, and a string array for `checkbox` or `multiple` fields. Defaults participate in `show_if` and `options_by`. |
| `questions[].required` | Set to `true` for a required question. |
| `questions[].show_if` | Conditional display. Use `{ "q": "<id of an earlier question>", "eq": "value" }`. It also supports exactly one of `in` (a list of values) or `not_empty` (show after any answer). When the condition is false, the question is hidden, is not treated as required, and its answer is not submitted. |
| `questions[].options_by` | Dynamic options. Use `{ "q": "<id of an earlier question>", "map": { "source answer": ["option"] } }`. This applies only to `radio` / `checkbox` / `select`. When the source has not been answered or no map entry matches, it falls back to `options`. |

### Answer Format

The answer sent back to the agent begins with `[form answers — <id>]` and includes one `- ` item for every visible question. Unanswered questions emit `(skipped)`. When an `option-cards` card id differs from its label, the answer is `Label [value: card-id]`. Hidden questions are not submitted.

### Field Types

#### `radio` / `checkbox` / `select`

Single-choice, multi-choice, or dropdown input with fixed `options`.

#### `text` / `textarea`

Open-ended single-line or multi-line input. May include `placeholder`.

#### `number`

Numeric input. Supported fields:

| Field | Description |
| --- | --- |
| `min` / `max` | Numeric range. The submitted value is clamped to this range. |
| `step` | Step size; defaults to `1`. |
| `unit` | Unit label displayed on the right side of the input. It is presentational only and is not included in the answer. |

```json
{
  "id": "ppt-page-count",
  "title": "Set the presentation page count",
  "questions": [
    {
      "id": "page_count",
      "label": "Pages",
      "type": "number",
      "min": 1,
      "max": 30,
      "step": 1,
      "unit": "pages",
      "required": true
    }
  ]
}
```

#### `date`

Date or date-time input.

| Field | Description |
| --- | --- |
| `mode` | `"date"` (default) or `"datetime"`. |
| `min` / `max` | ISO strings constraining the selectable range. |

```json
{
  "id": "project-deadline",
  "title": "Choose a deadline",
  "questions": [
    {
      "id": "deadline",
      "label": "Deadline",
      "type": "date",
      "required": true
    }
  ]
}
```

#### `yes-no`

Binary confirmation.

| Field | Description |
| --- | --- |
| `yes_label` / `no_label` | Custom text for the two buttons. When omitted, the system locale defaults are used. |

```json
{
  "id": "allow-subagent",
  "title": "Allow a subagent?",
  "questions": [
    {
      "id": "allow_subagent",
      "label": "Allow subagent",
      "type": "yes-no",
      "yes_label": "Allow",
      "no_label": "Deny",
      "required": true
    }
  ]
}
```

#### `option-cards`

Card-based options with richer presentation than `radio` / `select`.

| Field | Description |
| --- | --- |
| `multiple` | Set to `true` to enable multiple selection. Defaults to single selection. |
| `cards[].id` | Card identifier. |
| `cards[].label` | Display text and the submitted answer. |
| `cards[].description` | Secondary description for the card. |
| `cards[].icon` | Icon name from [lucide-react](https://lucide.dev/icons). |
| `cards[].mood` | Optional mood/tone label used to vary presentation style. |
| `cards[].palette` | Color array, displayed as swatches when `icon` is not set. |
| `cards[].displayFont` / `cards[].bodyFont` | Fonts for the card title/description, used for design direction. |

When both `icon` and `palette` are present, the icon takes precedence.

```json
{
  "id": "doc-type",
  "title": "Choose a document type",
  "questions": [
    {
      "id": "doc_type",
      "label": "Document type",
      "type": "option-cards",
      "required": true,
      "cards": [
        {
          "id": "blog",
          "label": "Blog",
          "description": "Conversational and story-driven",
          "icon": "feather"
        },
        {
          "id": "api",
          "label": "API documentation",
          "description": "Structured and searchable",
          "icon": "code"
        },
        {
          "id": "tutorial",
          "label": "Tutorial",
          "description": "Step-by-step guidance",
          "icon": "book-open"
        }
      ]
    }
  ]
}
```

##### Design direction (retaining `palette` and fonts)

```json
{
  "id": "visual-direction",
  "title": "Choose a visual direction",
  "questions": [
    {
      "id": "style",
      "label": "Visual direction",
      "type": "option-cards",
      "required": true,
      "cards": [
        {
          "id": "minimal",
          "label": "Minimal — clean / restrained",
          "description": "Generous whitespace and a disciplined typographic hierarchy.",
          "palette": [
            "#FFFFFF",
            "#F5F5F5",
            "#1A1A1A",
            "#0066FF"
          ],
          "displayFont": "Inter, sans-serif",
          "bodyFont": "Inter, sans-serif"
        },
        {
          "id": "editorial",
          "label": "Editorial — magazine / depth",
          "description": "Serif typography with a carefully considered layout.",
          "palette": [
            "#F8F4EF",
            "#2C1810",
            "#8B4513",
            "#D4A853"
          ],
          "displayFont": "'Playfair Display', serif",
          "bodyFont": "'Lora', serif"
        }
      ]
    }
  ]
}
```

#### `color`

Color picker.

| Field | Description |
| --- | --- |
| `swatches` | Array of preset color swatches as hex strings. |
| `allow_custom` | Whether to display a custom color picker. Defaults to `true`. |

The submitted value is normalized to a lowercase, seven-character hex value, such as `#ff6b6b`.

```json
{
  "id": "brand-color",
  "title": "Choose a primary brand color",
  "questions": [
    {
      "id": "brand_color",
      "label": "Primary brand color",
      "type": "color",
      "swatches": [
        "#FF6B6B",
        "#4ECDC4",
        "#FFE66D",
        "#1A1A1A"
      ],
      "required": true
    }
  ]
}
```

### Conditional Logic

`show_if` and `options_by` may reference only questions that appear earlier. An invalid reference is ignored: the question remains visible or uses fixed `options`, and the form does not fail. The answer of a hidden question is treated as empty while other conditions are evaluated, so conditions cascade.

```json
{
  "id": "deploy-survey",
  "title": "Deployment survey",
  "questions": [
    {
      "id": "target",
      "label": "Deployment type",
      "type": "radio",
      "options": [
        "Cloud",
        "On-premise"
      ],
      "required": true
    },
    {
      "id": "region",
      "label": "Region",
      "type": "select",
      "show_if": {
        "q": "target",
        "eq": "Cloud"
      },
      "options_by": {
        "q": "target",
        "map": {
          "Cloud": [
            "ap-northeast-1",
            "us-west-2"
          ]
        }
      }
    },
    {
      "id": "notes",
      "label": "Data center notes",
      "type": "textarea",
      "show_if": {
        "q": "target",
        "eq": "On-premise"
      }
    }
  ]
}
```

### PPT Skill Examples

#### Flow Selection

```json
{
  "id": "ppt-flow-choice",
  "title": "Choose a presentation creation workflow",
  "questions": [
    {
      "id": "flow",
      "label": "Workflow mode",
      "type": "radio",
      "options": [
        "Detailed flow",
        "Quick flow"
      ],
      "required": true
    }
  ]
}
```

#### Preview Method

```json
{
  "id": "ppt-preview-mode",
  "title": "Choose a style preview method",
  "questions": [
    {
      "id": "preview_mode",
      "label": "Preview method",
      "type": "radio",
      "options": [
        "SVG quick preview",
        "imagegen high-fidelity preview"
      ],
      "required": true
    }
  ]
}
```

#### Output Format

```json
{
  "id": "ppt-output-format",
  "title": "Choose an output format",
  "questions": [
    {
      "id": "output_formats",
      "label": "Output format",
      "type": "radio",
      "options": [
        ".pptx",
        "HTML presentation",
        "Both"
      ],
      "required": true
    }
  ]
}
```

## show_canvas_artifact

### show_canvas_artifact Invocation Rules

After producing a Canvas artifact (`canvas.json` and its content files), the agent should call:

```text
mcp__aileron__show_canvas_artifact
```

Unlike `ask_user_question`, this tool does not pause the turn. The agent may continue to output text after the call.

Example arguments:

```json
{
  "title": "Next.js Demo",
  "route": "/"
}
```

### Fields

| Field | Description |
| --- | --- |
| `title` | Required. Artifact name displayed on the notification card. |
| `route` | Optional. A route path from `canvas.json`, such as `/landing`. |

### Behavior

The frontend displays a card in the conversation with a title and open link. Selecting it opens the Canvas panel to inspect the artifact. The card itself does not interrupt or pause agent execution. For the complete `canvas.json` manifest contract, see [Canvas Protocol](/architecture/overview/canvas/protocol).
