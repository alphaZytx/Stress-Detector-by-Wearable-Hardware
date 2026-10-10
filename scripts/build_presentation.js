const pptxgen = require('pptxgenjs');
const path = require('path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Stress Wearable Project Team';
pptx.company = 'ECE Department, NIT Patna';
pptx.subject = 'Professor-facing engineering project presentation';
pptx.title = 'Real-Time Stress Detection Using Physiological Signals and Machine Learning';
pptx.lang = 'en-US';
pptx.theme = {
  headFontFace: 'Aptos Display',
  bodyFontFace: 'Aptos',
  lang: 'en-US',
};
pptx.defineLayout({ name: 'CUSTOM_WIDE', width: 13.333, height: 7.5 });
pptx.layout = 'CUSTOM_WIDE';

const S = pptx.ShapeType;
const W = 13.333;
const H = 7.5;

const C = {
  navy: '0B1736',
  navy2: '132650',
  ink: '18213D',
  cream: 'F7F4EE',
  white: 'FFFFFF',
  mist: 'EEF2F7',
  grey: '6E7893',
  grey2: 'A8B0C3',
  teal: '18A999',
  mint: 'DDF4EF',
  sky: '57B8E8',
  skyPale: 'E3F4FC',
  coral: 'F47A64',
  coralPale: 'FCE6E1',
  gold: 'F2C14E',
  goldPale: 'FFF3D2',
  violet: '7267E8',
  violetPale: 'ECEAFF',
  green: '2EA36F',
  red: 'D95062',
  paleLine: 'D8DEEA',
};

const ROOT = path.resolve(__dirname, '..');
const ASSET = (...parts) => path.join(ROOT, ...parts);
const OUT = ASSET('Real-Time-Stress-Detection-Professor-Presentation.pptx');

const img = {
  hero: ASSET('presentation_assets', 'wearable_concept.png'),
  baseline: ASSET('reports', 'screenshots', 'live_baseline.png'),
  stress: ASSET('reports', 'screenshots', 'live_stress_alert.png'),
  session: ASSET('reports', 'screenshots', 'session_detail.png'),
  calibration: ASSET('reports', 'screenshots', 'calibration_capture.png'),
  breathing: ASSET('reports', 'screenshots', 'breathing_active.png'),
};

const shadow = {
  type: 'outer',
  color: '071226',
  opacity: 0.16,
  blur: 3,
  angle: 45,
  distance: 2,
};

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: opts.fontFace || 'Aptos',
    fontSize: opts.fontSize || 14,
    bold: opts.bold || false,
    color: opts.color || C.ink,
    align: opts.align || 'left',
    valign: opts.valign || 'mid',
    margin: opts.margin === undefined ? 0 : opts.margin,
    breakLine: false,
    fit: 'shrink',
    paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
    bullet: opts.bullet,
    isTextBox: true,
    ...opts,
  });
}

function addRichText(slide, runs, x, y, w, h, opts = {}) {
  slide.addText(runs, {
    x, y, w, h,
    fontFace: opts.fontFace || 'Aptos',
    fontSize: opts.fontSize || 14,
    color: opts.color || C.ink,
    margin: opts.margin === undefined ? 0 : opts.margin,
    valign: opts.valign || 'mid',
    fit: 'shrink',
    ...opts,
  });
}

function roundedCard(slide, x, y, w, h, fill, opts = {}) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: opts.radius || 0.12,
    fill: { color: fill, transparency: opts.transparency || 0 },
    line: { color: opts.lineColor || fill, transparency: opts.lineTransparency === undefined ? 100 : opts.lineTransparency, width: opts.lineWidth || 1 },
    shadow: opts.shadow === false ? undefined : shadow,
  });
}

function pill(slide, text, x, y, w, fill, color = C.ink, opts = {}) {
  slide.addShape(S.roundRect, {
    x, y, w, h: opts.h || 0.38,
    rectRadius: 0.18,
    fill: { color: fill },
    line: { color: opts.lineColor || fill, transparency: opts.lineColor ? 0 : 100 },
  });
  addText(slide, text, x + 0.1, y, w - 0.2, opts.h || 0.38, {
    fontSize: opts.fontSize || 10.5,
    bold: opts.bold === undefined ? true : opts.bold,
    color,
    align: 'center',
    charSpacing: opts.charSpacing || 0.2,
  });
}

function addLine(slide, x, y, w, h, color = C.paleLine, width = 2, arrow = false) {
  slide.addShape(S.line, {
    x, y, w, h,
    line: {
      color,
      width,
      beginArrowType: 'none',
      endArrowType: arrow ? 'triangle' : 'none',
    },
  });
}

function cropTo(pathName, imgW, imgH, x, y, w, h) {
  const target = w / h;
  const source = imgW / imgH;
  let sx = 0;
  let sy = 0;
  let sw = imgW;
  let sh = imgH;
  if (source > target) {
    sw = imgH * target;
    sx = (imgW - sw) / 2;
  } else {
    sh = imgW / target;
    sy = (imgH - sh) / 2;
  }
  return { path: pathName, x, y, w, h, sizing: 'crop', crop: { x: sx, y: sy, w: sw, h: sh } };
}

function contain(pathName, imgW, imgH, x, y, w, h) {
  const scale = Math.min(w / imgW, h / imgH);
  const nw = imgW * scale;
  const nh = imgH * scale;
  return { path: pathName, x: x + (w - nw) / 2, y: y + (h - nh) / 2, w: nw, h: nh };
}

function addPageNumber(slide, n, dark = false) {
  addText(slide, String(n).padStart(2, '0'), 12.27, 7.02, 0.55, 0.22, {
    fontSize: 9,
    bold: true,
    color: dark ? 'B8C5DF' : C.grey,
    align: 'right',
    charSpacing: 1.5,
  });
}

