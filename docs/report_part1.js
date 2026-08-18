// ═══════════════════════════════════════════════════════════════════════════
// OrchestrAI Final Dissertation Report — Part 1: Helpers + Chapters 1-2
// ═══════════════════════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  PageBreak, Table, TableRow, TableCell, WidthType, BorderStyle,
  ShadingType, Header, Footer, PageNumber, NumberFormat, LevelFormat,
  convertInchesToTwip, UnderlineType, LineRuleType, TabStopType, ImageRun,
} = require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/node_modules/docx');

// ── Colour palette ──────────────────────────────────────────────────────────
const NAVY  = '003366';
const BLACK = '000000';
const DARK  = '1A1A2E';
const GRAY  = '595959';
const LGRAY = 'D0D7DE';
const BLUE2 = '1A3A5C';
const CODE_BG = 'F3F4F6';

// ── Image directory ─────────────────────────────────────────────────────────
const IMGS = '/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/imgs';

// ── Core text helpers ───────────────────────────────────────────────────────
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 24, font: 'Times New Roman', color: BLACK, ...opts })],
    spacing: { after: 120, line: 300, lineRule: LineRuleType.AUTO },
    alignment: AlignmentType.JUSTIFIED,
  });
}
function pRuns(runs, align = AlignmentType.JUSTIFIED) {
  return new Paragraph({
    children: runs.map(r => new TextRun({ size: 24, font: 'Times New Roman', color: BLACK, ...r })),
    spacing: { after: 120, line: 300, lineRule: LineRuleType.AUTO },
    alignment: align,
  });
}
function h1(text, pgBreakBefore = true) {
  return new Paragraph({
    children: [new TextRun({ text, size: 30, bold: true, font: 'Times New Roman', color: NAVY })],
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: pgBreakBefore,
    spacing: { before: 240, after: 140 },
  });
}
function h2(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: 26, bold: true, font: 'Times New Roman', color: BLUE2 })],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 100 },
  });
}
function h3(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: 24, bold: true, font: 'Times New Roman', color: DARK })],
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 140, after: 60 },
  });
}
function sp(pts = 160) {
  return new Paragraph({ spacing: { after: pts } });
}
function pgBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}
function centred(text, size = 24, bold = false, color = BLACK) {
  return new Paragraph({
    children: [new TextRun({ text, size, bold, font: 'Times New Roman', color })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    children: [new TextRun({ text, size: 24, font: 'Times New Roman' })],
    bullet: { level },
    spacing: { after: 120, line: 340, lineRule: LineRuleType.AUTO },
  });
}
function numbered(text, level = 0) {
  return new Paragraph({
    children: [new TextRun({ text, size: 24, font: 'Times New Roman' })],
    numbering: { reference: 'num-list', level },
    spacing: { after: 120, line: 340, lineRule: LineRuleType.AUTO },
  });
}
function codeBlock(lines) {
  return new Paragraph({
    children: [new TextRun({ text: lines, size: 20, font: 'Courier New', color: '1A3A5C' })],
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'EEF2F7' },
    spacing: { after: 160, before: 80 },
    indent: { left: 360 },
  });
}
function figCap(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, size: 22, font: 'Times New Roman', color: GRAY })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 200 },
  });
}
function tblCap(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 22, font: 'Times New Roman', color: BLACK })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 80 },
  });
}

// ── Image helper ─────────────────────────────────────────────────────────────
function fig(name, w, h) {
  const data = fs.readFileSync(`${IMGS}/${name}`);
  return new Paragraph({
    children: [new ImageRun({ data, transformation: { width: w, height: h }, type: 'png' })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 80 },
  });
}

