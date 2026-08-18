// ═══════════════════════════════════════════════════════════════════════════
// OrchestrAI Final Dissertation Report — Master Builder
// ═══════════════════════════════════════════════════════════════════════════
'use strict';

const fs = require('fs');

const {
  Document, Packer, LevelFormat, AlignmentType,
  Header, Footer, PageNumber, Paragraph, TextRun,
  TabStopType, BorderStyle,
} = require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/node_modules/docx');

const { coverPages, acknowledgements, projectDetails, abstract, toc, chapter1, chapter2 } =
  require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/report_part1');
const { chapter3, chapter4 } =
  require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/report_part2');
const { chapter5, chapter6, references } =
  require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/report_part3');

const NAVY  = '003366';
const BLACK = '000000';
const BLUE2 = '1A3A5C';
const DARK  = '1A1A2E';
const GRAY  = '595959';
const LGRAY = 'AAAAAA';

// ── Header / footer factory functions ────────────────────────────────────────
// Body pages: left title | right ID  (with bottom border line)
function mkBodyHeader() {
  return new Header({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: 'OrchestrAI — Final Dissertation Report',
            italics: true, size: 18, font: 'Times New Roman', color: GRAY,
          }),
          new TextRun({ text: '\t', size: 18 }),
          new TextRun({
            text: '2024AA05129  |  BITS ZG628T',
            size: 18, font: 'Times New Roman', color: GRAY,
          }),
        ],
        tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 6, color: LGRAY, space: 4 },
        },
        spacing: { after: 40 },
      }),
    ],
  });
}

// Cover page: centred italic title line  (with bottom border line)
function mkCoverHeader() {
  return new Header({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: 'OrchestrAI — Final Dissertation Report  |  Parthiv Patel  |  2024AA05129',
            italics: true, size: 18, font: 'Times New Roman', color: GRAY,
          }),
        ],
        alignment: AlignmentType.CENTER,
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 6, color: LGRAY, space: 4 },
        },
        spacing: { after: 40 },
      }),
    ],
  });
}

// Body pages: left course label | right page number  (with top border line)
function mkBodyFooter() {
  return new Footer({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: 'BITS Pilani  |  AIMLCZG628T: Dissertation',
            size: 18, font: 'Times New Roman', color: GRAY,
          }),
          new TextRun({ text: '\t', size: 18 }),
          new TextRun({
            children: ['Page ', PageNumber.CURRENT],
            size: 18, font: 'Times New Roman', color: GRAY,
          }),
        ],
        tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
        border: {
          top: { style: BorderStyle.SINGLE, size: 6, color: LGRAY, space: 4 },
        },
        spacing: { before: 60 },
      }),
    ],
  });
}

// Cover page: centred page number only (no border)
function mkCoverFooter() {
  return new Footer({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            children: ['Page ', PageNumber.CURRENT],
            size: 18, font: 'Times New Roman', color: GRAY,
          }),
        ],
        alignment: AlignmentType.CENTER,
      }),
    ],
  });
}

// ── Document ─────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullet-list',
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: '•',
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: { indent: { left: 720, hanging: 360 } },
            run: { font: 'Symbol', size: 24 },
          },
        }],
      },
      {
        reference: 'num-list',
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: '%1.',
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: { indent: { left: 720, hanging: 360 } },
            run: { size: 24, font: 'Times New Roman' },
          },
        }],
      },
    ],
  },
  styles: {
    paragraphStyles: [
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        run: { size: 30, bold: true, font: 'Times New Roman', color: NAVY },
        paragraph: { spacing: { before: 240, after: 140 } },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        run: { size: 26, bold: true, font: 'Times New Roman', color: BLUE2 },
        paragraph: { spacing: { before: 200, after: 100 } },
      },
      {
        id: 'Heading3',
        name: 'Heading 3',
        basedOn: 'Normal',
        next: 'Normal',
        run: { size: 24, bold: true, font: 'Times New Roman', color: DARK },
        paragraph: { spacing: { before: 140, after: 60 } },
      },
    ],
  },
  sections: [{
    properties: {
      titlePage: true,               // enables first-page header/footer
      page: {
        size: { width: 12240, height: 15840 },   // US Letter
        margin: { top: 1440, bottom: 1440, left: 1800, right: 1440 },
      },
    },
    headers: {
      default: mkBodyHeader(),       // all body pages
      first: mkCoverHeader(),        // cover page only
    },
    footers: {
      default: mkBodyFooter(),       // all body pages
      first: mkCoverFooter(),        // cover page only
    },
    children: [
      ...coverPages(),
      ...acknowledgements(),
      ...projectDetails(),
      ...abstract(),
      ...toc(),
      ...chapter1(),
      ...chapter2(),
      ...chapter3(),
      ...chapter4(),
      ...chapter5(),
      ...chapter6(),
      ...references(),
    ],
  }],
});

const OUT = '/sessions/friendly-fervent-cray/mnt/OrchetraAI/OrchestrAI_Final_Report_ParthivPatel.docx';

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  const kb = Math.round(buf.length / 1024);
  console.log(`✅  Report written: ${OUT}`);
  console.log(`    Size: ${kb} KB`);
}).catch(err => {
  console.error('❌  Build failed:', err.message);
  process.exit(1);
});