function addLightBackdrop(slide, accent = C.teal) {
  slide.background = { color: C.cream };
  slide.addShape(S.ellipse, {
    x: 10.5, y: -1.25, w: 4.3, h: 4.3,
    fill: { color: accent, transparency: 88 },
    line: { transparency: 100 },
  });
  slide.addShape(S.ellipse, {
    x: -1.25, y: 5.85, w: 3.0, h: 3.0,
    fill: { color: C.coral, transparency: 91 },
    line: { transparency: 100 },
  });
}

function addDarkBackdrop(slide) {
  slide.background = { color: C.navy };
  slide.addShape(S.ellipse, {
    x: 9.75, y: -1.7, w: 5.3, h: 5.3,
    fill: { color: C.teal, transparency: 82 },
    line: { transparency: 100 },
  });
  slide.addShape(S.ellipse, {
    x: -1.3, y: 5.55, w: 3.2, h: 3.2,
    fill: { color: C.coral, transparency: 84 },
    line: { transparency: 100 },
  });
}

function addHeader(slide, n, kicker, title, opts = {}) {
  const dark = !!opts.dark;
  const titleColor = dark ? C.white : C.navy;
  const kickerColor = opts.accent || C.teal;
  addText(slide, kicker.toUpperCase(), 0.68, 0.34, 5.7, 0.24, {
    fontSize: 9.5,
    bold: true,
    color: kickerColor,
    charSpacing: 2.0,
  });
  addText(slide, title, 0.68, 0.66, 11.7, 0.58, {
    fontFace: 'Aptos Display',
    fontSize: opts.fontSize || 25,
    bold: true,
    color: titleColor,
  });
  slide.addShape(S.line, {
    x: 0.68, y: 1.28, w: 11.96, h: 0,
    line: { color: dark ? '3B4D70' : C.paleLine, width: 1.1 },
  });
  addPageNumber(slide, n, dark);
}

function metricCard(slide, x, y, w, h, value, label, accent, opts = {}) {
  roundedCard(slide, x, y, w, h, opts.fill || C.white, { lineColor: opts.lineColor || C.paleLine, lineTransparency: 0, shadow: true });
  slide.addShape(S.rect, {
    x, y, w: 0.08, h,
    fill: { color: accent },
    line: { transparency: 100 },
  });
  addText(slide, value, x + 0.28, y + 0.14, w - 0.45, h * 0.47, {
    fontFace: 'Aptos Display',
    fontSize: opts.valueSize || 23,
    bold: true,
    color: opts.valueColor || C.navy,
  });
  addText(slide, label, x + 0.28, y + h * 0.59, w - 0.45, h * 0.25, {
    fontSize: opts.labelSize || 10.5,
    color: C.grey,
  });
}

// Slide 1 - title
{
  const slide = pptx.addSlide();
  addDarkBackdrop(slide);

  slide.addShape(S.rect, {
    x: 7.78, y: 0, w: 5.553, h: 7.5,
    fill: { color: C.navy2 },
    line: { transparency: 100 },
  });
  slide.addImage(cropTo(img.hero, 1440, 2160, 7.95, 0, 5.383, 7.5));
  slide.addShape(S.rect, {
    x: 7.65, y: 0, w: 5.683, h: 7.5,
    fill: { color: C.navy, transparency: 67 },
    line: { transparency: 100 },
  });
  slide.addShape(S.arc, {
    x: 9.0, y: 0.55, w: 3.4, h: 3.4,
    adjustPoint: 0.25,
    rotate: 18,
    fill: { color: C.navy, transparency: 100 },
    line: { color: C.teal, transparency: 25, width: 3 },
  });
  slide.addShape(S.arc, {
    x: 9.38, y: 0.93, w: 2.65, h: 2.65,
    rotate: 210,
    fill: { color: C.navy, transparency: 100 },
    line: { color: C.coral, transparency: 38, width: 2 },
  });

  pill(slide, 'ENGINEERING PROJECT PRESENTATION', 0.75, 0.65, 3.25, C.teal, C.navy, { h: 0.38, fontSize: 9.5, charSpacing: 1.1 });
  addText(slide, 'Real-Time Stress\nDetection', 0.75, 1.35, 6.45, 1.62, {
    fontFace: 'Aptos Display',
    fontSize: 32,
    bold: true,
    color: C.white,
    breakLine: true,
    valign: 'top',
    margin: 0,
  });
  addText(slide, 'using Physiological Signals\nand Machine Learning', 0.78, 3.05, 6.05, 0.86, {
    fontFace: 'Aptos Display',
    fontSize: 19,
    bold: false,
    color: 'C6D4EE',
    valign: 'top',
  });
  addText(slide, 'ESP32 wearable  •  leakage-safe ensemble  •  live web application', 0.78, 4.12, 6.32, 0.32, {
    fontSize: 11.5,
    bold: true,
    color: C.teal,
    charSpacing: 0.15,
  });
  slide.addShape(S.line, { x: 0.78, y: 5.13, w: 5.9, h: 0, line: { color: '35496E', width: 1 } });
  addText(slide, '[Student name(s)]  ·  [Roll number(s)]', 0.78, 5.38, 5.9, 0.33, {
    fontSize: 13,
    bold: true,
    color: C.white,
  });
  addText(slide, 'Supervisor: Dr. Anupam Kumar', 0.78, 5.82, 5.9, 0.28, {
    fontSize: 11.5,
    color: 'C6D4EE',
  });
  addText(slide, 'ECE Department · NIT Patna', 0.78, 6.16, 5.9, 0.28, {
    fontSize: 11.5,
    color: 'C6D4EE',
  });
  addText(slide, 'CONCEPT VISUAL', 11.3, 6.88, 1.55, 0.2, { fontSize: 7.5, bold: true, color: 'C6D4EE', align: 'right', charSpacing: 1.2 });
  addPageNumber(slide, 1, true);
  slide.addNotes('This project connects a multi-sensor wearable to a real-time machine-learning service and browser dashboard. The presentation focuses on the complete engineering pipeline, from sensing through a practical breathing response.');
}

