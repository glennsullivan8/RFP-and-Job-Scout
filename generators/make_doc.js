// generators/make_doc.js
// Generates professional Word documents (.docx) for RFP proposals and job applications.
// Usage: node make_doc.js <type> <data_json_path> <output_path>
// type: "rfp" or "job"

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, LevelFormat, ExternalHyperlink, PageBreak,
} = require("docx");
const fs = require("fs");

const TEAL   = "0F6E56";
const TEAL_L = "E1F5EE";
const BLUE   = "185FA5";
const BLUE_L = "E6F1FB";
const GRAY   = "F5F5F3";
const BLACK  = "111111";
const WHITE  = "FFFFFF";

const PROFILE = {
  name:    "Glenn Sullivan, GISP",
  company: "Niche Management LLC",
  email:   "glenn.sullivan8@gmail.com",
  phone:   "1 (248) 494-3642",
  website: "https://nichemanagementllc.com",
  linkedin:"https://www.linkedin.com/in/glenn-sullivan-gisp-22574013a/",
  location:"Salem, VA 24153",
  creds: [
    "GISP – GIS Professional Certification #161655 (2023)",
    "FAA 14 CFR Part 107 Remote Pilot License",
    "ESRI Technical Certifications: ArcGIS Pro, Online Admin, API for Python, Developer Foundation",
    "ICS 100b / 200b / 700a / 800b (Emergency Operations)",
    "B.A. Environmental Science – University of Michigan (2015)",
  ],
  awards: [
    "2024 USDA Secretary's Honor Award",
    "2023 USFS Chief's Honor Award",
    "USDA Certificate of Appreciation (2023)",
  ],
  caps: [
    "Remote sensing analysis: satellite, LiDAR, drone, multispectral imagery",
    "Object detection, classification, tracking & pixel segmentation (GeoAI)",
    "Python, ArcPy, FME automation & geospatial data pipelines",
    "ArcGIS Online/Enterprise web app development (JS SDK, React, Experience Builder)",
    "FAA Part 107 drone operations: aerial survey, photogrammetry, Drone2Map",
    "EPA emergency response GIS: Camp Fire, Thomas Fire, Husky Refinery",
    "13+ years federal experience: NASA, USFS, EPA, FEMA, NOAA, USGS",
  ],
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const border = (color = "CCCCCC") => ({ style: BorderStyle.SINGLE, size: 4, color });
const noBorder = () => ({ style: BorderStyle.NONE, size: 0, color: "FFFFFF" });
const allBorders = (color) => ({ top: border(color), bottom: border(color), left: border(color), right: border(color) });
const noBorders = () => ({ top: noBorder(), bottom: noBorder(), left: noBorder(), right: noBorder() });

function hr(color = "DDDDDD") {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color } },
    spacing: { before: 80, after: 80 },
    children: [],
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 280, after: 100 },
    children: [new TextRun({ text, bold: true, size: 28, color: TEAL, font: "Arial" })],
  });
}

function heading2(text) {
  return new Paragraph({
    spacing: { before: 220, after: 80 },
    children: [new TextRun({ text, bold: true, size: 24, color: BLUE, font: "Arial" })],
  });
}

function body(text, options = {}) {
  return new Paragraph({
    spacing: { before: 60, after: 60, line: 276 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: BLACK, ...options })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { before: 40, after: 40, line: 276 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: BLACK })],
  });
}

function spacer(before = 120) {
  return new Paragraph({ spacing: { before, after: 0 }, children: [] });
}

function labelValue(label, value) {
  return new Paragraph({
    spacing: { before: 40, after: 40 },
    children: [
      new TextRun({ text: `${label}: `, bold: true, size: 22, font: "Arial", color: BLACK }),
      new TextRun({ text: value, size: 22, font: "Arial", color: BLACK }),
    ],
  });
}

// ── Header bar table ───────────────────────────────────────────────────────────

function makeHeaderTable(titleLine, subtitleLine) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({ children: [
        new TableCell({
          width: { size: 9360, type: WidthType.DXA },
          shading: { fill: TEAL, type: ShadingType.CLEAR },
          borders: noBorders(),
          margins: { top: 200, bottom: 200, left: 300, right: 300 },
          children: [
            new Paragraph({ children: [new TextRun({ text: titleLine, bold: true, size: 36, font: "Arial", color: WHITE })] }),
            new Paragraph({ spacing: { before: 60 }, children: [new TextRun({ text: subtitleLine, size: 22, font: "Arial", color: "C8EDD9" })] }),
          ],
        }),
      ]}),
    ],
  });
}