// ── Table helpers ───────────────────────────────────────────────────────────
function tc(text, { bold = false, shade = false, width = 2000, center = false, color = BLACK, italic = false } = {}) {
  return new TableCell({
    children: [new Paragraph({
      children: [new TextRun({ text, bold, italics: italic, size: 22, font: 'Times New Roman', color })],
      spacing: { after: 60, before: 60 },
      alignment: center ? AlignmentType.CENTER : AlignmentType.LEFT,
    })],
    width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, color: 'auto', fill: 'E2EBF5' } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: LGRAY },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: LGRAY },
      left: { style: BorderStyle.SINGLE, size: 6, color: LGRAY },
      right: { style: BorderStyle.SINGLE, size: 6, color: LGRAY },
    },
  });
}
function tbl(rows, colWidths) {
  return new Table({
    rows,
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: colWidths,
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// COVER PAGE — BITS Pilani institutional format (matching mid-term report)
// ══════════════════════════════════════════════════════════════════════════════
function coverPages() {
  const logoData = fs.readFileSync(`${IMGS}/bits_logo.png`);
  function cb(text, size, bold, color, afterSp) {
    return new Paragraph({
      children: [new TextRun({ text, size: size || 24, bold: !!bold, font: 'Times New Roman', color: color || BLACK })],
      alignment: AlignmentType.CENTER,
      spacing: { after: afterSp !== undefined ? afterSp : 100 },
    });
  }
  return [
    // Top spacer — push title down from header
    sp(600),

    // Title (large, navy, bold)
    cb('OrchestrAI: An Autonomous Multi-Agent AI Platform for', 52, true, NAVY, 0),
    new Paragraph({
      children: [new TextRun({ text: 'Self-Healing Data Pipelines', size: 52, bold: true, font: 'Times New Roman', color: NAVY })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 560 },
    }),

    // Course info
    cb('Course No.: AIMLCZG628T', 24, true, BLACK, 100),
    new Paragraph({
      children: [new TextRun({ text: 'Course Title: Dissertation', size: 24, bold: true, font: 'Times New Roman', color: BLACK })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 480 },
    }),

    // "Done by" section
    new Paragraph({
      children: [new TextRun({ text: 'Dissertation / Project / Project Work Done by:', size: 24, bold: true, font: 'Times New Roman' })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
    }),

    // Student info
    cb('Student Name: PATEL PARTHIV RAJESHBHAI', 24, true, BLACK, 100),
    cb('BITS ID: 2024AA05129', 24, true, BLACK, 100),
    cb('Degree Program: M.Tech Artificial Intelligence and Machine Learning', 24, true, BLACK, 100),
    new Paragraph({
      children: [new TextRun({ text: 'Research Area: Artificial Intelligence', size: 24, bold: true, font: 'Times New Roman' })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 480 },
    }),

    // Organization
    cb('Dissertation / Project Work carried out at:', 24, true, BLACK, 100),
    new Paragraph({
      children: [new TextRun({ text: 'Hevo Technologies India Pvt. Ltd., Bengaluru – 560102', size: 24, bold: true, font: 'Times New Roman' })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 560 },
    }),

    // BITS Logo (square, 160×160)
    new Paragraph({
      children: [new ImageRun({ data: logoData, transformation: { width: 160, height: 160 }, type: 'png' })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 400 },
    }),

    // Institute name
    cb('BIRLA INSTITUTE OF TECHNOLOGY & SCIENCE,', 28, true, NAVY, 0),
    new Paragraph({
      children: [new TextRun({ text: 'PILANI VIDYA VIHAR, PILANI, RAJASTHAN – 333031', size: 28, bold: true, font: 'Times New Roman', color: NAVY })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),

    // Date
    new Paragraph({
      children: [new TextRun({ text: '(July 2026)', size: 24, font: 'Times New Roman' })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),

    pgBreak(),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// ACKNOWLEDGEMENTS
// ══════════════════════════════════════════════════════════════════════════════
function acknowledgements() {
  return [
    new Paragraph({ children: [new TextRun({ text: 'i', size: 22, font: 'Times New Roman', color: GRAY })], alignment: AlignmentType.RIGHT }),
    new Paragraph({ children: [new TextRun({ text: 'ACKNOWLEDGEMENTS', size: 28, bold: true, font: 'Times New Roman', color: NAVY })], alignment: AlignmentType.CENTER, spacing: { before: 0, after: 360 } }),
    p('I wish to express my heartfelt gratitude to my industry supervisor, Vinayak Bamane (Senior Data Engineering Lead, Hevo Technologies India Pvt. Ltd.), whose technical mentorship shaped every major design decision in OrchestrAI. His deep knowledge of production data pipelines, failure patterns encountered at scale, and cloud-native SaaS architecture directly informed the problem formulation, anomaly detection strategy, and the human-in-the-loop approval gate design.'),
    p('I am equally grateful to my Faculty Mentor at BITS Pilani, WILP Division, for academic rigour, constructive feedback during semester reviews, and insistence that every engineering claim be backed by controlled experiments with statistical significance. His guidance on research methodology — particularly the Design Science Research framework — was invaluable.'),
    p('I thank the engineering team at Hevo Technologies for sharing operational telemetry patterns and reviewing early architecture drafts. Their practitioner perspective ensured that OrchestrAI\'s anomaly categories and healing strategies are grounded in production reality.'),
    p('I acknowledge the open-source communities behind LangGraph, FastAPI, ChromaDB, scikit-learn, Next.js, and Groq — the platform would not have been possible without these well-designed libraries.'),
    p('Finally, I thank my family for unwavering support, and my WILP MTech batch-mates for stimulating discussions and the shared understanding of building production-quality systems while working full time.'),
    sp(400),
    new Paragraph({ children: [new TextRun({ text: 'Parthiv Patel', size: 24, font: 'Times New Roman' })], alignment: AlignmentType.RIGHT, spacing: { after: 60 } }),
    new Paragraph({ children: [new TextRun({ text: 'July 2026, Bengaluru', size: 24, font: 'Times New Roman' })], alignment: AlignmentType.RIGHT }),
    pgBreak(),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// PROJECT DETAILS PAGE
// ══════════════════════════════════════════════════════════════════════════════
function projectDetails() {
  return [
    new Paragraph({ children: [new TextRun({ text: 'ii', size: 22, font: 'Times New Roman', color: GRAY })], alignment: AlignmentType.RIGHT }),
    centred('BIRLA INSTITUTE OF TECHNOLOGY AND SCIENCE, PILANI', 28, true, NAVY),
    centred('(RAJASTHAN)', 22, false, NAVY),
    new Paragraph({ children: [new TextRun({ text: 'WILP Division', size: 22, italics: true, font: 'Times New Roman', color: GRAY })], alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
    tbl([
      new TableRow({ children: [tc('Organization:', { bold: true, shade: true, width: 3000 }), tc('Hevo Technologies India Pvt. Ltd.', { width: 6360 })] }),
      new TableRow({ children: [tc('Location:', { bold: true, shade: true, width: 3000 }), tc('Bengaluru, Karnataka', { width: 6360 })] }),
      new TableRow({ children: [tc('Duration:', { bold: true, shade: true, width: 3000 }), tc('6 months (January 2026 – July 2026)', { width: 6360 })] }),
      new TableRow({ children: [tc('Date of Submission:', { bold: true, shade: true, width: 3000 }), tc('July 2026', { width: 6360 })] }),
      new TableRow({ children: [tc('Title of the Project:', { bold: true, shade: true, width: 3000 }), tc('OrchestrAI: Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines', { width: 6360 })] }),
      new TableRow({ children: [tc('Name of the Student:', { bold: true, shade: true, width: 3000 }), tc('Parthiv Patel', { width: 6360 })] }),
      new TableRow({ children: [tc('ID No.:', { bold: true, shade: true, width: 3000 }), tc('2024HT01163', { width: 6360 })] }),
      new TableRow({ children: [tc('Programme:', { bold: true, shade: true, width: 3000 }), tc('MTech. Computer Science (Data Science)', { width: 6360 })] }),
      new TableRow({ children: [tc('Supervisor:', { bold: true, shade: true, width: 3000 }), tc('Vinayak Bamane, Senior Data Engineering Lead', { width: 6360 })] }),
    ], [3000, 6360]),
    sp(160),
    pRuns([{ text: 'Key Words: ', bold: true }, { text: 'Multi-Agent AI, Self-Healing Pipelines, LangGraph, Isolation Forest, RandomForest, Anomaly Detection, Human-in-the-Loop, ChromaDB RAG, NL-to-SQL, FastAPI, Next.js, DuckDB, Groq LLM.' }]),
    sp(60),
    new Paragraph({
      children: [
        new TextRun({ text: 'Signature of Student:', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: '                                              ', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: 'Signature of Supervisor:', size: 22, font: 'Times New Roman' }),
      ], spacing: { after: 80 },
    }),
    new Paragraph({
      children: [
        new TextRun({ text: 'Name: Parthiv Patel', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: '                                                          ', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: 'Name: Vinayak Bamane', size: 22, font: 'Times New Roman' }),
      ], spacing: { after: 60 },
    }),
    new Paragraph({
      children: [
        new TextRun({ text: 'Date: July 2026', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: '                                                                   ', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: 'Date: July 2026', size: 22, font: 'Times New Roman' }),
      ], spacing: { after: 60 },
    }),
    new Paragraph({
      children: [
        new TextRun({ text: 'Place: Bengaluru', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: '                                                                    ', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: 'Place: Pune', size: 22, font: 'Times New Roman' }),
      ],
    }),
    pgBreak(),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// ABSTRACT
// ══════════════════════════════════════════════════════════════════════════════
function abstract() {
  // Abstract uses wider line spacing to fill the page
  function pAbs(text) {
    return new Paragraph({
      children: [new TextRun({ text, size: 24, font: 'Times New Roman', color: BLACK })],
      spacing: { after: 180, line: 360, lineRule: LineRuleType.AUTO },
      alignment: AlignmentType.JUSTIFIED,
    });
  }
  return [
    new Paragraph({ children: [new TextRun({ text: 'iii', size: 22, font: 'Times New Roman', color: GRAY })], alignment: AlignmentType.RIGHT, pageBreakBefore: true }),
    new Paragraph({ children: [new TextRun({ text: 'ABSTRACT', size: 28, bold: true, font: 'Times New Roman', color: NAVY })], alignment: AlignmentType.CENTER, spacing: { before: 0, after: 320 } }),
    pAbs('Production data pipelines fail silently — schema changes, late-arriving data, memory exhaustion — costing engineers an estimated 15–20% of sprint capacity on manual triage. Gartner (2023) estimates that data engineers spend 44% of sprint capacity on reactive triage, compounding as real-time streaming architectures expand failure blast radius from a single downstream report to hundreds of simultaneously corrupted ML model features. No existing open-source or commercial platform closes the complete loop from autonomous detection through root-cause diagnosis, fix generation, human approval, deployment, and outcome-driven learning — leaving organisations dependent on fragmented tool chains requiring significant human coordination at every incident boundary.'),
    pAbs('This dissertation presents OrchestrAI: an Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines, designed and built at Hevo Technologies India Pvt. Ltd., Bengaluru using a Design Science Research methodology. Six specialised AI agents are orchestrated in a LangGraph 0.4.8 StateGraph: (1) Monitoring Agent — two-tier ML pipeline (IsolationForest ROC-AUC=0.896; RandomForest 6-class F1=0.980) detecting anomalies across six telemetry dimensions; (2) Diagnosis Agent — Groq LLM (llama-3.3-70b-versatile) with ReAct root-cause reasoning; (3) Fix Writer Agent — ChromaDB 0.5.23 RAG retrieval + LLM-generated unified diff patches; (4) Approval Gate — real-time WebSocket UI enabling human review before any system change; (5) Deployment Agent — applies the approved fix and triggers pipeline re-run; (6) Learning Agent — embeds accepted repairs as vector embeddings in ChromaDB and records MTTR deltas, closing the feedback loop.'),
    pAbs('Three controlled experiments validate all pre-registered targets. Ablation Study (n=20): OrchestrAI achieves 134 s mean MTTR — 94.4% vs. the manual baseline (p<0.001, d=3.76) and 77.7% vs. the rule-based baseline (p=0.003). IsolationForest ROC-AUC=0.896, RandomForest F1=0.980, and NL-to-SQL 80% accuracy each surpass their targets; a 30-day learning curve shows a further 68.8% MTTR reduction.'),
    pRuns([{ text: 'Keywords: ', bold: true }, { text: 'Multi-Agent AI, Self-Healing Pipelines, LangGraph, IsolationForest, RandomForest, ChromaDB RAG, Human-in-the-Loop, NL-to-SQL, FastAPI, Next.js, Groq LLM, DuckDB, Design Science Research.' }]),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// TABLE OF CONTENTS — full single page with sub-sections + LoF + LoT
// ══════════════════════════════════════════════════════════════════════════════
function toc() {
  function chRow(num, title, page) {
    return new Paragraph({
      children: [
        new TextRun({ text: `${num}   ${title}`, size: 24, bold: true, font: 'Times New Roman', color: NAVY }),
        new TextRun({ text: '\t', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: String(page), size: 24, bold: true, font: 'Times New Roman', color: NAVY }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
      spacing: { before: 140, after: 50 },
    });
  }
  function secRow(num, title, page) {
    return new Paragraph({
      children: [
        new TextRun({ text: `        ${num}   ${title}`, size: 21, font: 'Times New Roman', color: BLACK }),
        new TextRun({ text: '\t', size: 21, font: 'Times New Roman' }),
        new TextRun({ text: String(page), size: 21, font: 'Times New Roman', color: BLACK }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
      spacing: { before: 0, after: 30 },
    });
  }
  function fmRow(title, page) {
    return new Paragraph({
      children: [
        new TextRun({ text: title, size: 22, font: 'Times New Roman', color: BLACK }),
        new TextRun({ text: '\t', size: 22, font: 'Times New Roman' }),
        new TextRun({ text: String(page), size: 22, font: 'Times New Roman', color: BLACK }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
      spacing: { before: 0, after: 50 },
    });
  }
  function listEntry(label, title, page) {
    return new Paragraph({
      children: [
        new TextRun({ text: `        ${label}: ${title}`, size: 20, italics: true, font: 'Times New Roman', color: GRAY }),
        new TextRun({ text: '\t', size: 20, font: 'Times New Roman' }),
        new TextRun({ text: String(page), size: 20, italics: true, font: 'Times New Roman', color: GRAY }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
      spacing: { before: 0, after: 28 },
    });
  }
  function listHead(title) {
    return new Paragraph({
      children: [new TextRun({ text: title, size: 22, bold: true, font: 'Times New Roman', color: BLUE2 })],
      spacing: { before: 100, after: 50 },
    });
  }

  return [
    new Paragraph({
      pageBreakBefore: true,
      children: [new TextRun({ text: 'TABLE OF CONTENTS', size: 28, bold: true, font: 'Times New Roman', color: NAVY })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 180 },
    }),

    fmRow('Acknowledgements', 'i'),
    fmRow('Abstract', 'iii'),
    sp(60),

    chRow('1', 'INTRODUCTION', 1),
    secRow('1.1', 'Background and Motivation', 1),
    secRow('1.2', 'Problem Statement', 2),
    secRow('1.3', 'Research Objectives', 2),
    secRow('1.4', 'Research Scope and Boundaries', 3),
    secRow('1.5', 'Design Science Research Framework', 3),

    chRow('2', 'LITERATURE SURVEY', 4),
    secRow('2.1', 'Foundational Works and Gap Analysis', 4),
    secRow('2.2', 'Comparative Analysis of Existing Platforms', 7),

    chRow('3', 'SYSTEM ARCHITECTURE', 8),
    secRow('3.1', 'Four-Tier System Architecture', 8),
    secRow('3.2', 'Six-Agent Orchestration', 10),
    secRow('3.3', 'Shared State Design and Conditional Routing', 11),

    chRow('4', 'IMPLEMENTATION DETAILS', 13),
    secRow('4.1', 'Technology Stack', 13),
    secRow('4.2', 'ML Detection Pipeline', 14),
    secRow('4.3', 'LangGraph Agent Implementation', 15),
    secRow('4.4', 'RAG-Based Institutional Learning', 16),
    secRow('4.5', 'Security Architecture and API Design', 17),
    secRow('4.6', 'Frontend Architecture', 18),

    chRow('5', 'RESULTS AND DISCUSSION', 19),
    secRow('5.1', 'Experimental Setup and Environment', 19),
    secRow('5.2', 'Self-Healing Effectiveness — Ablation Study', 20),
    secRow('5.3', 'ML Anomaly Detection Accuracy', 22),
    secRow('5.4', 'NL-to-SQL and Learning Agent Effectiveness', 23),
    secRow('5.5', 'Discussion and Interpretation', 24),

    chRow('6', 'CONCLUSION AND FUTURE SCOPE', 25),
    secRow('6.1', 'Key Contributions', 25),
    secRow('6.2', 'Threats to Validity', 26),
    secRow('6.3', 'Limitations', 27),
    secRow('6.4', 'Future Work', 27),

    sp(60),
    fmRow('References', 28),

    pgBreak(),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// CHAPTER 1: INTRODUCTION
// ══════════════════════════════════════════════════════════════════════════════
function chapter1() {
  return [
    h1('1. INTRODUCTION', false),

    p('Modern data engineering organisations process hundreds of pipeline stages continuously, each representing a potential failure point. Schema changes in source systems, unexpected data volume spikes, network partitioning, and resource exhaustion can silently corrupt downstream analytics without triggering any alert for minutes to hours. Research by Gartner (2023) estimates that data engineers spend 44% of sprint capacity on reactive triage — manually identifying, diagnosing, and patching pipeline failures rather than building new capability. At Hevo Technologies India Pvt. Ltd., Bengaluru — a SaaS company processing billions of pipeline events monthly for global enterprise customers — this operational overhead represents a critical bottleneck to both engineering productivity and service reliability guarantees.'),

    p('Existing tools address individual sub-problems in isolation: Monte Carlo provides ML-powered observability alerts, Great Expectations enforces schema contracts at ingestion time, Datafold catches data regressions in the code review lifecycle, and dbt Cloud orchestrates transformation job dependencies. None of them generates an executable code fix autonomously, none provides a human-in-the-loop approval workflow for high-risk repairs, and none learns from resolved incidents to accelerate the repair of future similar failures. The consequence is a fragmented operations stack that demands significant human coordination across disconnected tools for every incident. This dissertation presents OrchestrAI — an Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines — that closes the full reliability loop end-to-end for the first time.'),

    h2('1.1  Background and Motivation'),
    p('The data reliability problem has intensified with the proliferation of real-time streaming pipelines, multi-cloud architectures, and ML-serving infrastructure. Where a single nightly batch failure in 2015 might affect one downstream report, a 2026 streaming pipeline failure can corrupt hundreds of ML model features, invalidate real-time dashboards, and trigger cascading SLA violations within seconds. The Sculley et al. (2015) [1] analysis of hidden technical debt in ML systems established that 40% of production ML failures originate from upstream data pipeline issues — schema changes, distribution shifts, or data volume anomalies that propagate undetected.'),

    p('Hevo Technologies\' engineering team processes pipeline_run telemetry records containing six key metrics per run: row_count, byte_throughput, null_ratio, schema_hash, latency_ms, and error_rate. Anomalies in any of these dimensions can signal different failure root causes: a null_ratio spike may indicate a source schema change, while a zero row_count may indicate a connector authentication failure. Manual correlation of these signals with application logs and deployment history takes a trained engineer 30–45 minutes per incident. Multiplied across 50 weekly incidents at Hevo\'s production scale, this represents 1,500–2,250 minutes of senior engineering time per week consumed by reactive triage rather than proactive capability development.'),

    h2('1.2  Problem Statement'),
    p('OrchestrAI addresses three distinct and compounding failure modes in enterprise pipeline operations, each individually well-understood but never collectively solved in a single integrated platform:'),
    tblCap('Table 1: Three-dimensional gap in existing pipeline reliability tooling.'),
    tbl([
      new TableRow({ children: [tc('Dimension', { bold: true, shade: true, width: 2600 }), tc('Root Cause', { bold: true, shade: true, width: 3000 }), tc('Business Impact', { bold: true, shade: true, width: 3760 })] }),
      new TableRow({ children: [tc('Detection latency', { bold: true, width: 2600 }), tc('Periodic polling (5–30 min intervals) instead of event-driven ML scoring on each pipeline run record', { width: 3000 }), tc('Corrupted or incomplete data propagates downstream before any alert fires; SLA breaches discovered retroactively', { width: 3760 })] }),
      new TableRow({ children: [tc('Diagnosis complexity', { bold: true, width: 2600 }), tc('Root cause requires simultaneously correlating logs, metrics, schema snapshots, and deployment history across disconnected tools', { width: 3000 }), tc('30–45 min engineer investigation per incident; severe context-switching cost per on-call rotation; knowledge lost on handover', { width: 3760 })] }),
      new TableRow({ children: [tc('Remediation fragmentation', { bold: true, width: 2600 }), tc('Detection, fix authoring, change-approval, and deployment use separate, manually-operated workflows with no shared context', { width: 3000 }), tc('Mean time to repair (MTTR) measured at 2,378 s in the controlled manual baseline experiment; no institutional memory of resolved incidents', { width: 3760 })] }),
    ], [2600, 3000, 3760]),
    sp(140),

    h2('1.3  Research Objectives'),
    p('Six research objectives were established at project inception, each paired with a quantitative success criterion to ensure falsifiability and enable rigorous experimental validation against pre-registered targets:'),
    tblCap('Table 2: Six research objectives with measurable targets — all achieved.'),
    tbl([
      new TableRow({ children: [tc('ID', { bold: true, shade: true, width: 360 }), tc('Objective', { bold: true, shade: true, width: 2800 }), tc('Measurable Target', { bold: true, shade: true, width: 2800 }), tc('Achieved Result', { bold: true, shade: true, width: 3400 })] }),
      new TableRow({ children: [tc('O1', { width: 360, center: true }), tc('Multi-agent orchestration', { width: 2800 }), tc('6-agent LangGraph StateGraph with conditional routing', { width: 2800 }), tc('✓ All 6 agents live; graph serialisable and replayable', { width: 3400 })] }),
      new TableRow({ children: [tc('O2', { width: 360, center: true }), tc('End-to-end self-healing loop', { width: 2800 }), tc('Detect → diagnose → fix → approve → deploy → learn, fully automated', { width: 2800 }), tc('✓ MTTR 134 s (−94.4% vs. 2,378 s manual baseline)', { width: 3400 })] }),
      new TableRow({ children: [tc('O3', { width: 360, center: true }), tc('ML anomaly detection', { width: 2800 }), tc('IsoForest AUC ≥ 0.85; RandomForest F1 ≥ 0.90', { width: 2800 }), tc('✓ AUC=0.896; weighted F1=0.980; 4.1 ms inference', { width: 3400 })] }),
      new TableRow({ children: [tc('O4', { width: 360, center: true }), tc('RAG institutional learning', { width: 2800 }), tc('Measurable MTTR reduction over 30 days of operation', { width: 2800 }), tc('✓ −68.8% MTTR reduction (280 s → 87 s over 30 days)', { width: 3400 })] }),
      new TableRow({ children: [tc('O5', { width: 360, center: true }), tc('NL-to-SQL analytics interface', { width: 2800 }), tc('≥ 65% accuracy on a structured 30-question benchmark', { width: 2800 }), tc('✓ 80% overall (Easy 100%; Medium 80%; Hard 60%)', { width: 3400 })] }),
      new TableRow({ children: [tc('O6', { width: 360, center: true }), tc('Empirical evaluation via DSR', { width: 2800 }), tc('3 experiments with p<0.05 significance thresholds', { width: 2800 }), tc('✓ p<0.001 (ablation); Cohen\'s d=3.76 (very large effect)', { width: 3400 })] }),
    ], [360, 2800, 2800, 3400]),
    sp(140),

    h2('1.4  Research Scope and Boundaries'),
    p('OrchestrAI targets structured, tabular data pipelines typical of enterprise ETL workloads. The platform is validated on a DuckDB 0.10.3 embedded warehouse containing 4,120 synthetic pipeline run records spanning six anomaly types and a 90-day synthetic operational history. The system is explicitly scoped to: (a) pipelines with structured telemetry output covering at least the six defined feature dimensions; (b) deterministic fix categories amenable to unified-diff representation; and (c) deployment environments accessible via Python-executable scripts with filesystem write access. Streaming pipelines (Kafka consumers, Flink jobs), unstructured log-only anomaly detection without structured telemetry, and multi-cloud cross-account orchestration are acknowledged as out-of-scope and addressed as future work in §6.4.'),

    h2('1.5  Design Science Research Framework'),
    p('OrchestrAI is developed under the Design Science Research (DSR) methodology of Hevner et al. (2004) [10], which explicitly requires both an artifact contribution and a rigorous evaluation of that artifact against measurable criteria. The three-cycle DSR model applied here comprises: (1) the Relevance Cycle — grounding problem formulation in observed Hevo Technologies production failure patterns, on-call telemetry, and incident response logs; (2) the Design Cycle — iterative 8-sprint construction of the LangGraph agent graph, ML detection pipeline, ChromaDB RAG layer, FastAPI backend, and Next.js frontend; and (3) the Rigor Cycle — validating design choices against the IS research knowledge base including multi-agent systems literature, anomaly detection surveys, and retrieval-augmented generation research.'),

    p('The dissertation thus constitutes both a constructive artifact (85 Python backend files, 13 Next.js pages, 6 LangGraph agents, 79 pytest tests, 4,120-record DuckDB warehouse) and an evaluative contribution (three controlled experiments with statistical significance testing, JSON result files, and ablation study across three baseline configurations). The remainder of this dissertation is organised as follows: Chapter 2 surveys the six foundational literature streams and positions OrchestrAI against competing platforms; Chapter 3 describes the system architecture across its four tiers; Chapter 4 details the implementation of each major subsystem; Chapter 5 presents experimental results with statistical analysis; Chapter 6 concludes with contributions, validity threats, limitations, and future directions.'),

    p('The eight-sprint Design Cycle was structured around iterative feedback from the Hevo Technologies on-call engineering team. Sprint 1 established the DuckDB warehouse schema and seeding pipeline. Sprints 2–3 built the ML detection subsystem, with the contamination threshold and classifier hyperparameters tuned against a 20% held-out validation set. Sprints 4–5 constructed the LangGraph agent graph, ReAct diagnosis chain, and RAG fix retrieval layer. Sprint 6 implemented the FastAPI backend with JWT authentication, Fernet encryption, and rate limiting. Sprint 7 built the Next.js frontend dashboard, including the WebSocket approval interface and NL-to-SQL analyst panel. Sprint 8 conducted the formal ablation study, statistical analysis, and report preparation. At each sprint boundary, the system was evaluated against pre-registered acceptance criteria before proceeding — a practice consistent with the DSR Design Cycle\'s emphasis on iterative refinement against measurable design requirements.'),

    p('Research quality in DSR is assessed along three criteria advanced by Hevner et al. (2004): utility (the artifact must solve a real and significant problem), rigour (design and evaluation must draw on established knowledge base foundations), and novelty (the artifact must provide a contribution not achievable by existing tools). OrchestrAI satisfies all three: utility is demonstrated by the 94.4% MTTR reduction and $194,688/year productivity reclamation quantified in §5.2; rigour is established through statistical significance testing (p<0.001, Cohen\'s d=3.76) and grounding in the six literature streams reviewed in Chapter 2; and novelty is evidenced by OrchestrAI\'s unique integration of LangGraph orchestration, two-tier ML detection, and RAG institutional learning — a combination absent from all evaluated competing platforms (Table 3).'),
    pgBreak(),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// CHAPTER 2: LITERATURE SURVEY
// ══════════════════════════════════════════════════════════════════════════════
function chapter2() {
  return [
    h1('2. LITERATURE SURVEY', true),

    p('This chapter reviews the six primary literature streams that directly informed OrchestrAI\'s design, conducts a per-work gap analysis explaining precisely what each contribution does not address, and positions the platform within the competitive landscape of data reliability tooling through a systematic capability comparison.'),

    h2('2.1  Foundational Works and Gap Analysis'),

    h3('2.1.1  Hidden Technical Debt in Machine Learning Systems'),
    p('Sculley et al. (2015) [1] demonstrated that ML systems in production accrue hidden technical debt through undeclared data dependencies, unstable input distributions, and implicit feedback loops that degrade model quality silently over time. Their Changing Anything Changes Everything (CACE) principle establishes that any upstream schema change can corrupt a downstream ML-powered pipeline without surfacing an explicit error — the pipeline continues to execute on malformed input, producing outputs that are statistically wrong but syntactically valid. This work directly motivated OrchestrAI\'s schema drift detection capability: the MonitoringAgent\'s six-dimensional feature vector includes schema_hash (a categorical integer capturing the schema fingerprint), null_ratio, and byte_throughput, which together capture precisely the input-distribution shifts Sculley et al. identify as the primary debt accumulation mechanism. The critical gap in Sculley et al.\'s work is remediation: they diagnose the problem class with rigour but propose no automated fix generation, no orchestration mechanism for routing anomalies to appropriate repair strategies, and no institutional memory system for accelerating future repairs.'),

    h3('2.1.2  Software Engineering for Machine Learning'),
    p('Amershi et al. (2019) [2] conducted a systematic study of ML engineering practices at Microsoft across 515 engineers, finding that teams with structured monitoring infrastructure report 2.3× lower mean time to detect (MTTD) and measurably reduced MTTR compared to teams relying on ad-hoc alerting. Their nine SE4ML challenges — data validation, feature management, model deployment, and monitoring — correspond directly to OrchestrAI\'s six agent responsibilities. OrchestrAI addresses all nine challenges in an integrated platform rather than treating each as a separate toolchain concern requiring human coordination. The gap in Amershi et al.\'s work is actionability: they document the problem landscape rigorously and provide engineering guidelines, but do not propose an architectural pattern for autonomously closing the detect-to-repair loop without human initiation of each remediation step.'),

    h3('2.1.3  LangGraph Multi-Agent Framework'),
    p('LangChain AI (2024) [3] introduced LangGraph as a directed-graph orchestration library for stateful multi-agent LLM applications. Its three key contributions are: (a) the StateGraph abstraction, which routes execution through typed nodes sharing a flat serialisable TypedDict state, enabling exactly the pipeline healing state machine required by OrchestrAI; (b) conditional edges, enabling branching logic based on computed state values such as the confidence_score threshold that determines whether the Approval Gate is inserted; and (c) structured human interruption, pausing graph execution at designated checkpoints for synchronous human review — the exact mechanism OrchestrAI uses for the ApprovalGateAgent. LangGraph provides routing infrastructure and state management primitives, but does not address domain-specific agent logic: the ML anomaly detectors, ReAct prompt strategies, RAG retrieval pipelines, and deployment validation suites are OrchestrAI\'s domain contributions that operate on top of LangGraph\'s orchestration layer.'),

    h3('2.1.4  Retrieval-Augmented Generation (RAG)'),
    p('Lewis et al. (2020) [4] established retrieval-augmented generation as the dominant paradigm for knowledge-intensive NLP tasks: a dense retrieval step fetches relevant documents from an external vector store, and those documents are prepended to the LLM prompt as few-shot context. Their experiments demonstrated that RAG substantially outperforms closed-book LLM generation on factual tasks requiring domain-specific knowledge not present in training data, because the retrieval step grounds the model\'s output in verified external evidence. OrchestrAI applies this pattern to fix generation: the FixWriterAgent embeds the current incident diagnosis and retrieves the top-3 most semantically similar historical fixes from ChromaDB, converting incident-resolution history into a continuously growing knowledge asset. Lewis et al.\'s original work targets open-domain question answering; OrchestrAI\'s novel contribution is the application of RAG to structured software repair, where "documents" are accepted unified diffs indexed by anomaly type and diagnosis text rather than natural language passages.'),

    h3('2.1.5  Anomaly Detection: A Survey'),
    p('Chandola et al. (2009) [5] provide the definitive taxonomy of anomaly detection approaches across statistical, proximity-based, classification-based, and reconstruction-based families. Their analysis directly justifies the two-tier ML architecture chosen for OrchestrAI\'s MonitoringAgent. IsolationForest is chosen for the binary detection tier because it is computationally efficient (O(n log n) training), requires no anomaly labels at training time (critical when labelled pipeline failure data is scarce in early deployment), and performs well in high-dimensional feature spaces by isolating anomalies through random partitioning. RandomForest is chosen for the six-class supervised tier because Chandola et al.\'s classification-based analysis identifies ensemble methods as the most robust approach for multi-class anomaly type discrimination, and because RandomForest handles class imbalance through class_weight=\'balanced\'. The survey provides the theoretical justification for the two-tier design but does not address the integration of anomaly detection into an agentic repair workflow — OrchestrAI\'s primary architectural contribution.'),

    h3('2.1.6  ReAct: Synergizing Reasoning and Acting'),
    p('Yao et al. (2023) [6] introduced ReAct as a prompting strategy that interleaves Thought, Action, and Observation traces in the LLM\'s generated output. ReAct agents consistently outperform chain-of-thought prompting alone on tasks requiring external tool use, because the explicit reasoning trace allows the model to self-correct based on observed tool outputs before committing to a final answer. OrchestrAI\'s DiagnosisAgent implements ReAct with Groq\'s llama-3.3-70b-versatile (128k context window): the Thought step articulates a diagnostic hypothesis based on the six telemetry features, the Action step queries the log context or schema history, and the Observation step incorporates the query result before committing to a final root-cause diagnosis and confidence score. This produces auditable, interpretable diagnoses rather than opaque LLM outputs — a requirement for human operators reviewing high-risk repair approvals via the WebSocket diff interface. The ReAct paper does not address the integration of reasoning chains into multi-agent orchestration graphs or the use of confidence scores for conditional workflow routing.'),

    sp(80),
    h2('2.2  Comparative Analysis of Existing Platforms'),
    p('The competitive analysis below evaluates OrchestrAI against the four most widely deployed data reliability platforms across eleven capability dimensions critical to autonomous pipeline healing. Each dimension corresponds directly to one of the three root causes identified in Table 1 or one of the six research objectives in Table 2. OrchestrAI is the only platform that achieves all eleven capabilities and the only one that combines ML-driven detection, LLM-driven diagnosis and repair, and RAG institutional learning in a single open-source, self-hostable system.'),
    tblCap('Table 3: Feature comparison — OrchestrAI vs. existing platforms. (✓ = full, ◑ = partial, ✗ = none.)'),
    tbl([
      new TableRow({ children: [tc('Capability', { bold: true, shade: true, width: 2800 }), tc('OrchestrAI', { bold: true, shade: true, width: 1312, center: true }), tc('Monte Carlo', { bold: true, shade: true, width: 1312, center: true }), tc('Great Expect.', { bold: true, shade: true, width: 1312, center: true }), tc('Datafold', { bold: true, shade: true, width: 1312, center: true }), tc('dbt Cloud', { bold: true, shade: true, width: 1312, center: true })] }),
      ...([
        ['ML anomaly detection',             '✓','✓','◑','◑','✗'],
        ['Six-class anomaly classification',  '✓','✗','✗','✗','✗'],
        ['Autonomous LLM fix generation',     '✓','✗','✗','✗','✗'],
        ['Sandboxed 12-check validation',     '✓','✗','✗','✗','✗'],
        ['Human-in-the-loop approval UI',     '✓','◑','✗','✗','✗'],
        ['RAG institutional learning',        '✓','✗','✗','✗','✗'],
        ['MTTR tracking + outcome learning',  '✓','✓','✗','◑','✗'],
        ['NL-to-SQL analytics',               '✓','✗','✗','✗','◑'],
        ['Data lineage visualisation',        '✓','✓','✗','✓','◑'],
        ['Schema drift detection',            '✓','✓','✓','✓','◑'],
        ['Open-source / self-hostable',       '✓','✗','✓','✗','✗'],
      ].map(([cap, ...vals]) => new TableRow({ children: [tc(cap, { width: 2800 }), ...vals.map(v => tc(v, { width: 1312, center: true }))] }))),
    ], [2800, 1312, 1312, 1312, 1312, 1312]),
    sp(100),
    p('Monte Carlo comes closest on observability coverage — it provides ML-based anomaly detection and MTTR tracking — but lacks autonomous LLM fix generation, sandboxed validation, and RAG institutional learning. Great Expectations provides the strongest schema validation guarantees but has no healing capability and no MTTR analytics. Datafold catches data regressions at the code review stage, making it a development-time tool rather than a production reliability platform. dbt Cloud orchestrates transformation dependencies but does not detect runtime anomalies or generate fixes. OrchestrAI\'s unique value proposition is the complete integration of all eleven capabilities in a single system, eliminating the human coordination overhead required when these capabilities are spread across disconnected tools. The open-source, self-hostable nature is also significant for data-sensitive enterprises that cannot route production telemetry to third-party SaaS vendors.'),

    p('On operational cost, Monte Carlo and Datafold operate as managed SaaS with per-connector pricing that escalates rapidly at enterprise scale. OrchestrAI imposes only infrastructure cost: DuckDB requires no separate database server and the Groq API is billed per token with no subscription floor. For 50–100 pipelines, total monthly inference cost is estimated at $18–$45 — versus Monte Carlo enterprise contracts that typically exceed $60,000 annually, making OrchestrAI viable for mid-market teams without enterprise licensing commitments.'),

    p('A further differentiator is explainability: only OrchestrAI provides a fully traceable audit chain from raw telemetry through the ReAct reasoning trace to the generated diff, essential for regulated industries where autonomous infrastructure changes require auditable human oversight.'),
  ];
}

module.exports = { coverPages, acknowledgements, projectDetails, abstract, toc, chapter1, chapter2, fig,
  // export helpers for parts 2 and 3
  p, pRuns, h1, h2, h3, sp, pgBreak, centred, bullet, codeBlock, figCap, tblCap, tc, tbl,
  NAVY, BLACK, GRAY, BLUE2, LGRAY, LineRuleType, AlignmentType,
  Paragraph, TextRun, HeadingLevel, PageBreak, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, LevelFormat,
};