// Slide 2 - introduction
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.sky);
  addHeader(slide, 2, 'Introduction', 'From biosignals to action');
  addText(slide, 'A wearable-to-web system that senses physiological changes, estimates stress probability, visualizes it live, and guides a calming response.', 0.72, 1.48, 11.92, 0.58, {
    fontSize: 17,
    color: C.grey,
    italic: true,
    align: 'center',
  });

  const stages = [
    { n: '01', t: 'SENSE', d: 'Three physiological\nsensors', fill: C.skyPale, accent: C.sky },
    { n: '02', t: 'PROCESS', d: '30 s windows\n18 features', fill: C.mint, accent: C.teal },
    { n: '03', t: 'PREDICT', d: 'Baseline vs. stress\nevery ~5 seconds', fill: C.violetPale, accent: C.violet },
    { n: '04', t: 'RESPOND', d: 'Live dashboard\nguided breathing', fill: C.coralPale, accent: C.coral },
  ];
  stages.forEach((s, i) => {
    const x = 0.72 + i * 3.08;
    if (i < stages.length - 1) addLine(slide, x + 2.66, 3.22, 0.43, 0, 'B7C1D2', 2, true);
    roundedCard(slide, x, 2.28, 2.66, 2.18, s.fill, { lineColor: s.accent, lineTransparency: 74 });
    slide.addShape(S.ellipse, {
      x: x + 0.2, y: 2.5, w: 0.58, h: 0.58,
      fill: { color: s.accent },
      line: { transparency: 100 },
    });
    addText(slide, s.n, x + 0.2, 2.5, 0.58, 0.58, { fontSize: 10, bold: true, color: C.white, align: 'center' });
    addText(slide, s.t, x + 0.2, 3.22, 2.22, 0.32, { fontSize: 15.5, bold: true, color: C.navy, charSpacing: 1.0 });
    addText(slide, s.d, x + 0.2, 3.62, 2.22, 0.55, { fontSize: 12, color: C.grey, valign: 'top' });
  });

  const chips = [
    ['5', 'sensors', C.sky],
    ['18', 'features', C.teal],
    ['16', 'subjects', C.violet],
    ['0.913', 'deployed accuracy', C.coral],
  ];
  chips.forEach((c, i) => {
    const x = 1.08 + i * 3.0;
    roundedCard(slide, x, 5.18, 2.55, 0.9, C.white, { lineColor: C.paleLine, lineTransparency: 0 });
    addText(slide, c[0], x + 0.18, 5.3, 0.85, 0.38, { fontSize: 20, bold: true, color: c[2], align: 'center' });
    addText(slide, c[1].toUpperCase(), x + 1.02, 5.36, 1.32, 0.25, { fontSize: 8.7, bold: true, color: C.grey, charSpacing: 0.8 });
  });
  addText(slide, 'Accuracy shown for deployed stacking under nested subject-independent evaluation.', 7.35, 6.23, 4.95, 0.22, { fontSize: 8.5, color: C.grey, align: 'right' });
  slide.addNotes('The system has four linked jobs: sense, process, predict, and respond. These proof points summarize the scale of the implementation before we look at each stage in detail.');
}

// Slide 3 - problem and objective
{
  const slide = pptx.addSlide();
  addDarkBackdrop(slide);
  addHeader(slide, 3, 'Motivation', 'Why real-time stress monitoring?', { dark: true, accent: C.coral });

  addText(slide, '“Can a wearable recognize\nsustained stress early enough\nto support self-regulation?”', 0.75, 1.68, 5.25, 2.0, {
    fontFace: 'Aptos Display',
    fontSize: 23,
    bold: true,
    color: C.white,
    valign: 'top',
    breakLine: true,
  });
  addText(slide, 'Stress can alter several signals at once. A multi-sensor view is more useful than relying on a single instantaneous reading.', 0.78, 4.05, 4.9, 0.92, {
    fontSize: 13,
    color: 'C8D3E9',
    valign: 'top',
  });

  const cards = [
    { y: 1.58, k: 'PROBLEM', h: 'Physiological change', d: 'Heart rate · skin conductance · temperature', a: C.coral },
    { y: 3.18, k: 'OBJECTIVE', h: 'Classify in near real time', d: 'Distinguish baseline from stress using fused wearable signals', a: C.teal },
    { y: 4.78, k: 'OUTCOME', h: 'Make the result actionable', d: 'Probability · live view · history · breathing prompt', a: C.gold },
  ];
  cards.forEach((c, i) => {
    if (i < cards.length - 1) addLine(slide, 8.09, c.y + 1.29, 0, 0.32, '546685', 2, true);
    roundedCard(slide, 6.25, c.y, 5.95, 1.26, '17294D', { lineColor: c.a, lineTransparency: 68, shadow: false });
    slide.addShape(S.ellipse, { x: 6.55, y: c.y + 0.27, w: 0.72, h: 0.72, fill: { color: c.a }, line: { transparency: 100 } });
    addText(slide, String(i + 1).padStart(2, '0'), 6.55, c.y + 0.27, 0.72, 0.72, { fontSize: 11, bold: true, color: C.navy, align: 'center' });
    addText(slide, c.k, 7.58, c.y + 0.16, 1.1, 0.22, { fontSize: 8.5, bold: true, color: c.a, charSpacing: 1.2 });
    addText(slide, c.h, 7.58, c.y + 0.42, 4.1, 0.3, { fontSize: 15, bold: true, color: C.white });
    addText(slide, c.d, 7.58, c.y + 0.78, 4.1, 0.28, { fontSize: 10.5, color: 'BAC7E0' });
  });
  pill(slide, 'ENGINEERING PROTOTYPE - NOT A MEDICAL DIAGNOSTIC DEVICE', 0.78, 6.18, 4.85, '26385E', 'D2DCEF', { h: 0.42, fontSize: 8.8, lineColor: '405377' });
  slide.addNotes('Stress is not read directly from one sensor. The goal is to combine three physiological signals, estimate a probability, and present it in a way that supports timely action without making a medical diagnosis.');
}