// ── Info bar table (org, date, deadline) ──────────────────────────────────────

function makeInfoTable(rows) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2600, 6760],
    rows: rows.map(([label, val]) => new TableRow({ children: [
      new TableCell({
        width: { size: 2600, type: WidthType.DXA },
        shading: { fill: GRAY, type: ShadingType.CLEAR },
        borders: allBorders("E0E0E0"),
        margins: { top: 80, bottom: 80, left: 120, right: 80 },
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 20, font: "Arial", color: "555555" })] })],
      }),
      new TableCell({
        width: { size: 6760, type: WidthType.DXA },
        borders: allBorders("E0E0E0"),
        margins: { top: 80, bottom: 80, left: 120, right: 80 },
        children: [new Paragraph({ children: [new TextRun({ text: val || "—", size: 20, font: "Arial", color: BLACK })] })],
      }),
    ]})),
  });
}

// ── Footer ─────────────────────────────────────────────────────────────────────

function makeFooter() {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: `${PROFILE.name}  ·  ${PROFILE.company}  ·  ${PROFILE.email}  ·  ${PROFILE.phone}`, size: 18, font: "Arial", color: "888888" }),
    ],
  });
}

// ── RFP PROPOSAL ──────────────────────────────────────────────────────────────

function buildRfpDoc(data) {
  const { rfp, draft } = data;

  const sections_content = [
    makeHeaderTable(
      "Technical Proposal",
      `${rfp.title || "Contract Opportunity"}`
    ),
    spacer(200),

    // Opportunity details
    makeInfoTable([
      ["Soliciting Agency", rfp.org || ""],
      ["Source / Portal",   rfp.source || ""],
      ["Posted Date",       rfp.posted || ""],
      ["Deadline",          rfp.deadline || ""],
      ["Set-Aside",         rfp.set_aside || "Small Business"],
      ["NAICS Code",        rfp.naics || ""],
      ["Opportunity URL",   rfp.url || ""],
    ]),
    spacer(200),

    heading1("Submitted By"),
    makeInfoTable([
      ["Company",       PROFILE.company],
      ["Contact",       PROFILE.name],
      ["Email",         PROFILE.email],
      ["Phone",         PROFILE.phone],
      ["Website",       PROFILE.website],
      ["Location",      PROFILE.location],
      ["Certifications","GISP #161655 | FAA Part 107 | ESRI Technical (6 certs)"],
      ["GISP Number",   "161655"],
    ]),
    spacer(200),

    heading1("Executive Summary"),
    hr(TEAL),
    ...(draft.executive_summary || ["Niche Management LLC is uniquely positioned to deliver exceptional results for this opportunity."]).map(p => body(p)),
    spacer(120),

    heading1("Technical Approach"),
    hr(TEAL),
    ...(draft.technical_approach || []).map(item => bullet(item)),
    spacer(120),

    heading1("Relevant Experience"),
    hr(TEAL),
    ...(draft.relevant_experience || []).map(p => body(p)),
    spacer(120),

    heading1("Key Personnel"),
    hr(TEAL),
    makeInfoTable([
      ["Name",           PROFILE.name],
      ["Role",           "Principal Investigator / Lead Consultant"],
      ["Experience",     "13+ years GIS, Remote Sensing, Python, FME, LiDAR"],
      ["Certifications", "GISP, FAA Part 107, ESRI Technical (6), ICS 100–800"],
      ["Awards",         "2024 USDA Secretary's Honor Award, 2023 USFS Chief's Honor Award"],
      ["Education",      "B.A. Environmental Science – University of Michigan (2015)"],
    ]),
    spacer(120),

    heading1("Core Capabilities"),
    hr(TEAL),
    ...PROFILE.caps.map(c => bullet(c)),
    spacer(120),

    heading1("Why Niche Management LLC"),
    hr(TEAL),
    ...(draft.why_us || ["Glenn Sullivan's award-winning federal project history and rare combination of GIS, remote sensing, and drone expertise make Niche Management LLC uniquely qualified to deliver high-quality, on-time results for this opportunity."]).map(p => body(p)),

    spacer(200),
    hr("CCCCCC"),
    spacer(80),
    makeFooter(),
  ];

  return new Document({
    numbering: {
      config: [{ reference: "bullets", levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }]}],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
        },
      },
      footers: { default: { options: { page: new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 18, color: "888888" })] }) } } },
      children: sections_content,
    }],
  });
}

// ── JOB APPLICATION ───────────────────────────────────────────────────────────

