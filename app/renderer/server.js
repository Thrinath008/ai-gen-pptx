/**
 * Enterprise Presentation Pipeline — Phase 2: Headless DOM Calculator
 * Node.js / Express / Playwright coordinate-scraping microservice.
 *
 * POST /calculate-layout
 *   Body: PresentationContract JSON (from Phase 1)
 *   Returns: absolute_coordinate_map JSON
 *
 * Install deps:
 *   npm install express playwright @playwright/browser-chromium zod winston
 *   npx playwright install chromium
 */

'use strict';

const express    = require('express');
const { chromium } = require('playwright');
const { z }      = require('zod');
const winston    = require('winston');
const path       = require('path');
const fs         = require('fs');

// ─── Logger ───────────────────────────────────────────────────────────────────
const log = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.colorize(),
    winston.format.printf(({ timestamp, level, message }) =>
      `${timestamp} [${level}] ${message}`)
  ),
  transports: [new winston.transports.Console()],
});

// ─── Configuration ────────────────────────────────────────────────────────────
const PORT              = process.env.PORT            || 3100;
const SLIDE_WIDTH_PX    = 1280;   // 16:9 canvas width  (maps to 12192000 EMU at 96dpi)
const SLIDE_HEIGHT_PX   = 720;    // 16:9 canvas height (maps to 6858000  EMU at 96dpi)
const BROWSER_TIMEOUT   = 30_000; // ms
const TEMPLATE_HTML_DIR = path.join(__dirname, '..', '..', 'templates');

// ─── Zod Input Validation ─────────────────────────────────────────────────────
const SlideSchema = z.object({
  slide_id:     z.string().uuid(),
  template_key: z.string(),
  content:      z.record(z.unknown()),
  visuals:      z.record(z.unknown()).optional(),
  transition:   z.string().optional(),
});

const ContractSchema = z.object({
  metadata:      z.object({ title: z.string(), aspect_ratio: z.string() }),
  global_styles: z.record(z.unknown()).optional(),
  slides:        z.array(SlideSchema).min(1),
});

// ─── Express App ─────────────────────────────────────────────────────────────
const app = express();
app.use(express.json({ limit: '10mb' }));

// ─── Health check ─────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

// ─── Main endpoint ────────────────────────────────────────────────────────────
app.post('/calculate-layout', async (req, res) => {
  // 1. Validate input
  const parsed = ContractSchema.safeParse(req.body);
  if (!parsed.success) {
    log.warn(`Input validation failed: ${JSON.stringify(parsed.error.flatten())}`);
    return res.status(400).json({ error: 'Invalid contract schema', details: parsed.error.flatten() });
  }

  const contract = parsed.data;
  log.info(`Calculating layout for "${contract.metadata.title}" — ${contract.slides.length} slides`);

  let browser = null;
  try {
    browser = await chromium.launch({ headless: true });
    const coordinateMap = await processPresentation(browser, contract);

    log.info(`Layout complete — ${coordinateMap.slides.length} slides processed`);
    return res.json(coordinateMap);

  } catch (err) {
    log.error(`Layout calculation failed: ${err.message}`);
    return res.status(500).json({ error: err.message });

  } finally {
    if (browser) {
      await browser.close().catch(e => log.warn(`Browser close error: ${e.message}`));
    }
  }
});

// ─── Core Processing ─────────────────────────────────────────────────────────

/**
 * Iterates slides and calculates layout for each one.
 * @param {import('playwright').Browser} browser
 * @param {object} contract  Validated PresentationContract
 * @returns {object} coordinate_map
 */
async function processPresentation(browser, contract) {
  const context = await browser.newContext({
    viewport: { width: SLIDE_WIDTH_PX, height: SLIDE_HEIGHT_PX },
    deviceScaleFactor: 1,
  });

  const slideResults = [];

  for (const slide of contract.slides) {
    const result = await processSlide(context, slide, contract.global_styles || {});
    slideResults.push(result);
    log.info(`  Slide ${slide.slide_id.slice(0, 8)}… [${slide.template_key}] — ${result.elements.length} elements`);
  }

  await context.close();

  return {
    presentation_title: contract.metadata.title,
    canvas:             { width_px: SLIDE_WIDTH_PX, height_px: SLIDE_HEIGHT_PX },
    slides:             slideResults,
  };
}