// Slide 4 - architecture
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.teal);
  addHeader(slide, 4, 'System design', 'How the system works');
  const stages = [
    { n: '01', t: 'WEARABLE', d: 'MAX30105 · GSR\nMLX90614', a: C.sky, f: C.skyPale },
    { n: '02', t: 'ACQUIRE', d: 'ESP32\nUSB serial', a: C.teal, f: C.mint },
    { n: '03', t: 'PROCESS', d: '30 s window\n18 features', a: C.gold, f: C.goldPale },
    { n: '04', t: 'INFER', d: 'Stacking\nEMA smoothing', a: C.violet, f: C.violetPale },
    { n: '05', t: 'PRESENT', d: 'WebSocket\nReact + SQLite', a: C.coral, f: C.coralPale },
  ];
  stages.forEach((s, i) => {
    const x = 0.58 + i * 2.55;
    if (i < 4) addLine(slide, x + 2.22, 3.0, 0.34, 0, 'AAB5C7', 2.2, true);
    roundedCard(slide, x, 1.78, 2.2, 2.5, s.f, { lineColor: s.a, lineTransparency: 65 });
    addText(slide, s.n, x + 0.18, 1.98, 0.42, 0.28, { fontSize: 9, bold: true, color: s.a, charSpacing: 1 });
    slide.addShape(S.ellipse, { x: x + 0.73, y: 2.15, w: 0.74, h: 0.74, fill: { color: s.a }, line: { transparency: 100 } });
    addText(slide, String(i + 1), x + 0.73, 2.15, 0.74, 0.74, { fontSize: 15, bold: true, color: i === 2 ? C.navy : C.white, align: 'center' });
    addText(slide, s.t, x + 0.18, 3.03, 1.84, 0.28, { fontSize: 12, bold: true, color: C.navy, align: 'center', charSpacing: 0.7 });
    addText(slide, s.d, x + 0.18, 3.42, 1.84, 0.55, { fontSize: 10.5, color: C.grey, align: 'center', valign: 'top' });
  });

  roundedCard(slide, 0.68, 4.78, 5.76, 1.25, C.white, { lineColor: C.paleLine, lineTransparency: 0 });
  addText(slide, 'PLUGGABLE INPUT', 0.96, 4.99, 1.55, 0.22, { fontSize: 8.8, bold: true, color: C.teal, charSpacing: 1.2 });
  addText(slide, 'Serial hardware  ·  CSV replay  ·  TCP  ·  Synthetic/demo', 0.96, 5.35, 4.98, 0.32, { fontSize: 13, bold: true, color: C.navy });

  roundedCard(slide, 6.78, 4.78, 5.87, 1.25, C.navy, { lineColor: C.navy, shadow: true });
  addText(slide, 'LIVE CADENCE', 7.08, 4.99, 1.4, 0.22, { fontSize: 8.8, bold: true, color: C.gold, charSpacing: 1.2 });
  addText(slide, 'A new prediction about every 5 seconds after the first window fills.', 7.08, 5.32, 5.08, 0.38, { fontSize: 13, bold: true, color: C.white });
  addText(slide, '115200 baud  •  authenticated WebSocket  •  train/serve feature parity', 0.72, 6.37, 11.9, 0.24, { fontSize: 9.4, color: C.grey, align: 'center' });
  slide.addNotes('The three-sensor hardware produces a one-hertz summary over USB serial. The service buffers thirty seconds, extracts the same eighteen features used in training, classifies and smooths the result, then pushes it to the browser and session database.');
}