function buildJobDoc(data) {
  const { job, draft } = data;

  const children = [
    makeHeaderTable(
      "Job Application",
      `${job.title || "Position"} — ${job.org || ""}`
    ),
    spacer(200),

    makeInfoTable([
      ["Position",    job.title || ""],
      ["Organization",job.org || ""],
      ["Location",    job.location || ""],
      ["Salary",      job.salary || ""],
      ["Job Type",    job.job_type || ""],
      ["Source",      job.source || ""],
      ["URL",         job.url || ""],
    ]),
    spacer(280),

    // ── COVER LETTER ──────────────────────────────────────────────────────────
    heading1("Cover Letter"),
    hr(TEAL),
    body(`${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}`),
    spacer(120),
    body("Hiring Team,"),
    spacer(80),
    ...(draft.cover_letter || ["Thank you for considering my application."]).map(p => body(p)),
    spacer(120),
    body("Sincerely,"),
    spacer(80),
    body(PROFILE.name, { bold: true }),
    body(PROFILE.company),
    body(PROFILE.email),
    body(PROFILE.phone),
    body(PROFILE.linkedin),
    spacer(200),

    // ── RESUME SUMMARY ────────────────────────────────────────────────────────
    new Paragraph({ children: [new PageBreak()] }),
    makeHeaderTable("Resume", PROFILE.name),
    spacer(160),

    makeInfoTable([
      ["Email",    PROFILE.email],
      ["Phone",    PROFILE.phone],
      ["Location", PROFILE.location],
      ["LinkedIn", PROFILE.linkedin],
      ["Website",  PROFILE.website],
    ]),
    spacer(200),

    heading1("Professional Summary"),
    hr(TEAL),
    body(draft.resume_summary || `Award-winning GIS and Remote Sensing consultant with 13+ years of federal project experience. GISP certified, FAA Part 107 licensed, and recipient of the 2024 USDA Secretary's Honor Award. Expertise in satellite/LiDAR remote sensing, GeoAI, Python/ArcPy automation, and ArcGIS platform development.`),
    spacer(160),

    heading1("Credentials"),
    hr(TEAL),
    ...PROFILE.creds.map(c => bullet(c)),
    spacer(80),
    ...PROFILE.awards.map(a => bullet(a)),
    spacer(160),

    heading1("Core Capabilities"),
    hr(TEAL),
    ...PROFILE.caps.map(c => bullet(c)),
    spacer(160),

    heading1("Key Experience Highlights"),
    hr(TEAL),
    heading2("Locana / US Forest Service (2021–Present) — Lead GIS Developer"),
    bullet("Lead developer for USFS Climate Risk Viewer: 11 StoryMaps, 10 Experience Builders, 10 Web Maps, 140+ data layers — earned Secretary's Honor Award"),
    bullet("Built Wilderness Evaluation Tool with ArcGIS API for Python automated cloning pipeline"),
    bullet("NDVI analysis from Landsat data; LiDAR water identification using PDAL"),
    spacer(80),
    heading2("Michigan Tech Research Institute / NASA (2014–2016) — GIS Developer"),
    bullet("NASA Food Security Project: Python/Twilio SMS app for Sub-Saharan Africa farmers using NOAA satellite data"),
    bullet("NASA Harmful Algae Bloom Mapping: MODIS Aqua satellite imagery, LiDAR flyover data analysis for Lake Erie"),
    bullet("Drone-based DEM spall detection algorithm for Michigan DOT bridge inspection"),
    spacer(80),
    heading2("Tetra Tech / EPA (2017–2019) — Environmental Scientist & GIS Analyst"),
    bullet("Camp Fire (Paradise CA): GIS lead for largest California wildfire cleanup — 18,000 structures"),
    bullet("VIPER live air monitoring system deployment and web map integration"),
    bullet("EPA Superfund START contract: GIS, database management, field sampling, emergency response"),
    spacer(200),

    hr("CCCCCC"),
    spacer(80),
    makeFooter(),
  ];

  return new Document({
    numbering: {
      config: [{ reference: "bullets", levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }]}],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
        },
      },
      children,
    }],
  });
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function main() {
  const [,, docType, dataPath, outputPath] = process.argv;
  if (!docType || !dataPath || !outputPath) {
    console.error("Usage: node make_doc.js <rfp|job> <data.json> <output.docx>");
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  let doc;

  if (docType === "rfp") {
    doc = buildRfpDoc(data);
  } else if (docType === "job") {
    doc = buildJobDoc(data);
  } else {
    console.error(`Unknown type: ${docType}. Use 'rfp' or 'job'.`);
    process.exit(1);
  }

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log(`Created: ${outputPath}`);
}

main().catch(e => { console.error(e); process.exit(1); });