/**
 * Opens a headless page for one slide, injects data, and scrapes coordinates.
 * @param {import('playwright').BrowserContext} context
 * @param {object} slide  Single slide from the contract
 * @param {object} globalStyles
 * @returns {object}
 */
async function processSlide(context, slide, globalStyles) {
  const page = await context.newPage();

  try {
    // Load the HTML template file for this layout
    const templatePath = resolveTemplatePath(slide.template_key);
    await page.goto(`file://${templatePath}`, { waitUntil: 'domcontentloaded', timeout: BROWSER_TIMEOUT });

    // Inject the slide data into the page's window object and trigger render
    await page.evaluate(({ slide, globalStyles, width, height }) => {
      window.__SLIDE_DATA__   = slide;
      window.__GLOBAL_STYLES__ = globalStyles;
      window.__CANVAS_W__     = width;
      window.__CANVAS_H__     = height;

      // Trigger any framework re-render if a global hook is exposed
      if (typeof window.__RENDER_SLIDE__ === 'function') {
        window.__RENDER_SLIDE__(slide, globalStyles);
      }
    }, { slide, globalStyles, width: SLIDE_WIDTH_PX, height: SLIDE_HEIGHT_PX });

    // Wait for layout to settle (fonts, images, flex recalculation)
    await page.waitForFunction(() => document.readyState === 'complete', { timeout: BROWSER_TIMEOUT });
    await page.waitForTimeout(300); // Extra buffer for CSS transitions

    // Scrape all measured elements
    const elements = await scrapeCoordinates(page);

    // Extract computed CSS gradient/shadow data from slide background
    const backgroundData = await extractBackgroundStyles(page);

    return {
      slide_id:        slide.slide_id,
      template_key:    slide.template_key,
      elements,
      background:      backgroundData,
      transition:      slide.transition || 'morph',
      morph_id:        slide.visuals?.morph_id || null,
    };

  } finally {
    await page.close();
  }
}

// ─── DOM Scraper ─────────────────────────────────────────────────────────────

/**
 * The core coordinate scraper.
 * Executed inside the headless browser context via page.evaluate().
 * Traverses every [data-pptx-role] element, capturing exact layout metrics.
 * @param {import('playwright').Page} page
 * @returns {Promise<Array>} elements
 */