// Slide 5 - hardware
{
  const slide = pptx.addSlide();
  addDarkBackdrop(slide);
  addHeader(slide, 5, 'Hardware', 'Three-sensor wearable', { dark: true, accent: C.sky });

  const center = { x: 5.0, y: 2.48, w: 3.33, h: 2.12 };
  const nodes = [
    { x: 0.78, y: 1.65, w: 3.1, h: 1.18, t: 'MAX30105', d: 'Optical heart rate / BPM', a: C.sky, anchorX: 5.05, anchorY: 2.88 },
    { x: 0.78, y: 3.25, w: 3.1, h: 1.18, t: 'GSR SENSOR', d: 'Electrodermal activity · raw ADC', a: C.coral, anchorX: 5.05, anchorY: 3.48 },
    { x: 9.45, y: 2.42, w: 3.1, h: 1.18, t: 'MLX90614', d: 'Temperature', a: C.gold, anchorX: 8.28, anchorY: 3.15 },
  ];
  nodes.forEach((n) => {
    const startX = n.x < center.x ? n.x + n.w : n.x;
    const startY = n.y + n.h / 2;
    addLine(slide, startX, startY, n.anchorX - startX, n.anchorY - startY, n.a, 2.1, false);
  });

  roundedCard(slide, center.x, center.y, center.w, center.h, '182C53', { lineColor: C.teal, lineTransparency: 0, lineWidth: 2.2 });
  slide.addShape(S.ellipse, { x: 6.16, y: 2.8, w: 1.02, h: 1.02, fill: { color: C.teal }, line: { transparency: 100 } });
  addText(slide, 'ESP', 6.16, 2.8, 1.02, 1.02, { fontSize: 15, bold: true, color: C.navy, align: 'center' });
  addText(slide, 'ESP32 DEVKIT V1', 5.35, 3.98, 2.63, 0.3, { fontSize: 13.8, bold: true, color: C.white, align: 'center', charSpacing: 0.5 });
  addText(slide, 'Acquisition + USB serial streaming', 5.35, 4.32, 2.63, 0.22, { fontSize: 9.8, color: 'C3D0E7', align: 'center' });

  nodes.forEach((n) => {
    roundedCard(slide, n.x, n.y, n.w, n.h, '16284B', { lineColor: n.a, lineTransparency: 45, shadow: false });
    slide.addShape(S.rect, { x: n.x, y: n.y, w: 0.08, h: n.h, fill: { color: n.a }, line: { transparency: 100 } });
    addText(slide, n.t, n.x + 0.26, n.y + 0.18, n.w - 0.48, 0.3, { fontSize: 12, bold: true, color: C.white });
    addText(slide, n.d, n.x + 0.26, n.y + 0.59, n.w - 0.48, 0.3, { fontSize: 9.8, color: 'BBC9E1' });
  });

  pill(slide, '1 Hz SENSOR SUMMARY', 5.12, 5.1, 1.58, '263A61', C.white, { h: 0.42, fontSize: 8.3, lineColor: '41557B' });
  pill(slide, 'USB · 115200 BAUD', 6.82, 5.1, 1.64, C.teal, C.navy, { h: 0.42, fontSize: 8.3 });
  addText(slide, 'MAX30105 heart rate, GSR skin conductance, and MLX90614 temperature form the complete hardware input.', 4.68, 5.76, 4.0, 0.55, { fontSize: 10.2, color: 'C7D3E8', align: 'center', valign: 'top' });
  addText(slide, 'Research prototype - not a medical diagnostic device.', 0.78, 6.77, 6.0, 0.22, { fontSize: 8.5, color: '9FADC7' });
  slide.addNotes('Three sensors feed the ESP32: MAX30105 supplies heart rate, GSR supplies skin conductance, and MLX90614 supplies temperature.');
}

// Slide 6 - data and features
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.gold);
  addHeader(slide, 6, 'Signal processing', 'From raw signals to model features');

  roundedCard(slide, 0.68, 1.55, 3.42, 4.9, C.navy, { lineColor: C.navy });
  addText(slide, 'DATASET', 0.98, 1.82, 1.0, 0.22, { fontSize: 8.8, bold: true, color: C.gold, charSpacing: 1.4 });
  addText(slide, '16', 0.98, 2.15, 1.25, 0.76, { fontFace: 'Aptos Display', fontSize: 34, bold: true, color: C.white });
  addText(slide, 'subjects', 2.05, 2.42, 1.25, 0.28, { fontSize: 13, bold: true, color: 'C6D3E9' });
  addText(slide, '15 WESAD + 1 project-hardware subject', 0.98, 2.92, 2.62, 0.5, { fontSize: 10.5, color: 'AEBBD4', valign: 'top' });
  addText(slide, '5,462', 0.98, 3.55, 2.15, 0.62, { fontFace: 'Aptos Display', fontSize: 28, bold: true, color: C.teal });
  addText(slide, 'windows', 2.25, 3.74, 1.05, 0.28, { fontSize: 12, bold: true, color: 'C6D3E9' });
  addText(slide, 'BASELINE  3,498', 0.98, 4.47, 1.5, 0.22, { fontSize: 8.8, bold: true, color: 'C6D3E9' });
  addText(slide, 'STRESS  1,964', 2.4, 4.47, 1.08, 0.22, { fontSize: 8.8, bold: true, color: 'C6D3E9', align: 'right' });
  slide.addShape(S.rect, { x: 0.98, y: 4.81, w: 2.78, h: 0.28, fill: { color: C.teal }, line: { transparency: 100 } });
  slide.addShape(S.rect, { x: 0.98 + 2.78 * 0.6404, y: 4.81, w: 2.78 * 0.3596, h: 0.28, fill: { color: C.coral }, line: { transparency: 100 } });
  addText(slide, '64%', 1.02, 5.14, 0.6, 0.22, { fontSize: 9, bold: true, color: C.teal });
  addText(slide, '36%', 3.0, 5.14, 0.58, 0.22, { fontSize: 9, bold: true, color: C.coral, align: 'right' });
  addText(slide, 'QUALITY GATE', 0.98, 5.6, 1.15, 0.22, { fontSize: 8.6, bold: true, color: C.gold, charSpacing: 1.1 });
  addText(slide, 'BPM 40–200 · at least 70% valid samples per window', 0.98, 5.91, 2.65, 0.38, { fontSize: 9.5, color: 'C6D3E9' });

  addText(slide, 'LIVE FEATURE PIPELINE', 4.48, 1.61, 2.0, 0.22, { fontSize: 8.8, bold: true, color: C.teal, charSpacing: 1.2 });
  const flow = [
    ['1 Hz', 'sensor summary'],
    ['✓', 'quality checks'],
    ['30 s', 'window'],
    ['5 s', 'stride'],
    ['18', 'features'],
  ];
  flow.forEach((f, i) => {
    const x = 4.45 + i * 1.62;
    if (i < flow.length - 1) addLine(slide, x + 1.3, 2.52, 0.34, 0, 'ADB8CA', 1.8, true);
    roundedCard(slide, x, 2.02, 1.3, 1.05, i === 4 ? C.mint : C.white, { lineColor: i === 4 ? C.teal : C.paleLine, lineTransparency: 0, shadow: false });
    addText(slide, f[0], x + 0.1, 2.16, 1.1, 0.32, { fontSize: 15, bold: true, color: i === 4 ? C.teal : C.navy, align: 'center' });
    addText(slide, f[1].toUpperCase(), x + 0.08, 2.61, 1.14, 0.2, { fontSize: 7.8, bold: true, color: C.grey, align: 'center', charSpacing: 0.5 });
  });

  const featureCards = [
    { x: 4.45, y: 3.48, t: 'HEART RATE / PPG', n: '7', d: 'mean · variation · range\nslope · pNN proxy', a: C.sky, f: C.skyPale },
    { x: 8.58, y: 3.48, t: 'GSR', n: '8', d: 'level · variation · range\nslope · area · peaks', a: C.coral, f: C.coralPale },
    { x: 4.45, y: 5.02, t: 'TEMPERATURE', n: '3', d: 'mean · variation · slope', a: C.gold, f: C.goldPale },
  ];
  featureCards.forEach((f) => {
    roundedCard(slide, f.x, f.y, 3.72, 1.22, f.f, { lineColor: f.a, lineTransparency: 68 });
    slide.addShape(S.ellipse, { x: f.x + 0.22, y: f.y + 0.24, w: 0.66, h: 0.66, fill: { color: f.a }, line: { transparency: 100 } });
    addText(slide, f.n, f.x + 0.22, f.y + 0.24, 0.66, 0.66, { fontSize: 15, bold: true, color: f.a === C.gold ? C.navy : C.white, align: 'center' });
    addText(slide, f.t, f.x + 1.05, f.y + 0.18, 2.38, 0.26, { fontSize: 10.5, bold: true, color: C.navy, charSpacing: 0.4 });
    addText(slide, f.d, f.x + 1.05, f.y + 0.53, 2.38, 0.47, { fontSize: 9.5, color: C.grey, valign: 'top' });
  });
  addText(slide, 'Same 18-feature ordering in training and live inference.', 4.48, 6.48, 5.2, 0.24, { fontSize: 9.3, bold: true, color: C.teal });
  addText(slide, 'WESAD - Schmidt et al., 2018', 9.25, 6.48, 3.15, 0.24, { fontSize: 8.5, color: C.grey, align: 'right' });
  slide.addNotes('The evaluation combines fifteen WESAD subjects with one project-hardware subject. Every thirty-second window becomes a fixed eighteen-feature vector, and the exact same extraction code and column order are used offline and in the live service.');
}

