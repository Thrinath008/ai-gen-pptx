# 12 HTML Slide Templates — Full Layout Specs
## AI PPTX Pipeline · Phase 2 Design System

All templates share the same **1280 × 720px canvas** (16:9).
CSS variables are injected at render time from `theme.json`.
Playwright captures at **deviceScaleFactor: 2** (1440dpi equivalent) for crisp EMU conversion.

---

## Global CSS — Injected Into Every Template

```css
/* --- THEME TOKENS (replaced at render time from theme.json) --- */
:root {
  --c-primary:    #1A6FA8;
  --c-secondary:  #0D9E75;
  --c-accent:     #F4A623;
  --c-bg:         #F7F9FC;
  --c-text-dark:  #1A1A2E;
  --c-text-light: #FFFFFF;
  --c-surface:    #FFFFFF;

  --f-heading: 'Montserrat', sans-serif;
  --f-body:    'Open Sans', sans-serif;
  --f-mono:    'Fira Code', monospace;
}

/* --- CANVAS --- */
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1280px; height: 720px; overflow: hidden; }
.slide {
  width: 1280px; height: 720px;
  background: var(--c-bg);
  font-family: var(--f-body);
  color: var(--c-text-dark);
  position: relative;
}

/* --- TYPOGRAPHY SCALE --- */
.t-hero    { font-family: var(--f-heading); font-size: 72px; font-weight: 800; line-height: 1.1; }
.t-h1      { font-family: var(--f-heading); font-size: 52px; font-weight: 700; line-height: 1.15; }
.t-h2      { font-family: var(--f-heading); font-size: 36px; font-weight: 700; line-height: 1.2; }
.t-h3      { font-family: var(--f-heading); font-size: 28px; font-weight: 600; }
.t-body    { font-size: 22px; line-height: 1.55; }
.t-small   { font-size: 18px; line-height: 1.5; }
.t-caption { font-size: 15px; opacity: 0.65; }

/* --- LAYOUT HELPERS --- */
.col-left   { position: absolute; left: 72px; top: 72px; width: 560px; height: 576px; }
.col-right  { position: absolute; right: 0; top: 0; width: 640px; height: 720px; }
.full-pad   { padding: 72px; }
.slide-tag  { position: absolute; top: 32px; right: 48px; font-size: 14px; font-family: var(--f-heading); font-weight: 600; color: var(--c-primary); opacity: 0.6; letter-spacing: 0.12em; text-transform: uppercase; }
.logo       { position: absolute; bottom: 28px; right: 48px; height: 36px; opacity: 0.8; }
.page-num   { position: absolute; bottom: 28px; left: 48px; font-size: 14px; opacity: 0.4; }
```

---

## Template 01 — `hero.html`

**Purpose:** Title slide. Full visual impact, sets the tone for the whole deck.
**Bloom:** Remember / None (pre-lesson)
**Coordinate map targets:** `#headline`, `#subheadline`, `#meta-block`

```
┌─────────────────────────────────────────────────────────────────┐
│  [FULL-BLEED BACKGROUND IMAGE with dark gradient overlay]       │
│                                                                  │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐       │
│   │  ACCENT LINE (4px, accent color, 80px wide)         │       │
│   │  HEADLINE (72px bold, white, max 2 lines)           │       │
│   │  SUBHEADLINE (28px, white 80% opacity, max 2 lines) │       │
│   │                                                     │       │
│   │  ─────────────────────────────────────────          │       │
│   │  Teacher Name · Class · Duration                    │       │
│   └─────────────────────────────────────────────────────┘       │
│                                          [SCHOOL LOGO]          │
└─────────────────────────────────────────────────────────────────┘
```

```html
<!-- hero.html -->
<div class="slide" id="slide-hero">
  <!-- Full-bleed image with overlay -->
  <div id="hero-image" style="
    position: absolute; inset: 0;
    background: url({{image_url}}) center/cover no-repeat;
  "></div>
  <div style="
    position: absolute; inset: 0;
    background: linear-gradient(
      to right,
      rgba(10,10,30, {{overlay_opacity}}) 55%,
      rgba(10,10,30, 0.2) 100%
    );
  "></div>

  <!-- Content block — left aligned, vertically centered -->
  <div style="
    position: absolute;
    left: 72px; top: 50%; transform: translateY(-50%);
    width: 660px;
  ">
    <!-- Accent line -->
    <div style="width: 80px; height: 5px; background: var(--c-accent); margin-bottom: 28px; border-radius: 2px;"></div>

    <h1 id="headline" class="t-hero" style="color: var(--c-text-light); margin-bottom: 20px;">
      {{headline}}
    </h1>

    <p id="subheadline" class="t-h3" style="color: rgba(255,255,255,0.82); margin-bottom: 48px; font-weight: 400;">
      {{subheadline}}
    </p>

    <!-- Divider -->
    <div style="width: 100%; height: 1px; background: rgba(255,255,255,0.25); margin-bottom: 24px;"></div>

    <p id="meta-block" class="t-small" style="color: rgba(255,255,255,0.65);">
      {{teacher_name}} &nbsp;·&nbsp; {{class_info}}
    </p>
  </div>

  <div class="slide-tag" style="color: rgba(255,255,255,0.5);">{{subject}}</div>
  <img class="logo" src="{{logo_url}}" />
</div>
```