async function scrapeCoordinates(page) {
  return await page.evaluate(() => {
    const CANVAS_W = window.__CANVAS_W__ || 1280;
    const CANVAS_H = window.__CANVAS_H__ || 720;
    const PX_TO_EMU = 9525; // 1 CSS pixel = 9525 EMU at 96 DPI

    const root    = document.getElementById('slide-root') || document.body;
    const rootBox = root.getBoundingClientRect();

    // Helper: resolve coordinate relative to slide root
    function toSlideCoords(rect) {
      return {
        x:      rect.left   - rootBox.left,
        y:      rect.top    - rootBox.top,
        width:  rect.width,
        height: rect.height,
      };
    }

    // Helper: convert px coords to EMU
    function toEmu(px) {
      return Math.round(px * PX_TO_EMU);
    }

    // Parse CSS box-shadow to PowerPoint polar shadow parameters
    function parseShadow(shadowStr) {
      if (!shadowStr || shadowStr === 'none') return null;
      // Format: "Xpx Ypx Blur Spread Color"
      const match = shadowStr.match(/([-\d.]+)px\s+([-\d.]+)px\s+([\d.]+)px/);
      if (!match) return null;
      const dx    = parseFloat(match[1]);
      const dy    = parseFloat(match[2]);
      const blur  = parseFloat(match[3]);
      // Convert Cartesian to PowerPoint polar coordinates
      const distance = Math.round(Math.sqrt(dx * dx + dy * dy));
      const angleRad = Math.atan2(dy, dx);
      const angleDeg = Math.round(((angleRad * 180) / Math.PI + 360) % 360);
      return { angle_deg: angleDeg, distance_pt: Math.round(distance * 0.75), blur_pt: Math.round(blur * 0.75) };
    }

    // Parse CSS linear-gradient to OOXML gradient stops
    function parseGradient(bgStr) {
      if (!bgStr || !bgStr.includes('gradient')) return null;
      // e.g. "linear-gradient(135deg, #0F2D5E 0%, #1a4a8a 100%)"
      const angleMatch = bgStr.match(/(\d+)deg/);
      const stopMatches = [...bgStr.matchAll(/#([0-9A-Fa-f]{6})\s+([\d.]+)%/g)];
      if (!stopMatches.length) return null;
      return {
        angle: angleMatch ? parseInt(angleMatch[1]) : 0,
        stops: stopMatches.map(m => ({ color: '#' + m[1], position: parseFloat(m[2]) })),
      };
    }

    const elements = [];
    // Select all elements tagged for PPTX extraction
    const nodes = root.querySelectorAll('[data-pptx-role]');

    nodes.forEach((el) => {
      const rect    = el.getBoundingClientRect();
      const coords  = toSlideCoords(rect);
      const style   = window.getComputedStyle(el);
      const role    = el.dataset.pptxRole;

      // Skip zero-size or off-canvas elements
      if (coords.width < 1 || coords.height < 1) return;
      if (coords.x > CANVAS_W || coords.y > CANVAS_H) return;

      const element = {
        role,
        element_id: el.id || el.dataset.elementId || null,

        // Pixel coordinates (relative to slide root)
        px: {
          x:      parseFloat(coords.x.toFixed(3)),
          y:      parseFloat(coords.y.toFixed(3)),
          width:  parseFloat(coords.width.toFixed(3)),
          height: parseFloat(coords.height.toFixed(3)),
        },

        // EMU coordinates (ready for OOXML a:off / a:ext)
        emu: {
          x:      toEmu(coords.x),
          y:      toEmu(coords.y),
          cx:     toEmu(coords.width),
          cy:     toEmu(coords.height),
        },

        // Typography
        typography: null,
        // Visual decorations
        fill:       null,
        border:     null,
        shadow:     null,
        opacity:    parseFloat(style.opacity),
        rotation:   0,
      };

      // ── Typography extraction ───────────────────────────
      if (['text', 'headline', 'subheadline', 'body', 'caption',
           'metric-value', 'metric-label', 'bullet', 'step-label'].includes(role)) {
        const fontSizePx  = parseFloat(style.fontSize);
        const fontSizePt  = parseFloat((fontSizePx * 0.75).toFixed(1)); // px → pt (1pt = 1.333px)

        element.text_content = el.innerText || el.textContent || '';
        element.typography = {
          font_family:  style.fontFamily.replace(/['"]/g, '').split(',')[0].trim(),
          font_size_pt: fontSizePt,
          font_size_px: fontSizePx,
          font_weight:  style.fontWeight,
          font_style:   style.fontStyle,
          color:        style.color,
          text_align:   style.textAlign,
          line_height:  style.lineHeight,
          letter_spacing: style.letterSpacing,
          text_transform: style.textTransform,
        };
      }

      // ── Image placeholder extraction ────────────────────
      if (role === 'image-placeholder' || role === 'chart-placeholder') {
        element.image_src    = el.dataset.imageSrc    || null;
        element.image_prompt = el.dataset.imagePrompt || null;
        element.object_fit   = style.objectFit        || 'cover';
        element.border_radius_px = parseFloat(style.borderRadius) || 0;
      }

      // ── Shape fill ──────────────────────────────────────
      const bgColor = style.backgroundColor;
      const bgImage = style.backgroundImage;

      if (bgImage && bgImage !== 'none') {
        element.fill = { type: 'gradient', gradient: parseGradient(bgImage) };
      } else if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
        element.fill = { type: 'solid', color: bgColor };
      }

      // ── Border ──────────────────────────────────────────
      const bWidth = parseFloat(style.borderWidth);
      if (bWidth > 0) {
        element.border = {
          width_pt: parseFloat((bWidth * 0.75).toFixed(2)),
          color:    style.borderColor,
          style:    style.borderStyle,
        };
      }

      // ── Shadow ──────────────────────────────────────────
      const shadowData = parseShadow(style.boxShadow);
      if (shadowData) element.shadow = shadowData;

      // ── CSS rotation ────────────────────────────────────
      const transform = style.transform;
      if (transform && transform !== 'none') {
        const rotMatch = transform.match(/rotate\(([-\d.]+)deg\)/);
        if (rotMatch) element.rotation = parseFloat(rotMatch[1]);
      }

      elements.push(element);
    });

    return elements;
  });
}

/**
 * Extracts slide background styles (gradient or solid) from the root element.
 * Handles both #RRGGBB hex and rgb()/rgba() computed color formats.
 */
async function extractBackgroundStyles(page) {
  return await page.evaluate(() => {
    const root  = document.getElementById('slide-root') || document.body;
    const style = window.getComputedStyle(root);
    const bg    = style.backgroundImage;
    const bgCol = style.backgroundColor;

    // Helper: convert any CSS color token to #RRGGBB
    function toHex(colorStr) {
      // Already hex
      if (/^#[0-9A-Fa-f]{6}$/.test(colorStr)) return colorStr.toUpperCase();
      // rgb(r, g, b) or rgba(r, g, b, a)
      const m = colorStr.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/);
      if (m) {
        const hex = [m[1], m[2], m[3]]
          .map(n => Math.round(parseFloat(n)).toString(16).padStart(2, '0'))
          .join('');
        return '#' + hex.toUpperCase();
      }
      return null;
    }

    // Helper: extract all color + position pairs from a gradient string
    // Handles both rgb(r,g,b) 0% and #RRGGBB 0% token formats
    function parseStops(gradientStr) {
      const stops = [];
      // Match rgb/rgba tokens with position
      const rgbRe = /rgba?\([^)]+\)\s+([\d.]+)%/g;
      let m;
      while ((m = rgbRe.exec(gradientStr)) !== null) {
        const colorToken = m[0].replace(/\s+[\d.]+%$/, '').trim();
        const pos        = parseFloat(m[1]);
        const hex        = toHex(colorToken);
        if (hex) stops.push({ color: hex, position: pos });
      }
      // Also match #RRGGBB tokens (fallback for pre-resolved values)
      const hexRe = /#([0-9A-Fa-f]{6})\s+([\d.]+)%/g;
      while ((m = hexRe.exec(gradientStr)) !== null) {
        const hex = '#' + m[1].toUpperCase();
        const pos = parseFloat(m[2]);
        if (!stops.find(s => Math.abs(s.position - pos) < 0.5)) {
          stops.push({ color: hex, position: pos });
        }
      }
      stops.sort((a, b) => a.position - b.position);
      return stops;
    }

    if (bg && bg !== 'none' && bg.includes('gradient')) {
      const angleMatch = bg.match(/(\d+)deg/);
      const stops      = parseStops(bg);

      if (stops.length >= 2) {
        return {
          type:  'gradient',
          angle: angleMatch ? parseInt(angleMatch[1]) : 135,
          stops,
        };
      }
      // Gradient detected but stops not parseable — use the first solid colour
      // derived from the element's background-color as fallback solid
      const solidFallback = toHex(bgCol);
      if (solidFallback && solidFallback !== '#000000') {
        return { type: 'solid', color: solidFallback };
      }
      // Last-resort: read the data-bg attribute templates can set
      const dataBg = root.dataset && root.dataset.bg;
      if (dataBg) return { type: 'solid', color: dataBg };
    }

    const solidColor = toHex(bgCol) || '#FFFFFF';
    return { type: 'solid', color: solidColor };
  });
}


// ─── Template Resolver ────────────────────────────────────────────────────────

/**
 * Maps a template_key to its absolute HTML file path.
 * In production: these are compiled React static exports.
 */
function resolveTemplatePath(templateKey) {
  const templateFile = path.join(TEMPLATE_HTML_DIR, `${templateKey}.html`);
  if (fs.existsSync(templateFile)) return templateFile;

  // Fallback to generic template
  const fallback = path.join(TEMPLATE_HTML_DIR, 'bullet_list.html');
  if (fs.existsSync(fallback)) return fallback;

  throw new Error(`No template found for key: ${templateKey}`);
}

// ─── Start Server ─────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  log.info(`DOM Calculator listening on http://localhost:${PORT}`);
  log.info(`Template directory: ${TEMPLATE_HTML_DIR}`);
  log.info(`Canvas: ${SLIDE_WIDTH_PX}×${SLIDE_HEIGHT_PX}px`);
});

module.exports = app; // for testing