// Slide 7 - ensemble
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.violet);
  addHeader(slide, 7, 'Machine learning', 'Leakage-safe multi-model ensemble', { accent: C.violet });

  const models = [
    { x: 0.72, t: 'RBF SVM', d: 'baseline + fallback', a: C.sky, f: C.skyPale },
    { x: 3.56, t: 'RANDOM FOREST', d: 'tree ensemble', a: C.teal, f: C.mint },
    { x: 6.4, t: 'XGBOOST', d: 'gradient boosting', a: C.gold, f: C.goldPale },
    { x: 9.24, t: 'MLP 64–32–16', d: 'neural network', a: C.coral, f: C.coralPale },
  ];
  models.forEach((m) => {
    roundedCard(slide, m.x, 1.62, 2.42, 1.24, m.f, { lineColor: m.a, lineTransparency: 62 });
    slide.addShape(S.ellipse, { x: m.x + 0.18, y: 1.9, w: 0.54, h: 0.54, fill: { color: m.a }, line: { transparency: 100 } });
    addText(slide, 'P', m.x + 0.18, 1.9, 0.54, 0.54, { fontSize: 13, bold: true, color: m.a === C.gold ? C.navy : C.white, align: 'center' });
    addText(slide, m.t, m.x + 0.86, 1.78, 1.33, 0.32, { fontSize: 11.2, bold: true, color: C.navy, align: 'center' });
    addText(slide, m.d, m.x + 0.83, 2.24, 1.4, 0.22, { fontSize: 8.8, color: C.grey, align: 'center' });
    addLine(slide, m.x + 1.21, 2.87, 0, 0.47, 'ABB7C9', 1.6, true);
  });

  roundedCard(slide, 4.85, 3.27, 3.63, 0.75, C.navy, { lineColor: C.navy, shadow: true });
  addText(slide, 'FOUR P(STRESS) OUTPUTS', 5.15, 3.45, 3.03, 0.31, { fontSize: 12.5, bold: true, color: C.white, align: 'center', charSpacing: 0.6 });
  addLine(slide, 6.67, 4.02, -2.75, 0.44, 'A9B4C7', 1.8, true);
  addLine(slide, 6.67, 4.02, 2.75, 0.44, 'A9B4C7', 1.8, true);

  roundedCard(slide, 1.7, 4.48, 4.05, 1.12, C.white, { lineColor: C.paleLine, lineTransparency: 0 });
  addText(slide, 'SOFT VOTING', 2.02, 4.67, 1.55, 0.25, { fontSize: 11.5, bold: true, color: C.teal, charSpacing: 0.7 });
  addText(slide, 'Average the four model probabilities', 2.02, 5.08, 3.3, 0.27, { fontSize: 11, color: C.grey });

  roundedCard(slide, 7.58, 4.42, 4.1, 1.25, C.violet, { lineColor: C.violet, shadow: true });
  pill(slide, 'DEPLOYED', 10.24, 4.6, 1.1, C.gold, C.navy, { h: 0.32, fontSize: 8.2 });
  addText(slide, 'STACKING', 7.9, 4.64, 1.55, 0.27, { fontSize: 12.2, bold: true, color: C.white, charSpacing: 0.7 });
  addText(slide, 'Logistic Regression learns the combination', 7.9, 5.09, 3.38, 0.28, { fontSize: 10.8, color: 'E6E4FF' });

  roundedCard(slide, 0.72, 6.02, 11.9, 0.68, 'E9E7FA', { lineColor: C.violet, lineTransparency: 65, shadow: false });
  addText(slide, 'LEAKAGE GUARD', 0.95, 6.18, 1.28, 0.2, { fontSize: 8.4, bold: true, color: C.violet, charSpacing: 1.1 });
  addText(slide, 'Hold out one subject  →  train on the others  →  grouped out-of-fold probabilities  →  train meta-model  →  test once', 2.35, 6.12, 9.85, 0.28, { fontSize: 9.8, bold: true, color: C.navy, align: 'center' });
  addText(slide, 'No data from the held-out subject enters tuning or training.', 4.15, 6.82, 5.0, 0.22, { fontSize: 9, bold: true, color: C.violet, align: 'center' });
  slide.addNotes('Four base models produce separate stress probabilities. Soft voting averages them, while the deployed stacking model learns their combination from grouped out-of-fold predictions, ensuring the held-out subject never leaks into model selection or training.');
}