---

## Template 02 — `learning_objectives.html`

**Purpose:** Set expectations. Checklist format with staggered entrance animation.
**Bloom:** Remember / Understand
**Coordinate map targets:** `#headline`, `.obj-item` (array)

```
┌──────────────────────────────────────────────────────────────────┐
│  [PRIMARY COLOR LEFT SIDEBAR — 16px wide]                        │
│                                                                   │
│  HEADLINE (52px)                    [DECORATIVE ICON / IMAGE]    │
│  intro_line (22px, muted)                                        │
│                                                                   │
│  ┌──┐  [VERB]  objective text                                    │
│  │✓ │  [VERB]  objective text                                    │
│  └──┘  [VERB]  objective text                                    │
│         [VERB]  objective text                                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- learning_objectives.html -->
<div class="slide" id="slide-objectives">
  <!-- Left sidebar accent -->
  <div style="position:absolute; left:0; top:0; width:16px; height:100%; background: var(--c-primary);"></div>

  <div class="col-left" style="left: 88px;">
    <p class="slide-tag" style="position:static; margin-bottom:20px;">Learning Objectives</p>
    <h1 id="headline" class="t-h1" style="margin-bottom: 16px; color: var(--c-primary);">
      {{headline}}
    </h1>
    <p class="t-body" style="color: rgba(26,26,46,0.55); margin-bottom: 48px;">
      {{intro_line}}
    </p>

    <!-- Objective items -->
    <div id="objectives-list" style="display: flex; flex-direction: column; gap: 20px;">
      {{#each objectives}}
      <div class="obj-item" style="display: flex; align-items: flex-start; gap: 20px;">
        <!-- Checkbox circle -->
        <div style="
          min-width: 40px; height: 40px; border-radius: 50%;
          background: var(--c-secondary);
          display: flex; align-items: center; justify-content: center;
          margin-top: 2px;
        ">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <p class="t-body">
          <strong style="color: var(--c-primary); font-family: var(--f-heading);">{{verb}}</strong>
          {{text}}
        </p>
      </div>
      {{/each}}
    </div>
  </div>

  <!-- Right side: decorative image or illustration -->
  <div class="col-right" style="
    background: url({{image_url}}) center/cover no-repeat;
    opacity: 0.15;
    clip-path: polygon(15% 0%, 100% 0%, 100% 100%, 0% 100%);
  "></div>

  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 03 — `hook.html`

**Purpose:** Grab attention. Dramatic, full-bleed, huge statement text.
**Bloom:** Understand / Analyze
**Coordinate map targets:** `#hook-text`, `#source`, `#prompt`

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│         [RIGHT HALF: IMAGE]         │  [LEFT HALF: DARK BG]     │
│                                     │                            │
│                                     │  hook_text (44px bold)    │
│                                     │                            │
│                                     │  ── source citation ──    │
│                                     │                            │
│                                     │  💬 prompt_text           │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- hook.html -->
<div class="slide" id="slide-hook" style="background: var(--c-text-dark);">
  <!-- Right: image -->
  <div style="
    position: absolute; right: 0; top: 0;
    width: 50%; height: 100%;
    background: url({{image_url}}) center/cover no-repeat;
    opacity: 0.6;
  "></div>
  <div style="
    position: absolute; right: 0; top: 0;
    width: 50%; height: 100%;
    background: linear-gradient(to right, var(--c-text-dark) 0%, transparent 60%);
  "></div>

  <!-- Left: content -->
  <div style="
    position: absolute; left: 72px; top: 50%; transform: translateY(-50%);
    width: 580px;
  ">
    <!-- Hook type badge -->
    <div style="
      display: inline-block; padding: 6px 16px; border-radius: 20px;
      background: var(--c-accent); color: var(--c-text-dark);
      font-family: var(--f-heading); font-size: 14px; font-weight: 700;
      letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 32px;
    ">{{hook_type}}</div>

    <blockquote id="hook-text" style="
      font-family: var(--f-heading); font-size: 44px; font-weight: 800;
      color: var(--c-text-light); line-height: 1.2; margin-bottom: 28px;
    ">"{{hook_text}}"</blockquote>

    {{#if source}}
    <p id="source" class="t-caption" style="color: rgba(255,255,255,0.45); margin-bottom: 40px;">
      — {{source}}
    </p>
    {{/if}}

    <!-- Prompt box -->
    <div style="
      border-left: 4px solid var(--c-accent);
      padding: 16px 24px;
      background: rgba(255,255,255,0.06);
      border-radius: 0 8px 8px 0;
    ">
      <p id="prompt" class="t-small" style="color: rgba(255,255,255,0.8);">
        💬 {{prompt_text}}
      </p>
    </div>
  </div>
</div>
```

---

## Template 04 — `content_single.html`

**Purpose:** Teach one concept. Max 4 bullets. Optional callout box and image.
**Bloom:** Remember / Understand / Apply
**Coordinate map targets:** `#headline`, `.bullet-item` (array), `#callout`

```
┌─────────────────────────────────────────────────────────────────┐
│  [TOPIC TAG]                                                     │
│  HEADLINE (52px)                       [RIGHT: IMAGE]           │
│  subheadline (22px, muted)                                      │
│                                                                  │
│  ● Bullet text (22px)                                           │
│    └ sub-bullet (18px, indented)                                │
│  ● Bullet text                                                   │
│  ● EMPHASIZED bullet (accent color bg)                          │
│                                                                  │
│  ┌────────────────────────────────────┐                         │
│  │  KEY TERM  Definition text here   │                         │
│  └────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

```html
<!-- content_single.html -->
<div class="slide" id="slide-content-single">
  <!-- Top accent bar -->
  <div style="position:absolute; top:0; left:0; right:0; height:6px; background: var(--c-primary);"></div>

  <!-- Image (right half, behind content with gradient mask) -->
  {{#if image}}
  <div style="
    position: absolute; right: 0; top: 0;
    width: 480px; height: 100%;
    background: url({{image.url}}) center/cover no-repeat;
  "></div>
  <div style="
    position: absolute; right: 0; top: 0;
    width: 480px; height: 100%;
    background: linear-gradient(to right, var(--c-bg) 20%, transparent 80%);
  "></div>
  {{/if}}

  <!-- Content -->
  <div class="col-left" style="top: 60px;">
    <p class="slide-tag" style="position:static; margin-bottom: 16px;">{{curriculum_tag}}</p>
    <h1 id="headline" class="t-h1" style="margin-bottom: 12px;">{{headline}}</h1>
    <p class="t-body" style="color: rgba(26,26,46,0.5); margin-bottom: 40px;">{{subheadline}}</p>

    <!-- Bullets -->
    <div style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 32px;">
      {{#each bullets}}
      <div class="bullet-item" style="
        padding: 14px 20px;
        border-radius: 8px;
        background: {{#if emphasis}}rgba(26,111,168,0.08){{else}}transparent{{/if}};
        border-left: 4px solid {{#if emphasis}}var(--c-accent){{else}}var(--c-primary){{/if}};
      ">
        <p class="t-body" style="
          color: {{#if emphasis}}var(--c-primary){{else}}var(--c-text-dark){{/if}};
          font-weight: {{#if emphasis}}600{{else}}400{{/if}};
        ">{{text}}</p>
        {{#each sub_bullets}}
        <p class="t-small" style="margin-top: 6px; padding-left: 16px; color: rgba(26,26,46,0.6);">
          → {{this}}
        </p>
        {{/each}}
      </div>
      {{/each}}
    </div>

    <!-- Callout box -->
    {{#if callout}}
    <div id="callout" style="
      display: flex; gap: 16px; align-items: center;
      background: var(--c-primary); color: var(--c-text-light);
      padding: 16px 24px; border-radius: 10px;
    ">
      <span style="font-family: var(--f-heading); font-size: 13px; font-weight: 700; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.1em; white-space: nowrap;">{{callout.label}}</span>
      <div style="width: 1px; height: 32px; background: rgba(255,255,255,0.3);"></div>
      <p class="t-small">{{callout.content}}</p>
    </div>
    {{/if}}
  </div>

  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 05 — `content_three_col.html`

**Purpose:** Three parallel concepts side by side (e.g., Inputs / Process / Outputs).
**Bloom:** Understand / Analyze
**Coordinate map targets:** `#headline`, `.col-card` (array of 3)

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADLINE (52px, centered)                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │    ICON     │  │    ICON     │  │    ICON     │            │
│  │   TITLE     │  │   TITLE     │  │   TITLE     │            │
│  │ ─────────── │  │ ─────────── │  │ ─────────── │            │
│  │ • point     │  │ • point     │  │ • point     │            │
│  │ • point     │  │ • point     │  │ • point     │            │
│  │ • point     │  │ • point     │  │ • point     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

```html
<!-- content_three_col.html -->
<div class="slide" id="slide-three-col">
  <!-- Header band -->
  <div style="background: var(--c-primary); padding: 36px 72px 32px;">
    <h1 id="headline" class="t-h2" style="color: var(--c-text-light); text-align: center;">
      {{headline}}
    </h1>
  </div>

  <!-- Three columns -->
  <div style="
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 24px; padding: 40px 64px; height: calc(100% - 120px);
  ">
    {{#each columns}}
    <div class="col-card" style="
      background: var(--c-surface);
      border-radius: 12px;
      padding: 32px 28px;
      box-shadow: 0 2px 16px rgba(0,0,0,0.06);
      display: flex; flex-direction: column;
      border-top: 5px solid {{color}};
    ">
      <div style="font-size: 42px; margin-bottom: 16px;">{{icon}}</div>
      <h3 class="t-h3" style="margin-bottom: 16px; color: {{color}};">{{title}}</h3>
      <div style="width: 40px; height: 3px; background: {{color}}; margin-bottom: 20px; border-radius: 2px; opacity: 0.4;"></div>
      <ul style="list-style: none; display: flex; flex-direction: column; gap: 10px;">
        {{#each points}}
        <li style="display: flex; gap: 10px; align-items: flex-start;">
          <span style="color: {{../color}}; font-weight: 700; margin-top: 2px;">›</span>
          <span class="t-small">{{this}}</span>
        </li>
        {{/each}}
      </ul>
    </div>
    {{/each}}
  </div>

  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 06 — `visual_diagram.html`

**Purpose:** Data visualization or labeled diagram. Chart.js renders real charts.
**Bloom:** Analyze / Evaluate
**Coordinate map targets:** `#headline`, `#chart-canvas` OR `#labeled-image`

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADLINE                    [SLIDE TAG]                        │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │    [CHART.JS CANVAS  or  LABELED DIAGRAM IMAGE]           │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  CAPTION TEXT (centered, muted)                                  │
└─────────────────────────────────────────────────────────────────┘
```

```html
<!-- visual_diagram.html -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<div class="slide" id="slide-diagram" style="padding: 56px 72px;">
  <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 32px;">
    <h1 id="headline" class="t-h2">{{headline}}</h1>
    <p class="slide-tag" style="position: static;">{{subject}}</p>
  </div>

  {{#if chart}}
  <div style="
    background: var(--c-surface); border-radius: 12px;
    padding: 24px; height: 480px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  ">
    <canvas id="chart-canvas"></canvas>
  </div>
  <script>
    new Chart(document.getElementById('chart-canvas'), {
      type: '{{chart.chart_type}}',
      data: {
        labels: {{chart.labels_json}},
        datasets: {{chart.datasets_json}}
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          x: { title: { display: true, text: '{{chart.x_axis_label}}' } },
          y: { title: { display: true, text: '{{chart.y_axis_label}}' } }
        }
      }
    });
  </script>
  {{/if}}

  {{#if labeled_image}}
  <div id="labeled-image" style="position: relative; height: 520px;">
    <img src="{{labeled_image.image.url}}" style="width:100%; height:100%; object-fit:contain;" />
    {{#each labeled_image.labels}}
    <div style="
      position: absolute;
      left: {{position_x_pct}}%; top: {{position_y_pct}}%;
      transform: translate(-50%, -50%);
      background: var(--c-primary); color: var(--c-text-light);
      padding: 6px 14px; border-radius: 20px;
      font-size: 16px; font-weight: 600; white-space: nowrap;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    ">{{text}}</div>
    {{/each}}
  </div>
  {{/if}}

  <p style="text-align: center; margin-top: 16px;" class="t-caption">{{caption}}</p>
  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 07 — `timeline.html`

**Purpose:** Chronological events, process stages, or historical sequence.
**Bloom:** Remember / Understand
**Coordinate map targets:** `#headline`, `.tl-event` (array)

```
┌──────────────────────────────────────────────────────────────────┐
│  HEADLINE                                                        │
│                                                                  │
│  [LABEL]────●────────────────────●────────────────●─────       │
│   title    ╰─ description    title              title           │
│   desc                        desc               desc           │
│                     [HIGHLIGHTED EVENT: accent color dot]       │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- timeline.html -->
<div class="slide" id="slide-timeline" style="padding: 56px 72px;">
  <h1 id="headline" class="t-h1" style="margin-bottom: 72px;">{{headline}}</h1>

  <!-- Horizontal timeline -->
  <div style="position: relative;">
    <!-- Spine line -->
    <div style="
      position: absolute; top: 20px; left: 0; right: 0;
      height: 3px; background: linear-gradient(to right, var(--c-primary), var(--c-secondary));
      border-radius: 2px;
    "></div>

    <!-- Events -->
    <div style="display: flex; justify-content: space-between; position: relative;">
      {{#each events}}
      <div class="tl-event" style="
        display: flex; flex-direction: column; align-items: center;
        width: {{event_width_px}}px;
      ">
        <!-- Dot -->
        <div style="
          width: {{#if highlight}}28{{else}}18{{/if}}px;
          height: {{#if highlight}}28{{else}}18{{/if}}px;
          border-radius: 50%;
          background: {{#if highlight}}var(--c-accent){{else}}var(--c-primary){{/if}};
          border: 4px solid var(--c-bg);
          box-shadow: 0 0 0 2px {{#if highlight}}var(--c-accent){{else}}var(--c-primary){{/if}};
          margin-bottom: 24px;
          z-index: 1;
        "></div>

        <!-- Label (year/step) -->
        <p style="
          font-family: var(--f-heading); font-size: 18px; font-weight: 700;
          color: {{#if highlight}}var(--c-accent){{else}}var(--c-primary){{/if}};
          margin-bottom: 8px; text-align: center;
        ">{{label}}</p>

        <p class="t-small" style="font-weight: 600; text-align: center; margin-bottom: 8px;">{{title}}</p>
        <p class="t-caption" style="text-align: center; color: rgba(26,26,46,0.55);">{{description}}</p>
      </div>
      {{/each}}
    </div>
  </div>

  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 08 — `comparison_table.html`

**Purpose:** Side-by-side comparison of 2–3 items across multiple criteria.
**Bloom:** Analyze / Evaluate
**Coordinate map targets:** `#headline`, `.compare-col` (array), `.criteria-row` (array)

```
┌──────────────────────────────────────────────────────────────────┐
│  HEADLINE                                                        │
│  ┌──────────────┬────────────────┬─────────────────┐           │
│  │  [CRITERIA]  │   ITEM A       │  ★ ITEM B       │           │
│  │              │                │  (highlighted)  │           │
│  ├──────────────┼────────────────┼─────────────────┤           │
│  │  Criterion 1 │  value         │  value          │           │
│  │  Criterion 2 │  value         │  value          │           │
│  │  Criterion 3 │  value         │  value          │           │
│  └──────────────┴────────────────┴─────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- comparison_table.html -->
<div class="slide" id="slide-comparison" style="padding: 56px 72px;">
  <h1 id="headline" class="t-h2" style="margin-bottom: 40px;">{{headline}}</h1>

  <table style="width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.06);">
    <!-- Header row -->
    <thead>
      <tr>
        <th style="background: var(--c-text-dark); padding: 20px 28px; text-align: left; color: rgba(255,255,255,0.5); font-size: 15px; font-weight: 500; width: 220px;">
          Criteria
        </th>
        {{#each items}}
        <th style="
          background: {{#if highlight}}var(--c-primary){{else}}var(--c-text-dark){{/if}};
          padding: 20px 28px; text-align: center;
          font-family: var(--f-heading); font-size: 22px; font-weight: 700;
          color: var(--c-text-light); border-left: 2px solid rgba(255,255,255,0.08);
        ">
          {{#if highlight}}<span style="font-size: 14px; background: var(--c-accent); color: #1A1A2E; padding: 2px 10px; border-radius: 12px; margin-right: 8px;">★ Best</span>{{/if}}
          {{name}}
        </th>
        {{/each}}
      </tr>
    </thead>
    <!-- Data rows -->
    <tbody>
      {{#each criteria}}
      <tr class="criteria-row">
        <td style="padding: 18px 28px; font-size: 18px; font-weight: 600; background: var(--c-surface); border-bottom: 1px solid rgba(0,0,0,0.06);">
          {{label}}
        </td>
        {{#each values}}
        <td style="
          padding: 18px 28px; text-align: center; font-size: 18px;
          background: var(--c-surface); border-bottom: 1px solid rgba(0,0,0,0.06);
          border-left: 2px solid rgba(0,0,0,0.04);
        ">{{this}}</td>
        {{/each}}
      </tr>
      {{/each}}
    </tbody>
  </table>

  <img class="logo" src="{{logo_url}}" />
  <span class="page-num">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 09 — `real_world_example.html`

**Purpose:** Bridge abstract concept to student's daily life. Story-driven.
**Bloom:** Apply / Understand
**Coordinate map targets:** `#headline`, `#example-text`, `#follow-up`

```
┌──────────────────────────────────────────────────────────────────┐
│                         │                                        │
│   [LEFT: FULL IMAGE]    │  "You See This Every Day"             │
│                         │                                        │
│                         │  connection_text (28px, accent)       │
│                         │                                        │
│                         │  example_text (22px)                  │
│                         │                                        │
│                         │  ┌──────────────────────────┐         │
│                         │  │ 🤔 follow_up question    │         │
│                         │  └──────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- real_world_example.html -->
<div class="slide" id="slide-example" style="display: flex;">
  <!-- Left: image -->
  <div style="
    width: 480px; flex-shrink: 0;
    background: url({{image.url}}) center/cover no-repeat;
    position: relative;
  ">
    <div style="
      position: absolute; inset: 0;
      background: linear-gradient(to right, transparent 60%, var(--c-bg) 100%);
    "></div>
  </div>

  <!-- Right: content -->
  <div style="flex: 1; padding: 64px 72px 64px 48px; display: flex; flex-direction: column; justify-content: center;">
    <p class="slide-tag" style="position: static; margin-bottom: 16px;">Real World Connection</p>
    <h1 id="headline" class="t-h2" style="margin-bottom: 20px;">{{headline}}</h1>

    <p style="
      font-family: var(--f-heading); font-size: 26px; font-weight: 700;
      color: var(--c-accent); margin-bottom: 28px;
    ">{{connection_text}}</p>

    <p id="example-text" class="t-body" style="
      color: rgba(26,26,46,0.75); line-height: 1.6; margin-bottom: 36px;
    ">{{example_text}}</p>

    <!-- Follow-up question box -->
    <div id="follow-up" style="
      background: var(--c-primary); color: var(--c-text-light);
      padding: 20px 28px; border-radius: 10px;
      display: flex; gap: 16px; align-items: flex-start;
    ">
      <span style="font-size: 28px;">🤔</span>
      <p class="t-body">{{follow_up}}</p>
    </div>
  </div>
</div>
```

---

## Template 10 — `activity.html`

**Purpose:** Student engagement slide. Timer, instructions, materials list.
**Bloom:** Apply / Create
**Coordinate map targets:** `#headline`, `#activity-type-badge`, `.instruction-step` (array)

```
┌──────────────────────────────────────────────────────────────────┐
│  [ACTIVITY BADGE]  HEADLINE                    [⏱ TIMER]       │
│  ──────────────────────────────────────────────────────          │
│                                                                  │
│  STEP 1  ──────────────────────────────────────────────         │
│  STEP 2  ──────────────────────────────────────────────         │
│  STEP 3  ──────────────────────────────────────────────         │
│                                                                  │
│  📎 Materials: item, item, item                                 │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- activity.html -->
<div class="slide" id="slide-activity" style="padding: 56px 72px; background: var(--c-text-dark);">
  <!-- Header -->
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px;">
    <div style="display: flex; align-items: center; gap: 20px;">
      <div id="activity-type-badge" style="
        background: var(--c-accent); color: var(--c-text-dark);
        padding: 8px 20px; border-radius: 24px;
        font-family: var(--f-heading); font-size: 15px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em;
      ">{{activity_type}}</div>
      <h1 id="headline" class="t-h2" style="color: var(--c-text-light);">{{headline}}</h1>
    </div>
    <!-- Timer -->
    <div style="text-align: center;">
      <div style="font-size: 56px; font-family: var(--f-heading); font-weight: 800; color: var(--c-accent); line-height: 1;">
        {{duration_min}}
      </div>
      <p style="font-size: 14px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.1em;">mins</p>
    </div>
  </div>

  <div style="width: 100%; height: 2px; background: rgba(255,255,255,0.1); margin-bottom: 40px;"></div>

  <!-- Instructions -->
  <div style="display: flex; flex-direction: column; gap: 20px; margin-bottom: 40px;">
    {{#each instructions}}
    <div class="instruction-step" style="display: flex; gap: 24px; align-items: flex-start;">
      <div style="
        min-width: 40px; height: 40px; border-radius: 50%;
        background: var(--c-primary);
        display: flex; align-items: center; justify-content: center;
        font-family: var(--f-heading); font-size: 18px; font-weight: 800;
        color: var(--c-text-light);
      ">{{@index+1}}</div>
      <p class="t-body" style="color: rgba(255,255,255,0.85); padding-top: 6px;">{{this}}</p>
    </div>
    {{/each}}
  </div>

  <!-- Materials -->
  {{#if materials}}
  <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
    <span style="font-size: 20px;">📎</span>
    <span class="t-small" style="color: rgba(255,255,255,0.5); font-weight: 600;">You will need:</span>
    {{#each materials}}
    <span style="
      padding: 4px 14px; border-radius: 16px;
      background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7);
      font-size: 16px;
    ">{{this}}</span>
    {{/each}}
  </div>
  {{/if}}

  <img class="logo" src="{{logo_url}}" style="filter: brightness(0) invert(1); opacity: 0.4;" />
  <span class="page-num" style="color: rgba(255,255,255,0.25);">{{slide_number}} / {{total}}</span>
</div>
```

---

## Template 11 — `quiz_mcq.html`

**Purpose:** MCQ questions with click-to-reveal answers.
**Bloom:** Remember / Understand / Apply
**Coordinate map targets:** `#headline`, `.question-block` (array), `.option-btn` (array per question)

```
┌──────────────────────────────────────────────────────────────────┐
│  ❓ HEADLINE                                                     │
│  ──────────────────────────────────────────────────              │
│  Q1: Question text                                               │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │  A) Option  │  │  B) Option  │  (correct = green on reveal) │
│  └─────────────┘  └─────────────┘                               │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │  C) Option  │  │  D) Option  │                               │
│  └─────────────┘  └─────────────┘                               │
│  [Explanation — shown on reveal]                                 │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- quiz_mcq.html -->
<div class="slide" id="slide-quiz" style="padding: 48px 72px; overflow: hidden;">
  <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 8px;">
    <span style="font-size: 40px;">❓</span>
    <h1 id="headline" class="t-h2">{{headline}}</h1>
  </div>
  <div style="width: 100%; height: 2px; background: var(--c-primary); opacity: 0.15; margin-bottom: 36px;"></div>

  <!-- Questions (render one per slide OR stacked depending on count) -->
  {{#each questions}}
  <div class="question-block" style="margin-bottom: 32px;" data-correct="{{correct_index}}">
    <p class="t-body" style="font-weight: 600; margin-bottom: 20px;">
      <span style="color: var(--c-primary);">Q{{@index+1}}.</span> {{question_text}}
    </p>

    <!-- Options grid -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
      {{#each options}}
      <button class="option-btn" data-index="{{@index}}" style="
        padding: 16px 20px; border-radius: 8px; text-align: left;
        font-size: 18px; font-family: var(--f-body); cursor: pointer;
        border: 2px solid rgba(26,111,168,0.2);
        background: var(--c-surface); color: var(--c-text-dark);
        transition: all 0.2s; display: flex; gap: 12px; align-items: center;
      ">
        <span style="
          font-family: var(--f-heading); font-weight: 700;
          color: var(--c-primary); font-size: 16px;
        ">{{option_letter}})</span>
        {{this}}
      </button>
      {{/each}}
    </div>

    <!-- Explanation (hidden until reveal) -->
    <div class="explanation" style="
      display: none; padding: 14px 20px; border-radius: 8px;
      background: rgba(13,158,117,0.1); border-left: 4px solid var(--c-secondary);
    ">
      <p class="t-small" style="color: var(--c-secondary);">✅ {{explanation}}</p>
    </div>
  </div>
  {{/each}}
</div>
<script>
  document.querySelectorAll('.option-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const block = this.closest('.question-block');
      const correct = parseInt(block.dataset.correct);
      const idx = parseInt(this.dataset.index);
      block.querySelectorAll('.option-btn').forEach((b, i) => {
        b.style.pointerEvents = 'none';
        if (i === correct) { b.style.background = '#E1F5EE'; b.style.borderColor = '#0D9E75'; }
        else if (i === idx && i !== correct) { b.style.background = '#FAECE7'; b.style.borderColor = '#D85A30'; }
      });
      block.querySelector('.explanation').style.display = 'block';
    });
  });
</script>
```

---

## Template 12 — `summary.html`

**Purpose:** Close the lesson. Key takeaways + next class preview + homework.
**Bloom:** Remember / Evaluate
**Coordinate map targets:** `#headline`, `.takeaway-item` (array), `#closing-q`

```
┌──────────────────────────────────────────────────────────────────┐
│  [PRIMARY COLOR TOP BAND with HEADLINE]                          │
│                                                                  │
│   1  Takeaway one (large numbered list)                         │
│   2  Takeaway two                                               │
│   3  Takeaway three                                             │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │  💭 Closing Q       │  │  📖 Next: ...  📝 Homework: ..  │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

```html
<!-- summary.html -->
<div class="slide" id="slide-summary">
  <!-- Top band -->
  <div style="background: var(--c-primary); padding: 36px 72px; display: flex; justify-content: space-between; align-items: center;">
    <h1 id="headline" class="t-h2" style="color: var(--c-text-light);">{{headline}}</h1>
    <div style="font-size: 42px;">🎯</div>
  </div>

  <!-- Takeaways -->
  <div style="padding: 36px 72px; display: flex; flex-direction: column; gap: 16px;">
    {{#each takeaways}}
    <div class="takeaway-item" style="display: flex; align-items: center; gap: 24px;">
      <div style="
        font-family: var(--f-heading); font-size: 52px; font-weight: 900;
        color: var(--c-primary); opacity: 0.12; line-height: 1; min-width: 48px;
      ">{{number}}</div>
      <p class="t-body" style="font-weight: 500; border-left: 3px solid var(--c-secondary); padding-left: 20px;">{{text}}</p>
    </div>
    {{/each}}
  </div>

  <!-- Bottom row -->
  <div style="
    position: absolute; bottom: 0; left: 0; right: 0;
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0; border-top: 1px solid rgba(0,0,0,0.08);
  ">
    <div id="closing-q" style="padding: 20px 36px; background: rgba(244,166,35,0.08); border-right: 1px solid rgba(0,0,0,0.08);">
      <p class="t-small"><span style="font-weight: 700; color: var(--c-accent);">💭 Think about:</span> {{closing_question}}</p>
    </div>
    <div style="padding: 20px 36px; display: flex; flex-direction: column; gap: 8px;">
      {{#if next_lesson}}<p class="t-small"><span style="font-weight: 700; color: var(--c-primary);">📖 Next:</span> {{next_lesson}}</p>{{/if}}
      {{#if homework}}<p class="t-small"><span style="font-weight: 700; color: var(--c-secondary);">📝 HW:</span> {{homework}}</p>{{/if}}
    </div>
  </div>

  <img class="logo" src="{{logo_url}}" />
</div>
```

---

## Rendering Checklist for Phase 2

```javascript
// playwright_renderer.js — coordinate capture per template

const coordinateMap = {
  slide_number: contract.slide_number,
  template_type: contract.template_type,
  canvas: { width: 1280, height: 720 },
  device_scale_factor: 2,                    // CRITICAL for EMU math
  elements: []
};

// Scrape every target element
for (const selector of TEMPLATE_TARGETS[template_type]) {
  const el = await page.$(selector);
  if (!el) continue;
  const box = await el.boundingBox();
  const styles = await el.evaluate(el => {
    const s = getComputedStyle(el);
    return {
      font_family:  s.fontFamily,
      font_size:    parseFloat(s.fontSize),
      font_weight:  s.fontWeight,
      color:        s.color,
      bg_color:     s.backgroundColor,
      text_align:   s.textAlign,
      line_height:  parseFloat(s.lineHeight),
    };
  });
  coordinateMap.elements.push({
    id: selector,
    x: box.x, y: box.y,
    width: box.width, height: box.height,
    text: await el.textContent(),
    ...styles
  });
}
```

---

## Subject → Default Theme Mapping

| Subject         | Theme Name          | Primary    | Secondary  | Accent     |
|-----------------|---------------------|------------|------------|------------|
| Science         | `science_blue`      | `#1A6FA8`  | `#0D9E75`  | `#F4A623`  |
| Mathematics     | `math_purple`       | `#5A3FA8`  | `#8B5CF6`  | `#10B981`  |
| History         | `history_gold`      | `#92400E`  | `#B45309`  | `#1A6FA8`  |
| English         | `english_teal`      | `#0F766E`  | `#0D9E75`  | `#F472B6`  |
| Computer Science| `cs_dark`           | `#1E293B`  | `#3B82F6`  | `#22D3EE`  |
| Geography       | `geo_green`         | `#166534`  | `#15803D`  | `#F59E0B`  |
| Social Studies  | `social_orange`     | `#C2410C`  | `#EA580C`  | `#0F766E`  |