// Slide 8 - results
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.sky);
  addHeader(slide, 8, 'Evaluation', 'Subject-independent model results');
  pill(slide, 'NESTED LOSO  ·  16 SUBJECTS  ·  5,462 WINDOWS', 0.72, 1.42, 4.08, C.navy, C.white, { h: 0.38, fontSize: 8.6, charSpacing: 0.7 });

  roundedCard(slide, 0.68, 1.94, 7.35, 3.94, C.white, { lineColor: C.paleLine, lineTransparency: 0 });
  slide.addChart(pptx.ChartType.bar, [
    {
      name: 'Macro-F1',
      labels: ['Wtd. voting', 'Soft voting', 'Stacking', 'MLP', 'SVM baseline', 'XGBoost', 'Random Forest'],
      values: [0.910, 0.910, 0.906, 0.895, 0.889, 0.885, 0.873],
    },
  ], {
    x: 0.94, y: 2.15, w: 6.78, h: 3.44,
    showTitle: false,
    showLegend: false,
    showValue: true,
    showCatName: false,
    chartColors: [C.teal],
    showCategoryName: false,
    catAxisLabelFontFace: 'Aptos',
    catAxisLabelFontSize: 10,
    catAxisLabelColor: C.grey,
    catAxisLineColor: C.paleLine,
    catAxisReverseOrder: true,
    valAxisLabelFontFace: 'Aptos',
    valAxisLabelFontSize: 8,
    valAxisLabelColor: C.grey,
    valAxisMinVal: 0.84,
    valAxisMaxVal: 0.92,
    valAxisMajorUnit: 0.02,
    valAxisLabelFormatCode: '0.00',
    valGridLine: { color: 'E3E7EF', width: 1 },
    dataLabelColor: C.navy,
    dataLabelPosition: 'outEnd',
    dataLabelFormatCode: '0.000',
    dataLabelFormatString: '0.000',
    showBorder: false,
    showValue: true,
    gapWidthPct: 42,
  });

  metricCard(slide, 8.35, 1.75, 4.2, 1.16, '0.918  /  0.910', 'weighted soft voting · accuracy / macro-F1', C.teal, { valueSize: 21 });
  metricCard(slide, 8.35, 3.15, 4.2, 1.16, '0.913  /  0.906', 'deployed stacking · accuracy / macro-F1', C.violet, { valueSize: 21, fill: C.violetPale, lineColor: C.violet });
  metricCard(slide, 8.35, 4.55, 4.2, 1.16, '0.897  /  0.889', 'SVM baseline · accuracy / macro-F1', C.coral, { valueSize: 21 });

  roundedCard(slide, 0.68, 6.12, 11.87, 0.7, C.navy, { lineColor: C.navy, shadow: false });
  addText(slide, 'HONEST INTERPRETATION', 0.96, 6.31, 1.62, 0.2, { fontSize: 8.2, bold: true, color: C.gold, charSpacing: 1.0 });
  addText(slide, 'Ensembles lead on pooled metrics, but the per-subject difference from SVM is not statistically significant at n = 16.', 2.7, 6.24, 9.4, 0.28, { fontSize: 10.4, bold: true, color: C.white, align: 'center' });
  addText(slide, 'Source: project evaluation reports · ROC-AUC: stacking 0.962 · SVM 0.955', 6.28, 6.9, 6.0, 0.2, { fontSize: 8.2, color: C.grey, align: 'right' });
  slide.addNotes('Weighted soft voting has the highest pooled score, while stacking is the deployed model because it learns its combination from out-of-fold data. The gap is small relative to between-subject variation, so the defensible claim is comparable performance rather than proven superiority.');
}

// Slide 9 - live dashboard
{
  const slide = pptx.addSlide();
  addDarkBackdrop(slide);
  addHeader(slide, 9, 'Live application', 'Baseline to stress alert - live', { dark: true, accent: C.teal });

  roundedCard(slide, 0.55, 1.5, 6.04, 3.75, '172849', { lineColor: '314365', lineTransparency: 0, shadow: true });
  roundedCard(slide, 6.75, 1.5, 6.04, 3.75, '172849', { lineColor: '314365', lineTransparency: 0, shadow: true });
  pill(slide, 'BASELINE · P(STRESS) 10%', 0.78, 1.68, 2.34, C.green, C.white, { h: 0.34, fontSize: 8.5 });
  pill(slide, 'STRESS ALERT · P(STRESS) 98%', 6.98, 1.68, 2.72, C.red, C.white, { h: 0.34, fontSize: 8.5 });
  slide.addImage(contain(img.baseline, 2992, 1694, 0.76, 2.14, 5.62, 2.93));
  slide.addImage(contain(img.stress, 2992, 1694, 6.96, 2.14, 5.62, 2.93));

  const callouts = [
    { x: 0.72, t: 'LIVE SIGNALS', d: 'Heart-rate trace + HRV proxy', a: C.sky },
    { x: 4.48, t: 'SENSOR CONTEXT', d: 'Heart rate · GSR · temperature', a: C.teal },
    { x: 8.24, t: 'ACTION', d: 'Sustained stress → breathing prompt', a: C.coral },
  ];
  callouts.forEach((c) => {
    roundedCard(slide, c.x, 5.58, 3.56, 0.92, '182A4D', { lineColor: c.a, lineTransparency: 70, shadow: false });
    slide.addShape(S.ellipse, { x: c.x + 0.18, y: 5.79, w: 0.42, h: 0.42, fill: { color: c.a }, line: { transparency: 100 } });
    addText(slide, '•', c.x + 0.18, 5.76, 0.42, 0.42, { fontSize: 18, bold: true, color: C.navy, align: 'center' });
    addText(slide, c.t, c.x + 0.76, 5.69, 2.5, 0.2, { fontSize: 8.4, bold: true, color: c.a, charSpacing: 0.8 });
    addText(slide, c.d, c.x + 0.76, 6.0, 2.55, 0.24, { fontSize: 9.8, color: C.white });
  });
  addText(slide, 'Snapshots from the working dashboard/demo pipeline · authenticated WebSocket updates · EMA smoothing reduces flicker', 0.78, 6.75, 11.7, 0.22, { fontSize: 8.7, color: 'AAB9D2', align: 'center' });
  slide.addNotes('These are real application screenshots. The service streams samples, feature vectors, and predictions over an authenticated WebSocket, and the exponential moving average prevents the displayed state from flickering between individual windows.');
}

// Slide 10 - application experience
{
  const slide = pptx.addSlide();
  addLightBackdrop(slide, C.coral);
  addHeader(slide, 10, 'Application experience', 'Beyond detection: track, personalize, respond', { accent: C.coral, fontSize: 23.5 });
  const cards = [
    { x: 0.55, img: img.session, tag: 'TRACK', title: 'Session history', desc: 'Timeline, annotations, and CSV / JSON export.', a: C.sky, f: C.skyPale },
    { x: 4.47, img: img.calibration, tag: 'PERSONALIZE', title: 'Resting baseline', desc: 'Optional per-user calibration, clearly labelled as a heuristic.', a: C.teal, f: C.mint },
    { x: 8.39, img: img.breathing, tag: 'RESPOND', title: 'Guided breathing', desc: 'Box, 4-7-8, and coherent breathing patterns.', a: C.coral, f: C.coralPale },
  ];
  cards.forEach((c) => {
    roundedCard(slide, c.x, 1.55, 3.75, 4.42, C.white, { lineColor: c.a, lineTransparency: 72 });
    slide.addImage(contain(c.img, 2992, 1694, c.x + 0.16, 1.72, 3.43, 1.94));
    pill(slide, c.tag, c.x + 0.23, 3.86, 1.28, c.a, c.a === C.gold ? C.navy : C.white, { h: 0.33, fontSize: 8.2, charSpacing: 0.8 });
    addText(slide, c.title, c.x + 0.23, 4.34, 3.05, 0.36, { fontSize: 16, bold: true, color: C.navy });
    addText(slide, c.desc, c.x + 0.23, 4.87, 3.05, 0.67, { fontSize: 10.5, color: C.grey, valign: 'top' });
  });
  pill(slide, 'JWT LOGIN', 0.85, 6.18, 1.35, C.navy, C.white, { h: 0.36, fontSize: 8.2 });
  pill(slide, 'SQLITE PERSISTENCE', 2.42, 6.18, 1.85, C.navy, C.white, { h: 0.36, fontSize: 8.2 });
  pill(slide, 'WEBSOCKET AUTO-RECONNECT', 4.49, 6.18, 2.44, C.navy, C.white, { h: 0.36, fontSize: 8.2 });
  pill(slide, 'HARDWARE-FREE DEMO MODE', 7.16, 6.18, 2.47, C.navy, C.white, { h: 0.36, fontSize: 8.2 });
  pill(slide, 'EXPORTABLE SESSIONS', 9.86, 6.18, 1.95, C.navy, C.white, { h: 0.36, fontSize: 8.2 });
  roundedCard(slide, 0.68, 6.75, 11.96, 0.52, C.navy, { lineColor: C.navy, shadow: false });
  addText(slide, 'A complete path from wearable biosignals to leakage-aware ML, live visualization, and a practical response.', 0.98, 6.86, 11.36, 0.25, { fontSize: 11.2, bold: true, color: C.white, align: 'center' });
  slide.addNotes('The application does more than display a label. It records sessions, supports an explicitly heuristic personal baseline, and connects sustained stress to a guided breathing exercise, while remaining demonstrable without the physical wearable.');
}

pptx.writeFile({ fileName: OUT });
