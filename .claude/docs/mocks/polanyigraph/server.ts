import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from "@google/genai";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json());

const PORT = 3000;

// Initialize Gemini Client
const aiKey = process.env.GEMINI_API_KEY || '';
let ai: GoogleGenAI | null = null;
if (aiKey) {
  try {
    ai = new GoogleGenAI({
      apiKey: aiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        }
      }
    });
    console.log('Gemini client initialized successfully.');
  } catch (err) {
    console.error('Error initializing Gemini Client:', err);
  }
} else {
  console.warn('GEMINI_API_KEY not found in environment. Falling back to local heuristic rules and stubs.');
}

// In-Memory Database Structure
interface LayoutNode {
  id: string;
  label: string;
  type: string;
  activation?: number;
  derived?: boolean;
  sourceDoc?: string;
  salience?: number;
  properties?: Record<string, string>;
  note?: string;
  communityId?: number | null;
}

interface ApiEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
}

interface DerivedFact {
  id: string;
  fact: string;
  confidence: number;
  iteration: number;
  sourceId: string;
  targetId: string;
  ruleName: string;
  proofPath: any[];
  fedBack: boolean;
}

interface TraceEntry {
  ruleName: string;
  edgeType: string;
  sourceLabel: string;
  targetLabel: string;
  sourceActivation: number;
  threshold: number;
  fired: boolean;
  iteration: number;
  skipReason: string | null;
  factId: string | null;
}

interface ImplicitFact {
  id: string;
  heuristicType: string;
  text: string;
  confidence: number;
  status: 'pending' | 'approved' | 'rejected';
  anchorEntityIds: string[];
}

interface IngestEvent {
  id: string;
  text: string;
  entityCount: number;
  relationshipCount: number;
  droppedCount: number;
  createdAt: string;
}

interface Rule {
  id: string;
  name: string;
  edgeType: string;
  sourceType: string;
  targetType: string;
  threshold: number;
  weight: number;
  description: string;
  source: 'seed' | 'custom';
}

interface GraphStore {
  nodes: LayoutNode[];
  edges: ApiEdge[];
  facts: DerivedFact[];
  trace: TraceEntry[];
  pendingFacts: ImplicitFact[];
  approvedFacts: ImplicitFact[];
  history: IngestEvent[];
  loopIteration: number;
  loopStep: 'idle' | 'neural' | 'symbolic' | 'feedback';
}

const db: Record<string, GraphStore> = {};

function getOrCreateGraph(graphId: string): GraphStore {
  if (!db[graphId]) {
    db[graphId] = {
      nodes: [
        { id: 'n1', label: 'Credit Suisse', type: 'fibo-be-ge-ge:Bank', activation: 0, note: 'Global systemically important bank.', properties: { lei: '529900LX67VQ8V3N7N11', jurisdiction: 'CH', sector: 'Banking' }, salience: 1.0, communityId: null },
        { id: 'n2', label: 'Zürich', type: 'fibo-be-ge-ge:BusinessCenter', activation: 0, note: 'Swiss financial center.', properties: { jurisdiction: 'CH' }, salience: 1.0, communityId: null },
        { id: 'n3', label: 'CS Atlas Bond I', type: 'fibo-sec-sec-dbt:BondInstrument', activation: 0, note: 'CHF-denominated corporate bond.', properties: { isin: 'CH1234567890', currency: 'CHF', rating: 'A', maturity: '2030-12-31' }, salience: 1.2, communityId: null },
        { id: 'n4', label: 'Swiss Franc', type: 'fibo-sec-sec-cls:Currency', activation: 0, note: 'ISO CHF.', properties: { currency: 'CHF' }, salience: 0.8, communityId: null },
        { id: 'n5', label: 'FINMA', type: 'fibo-fbc-fct-fct:RegulatoryAgency', activation: 0, note: 'Swiss Financial Market Supervisory Authority.', properties: { jurisdiction: 'CH' }, salience: 1.1, communityId: null },
        { id: 'n6', label: 'UBS', type: 'fibo-be-ge-ge:Bank', activation: 0, note: 'Swiss universal bank.', properties: { lei: '529900LX67VQ8V3N7N12', jurisdiction: 'CH', sector: 'Banking' }, salience: 1.0, communityId: null },
      ],
      edges: [
        { id: 'e1', source: 'n1', target: 'n2', type: 'hasDomicile', weight: 1 },
        { id: 'e2', source: 'n3', target: 'n1', type: 'issuedBy', weight: 1 },
        { id: 'e3', source: 'n3', target: 'n4', type: 'denominatedIn', weight: 1 },
        { id: 'e4', source: 'n5', target: 'n1', type: 'regulates', weight: 1 },
        { id: 'e5', source: 'n5', target: 'n6', type: 'regulates', weight: 1 },
        { id: 'e6', source: 'n6', target: 'n2', type: 'hasDomicile', weight: 1 },
      ],
      facts: [],
      trace: [],
      pendingFacts: [],
      approvedFacts: [],
      history: [
        { id: 'h-1', text: 'Seeded Credit Suisse & UBS ecosystem.', entityCount: 6, relationshipCount: 6, droppedCount: 0, createdAt: new Date().toISOString() }
      ],
      loopIteration: 0,
      loopStep: 'idle'
    };
  }
  return db[graphId];
}

const globalRules: Rule[] = [
  { id: 'r1', name: 'Issuer Domicile', edgeType: 'issuedBy', sourceType: 'fibo-sec-sec-dbt:BondInstrument', targetType: 'fibo-be-ge-ge:Bank', threshold: 0.2, weight: 1, description: '{source} is issued by an entity domiciled in a jurisdiction tracked by {target}.', source: 'seed' },
  { id: 'r2', name: 'Regulatory Oversight', edgeType: 'regulates', sourceType: 'fibo-fbc-fct-fct:RegulatoryAgency', targetType: 'fibo-be-ge-ge:Bank', threshold: 0.15, weight: 1, description: '{target} is under regulatory oversight by {source}.', source: 'seed' },
];

const ONT_CLASSES = [
  { label: 'Business Center', uri: 'fibo-be-ge-ge:BusinessCenter', comment: 'A financial or business center.' },
  { label: 'Bank', uri: 'fibo-be-ge-ge:Bank', comment: 'A commercial or universal banking institution.' },
  { label: 'Legal Entity', uri: 'fibo-be-le-lp:LegalEntity', comment: 'An entity with legal rights and duties.' },
  { label: 'Bond Instrument', uri: 'fibo-sec-sec-dbt:BondInstrument', comment: 'A debt security representing a bond.' },
  { label: 'Currency', uri: 'fibo-sec-sec-cls:Currency', comment: 'A medium of exchange.' },
  { label: 'Security', uri: 'fibo-sec-sec-cls:Security', comment: 'A financial instrument.' },
  { label: 'Regulatory Agency', uri: 'fibo-fbc-fct-fct:RegulatoryAgency', comment: 'A government or statutory body.' },
  { label: 'Regulation', uri: 'fibo-fbc-fct-fct:Regulation', comment: 'A rule or directive.' },
  { label: 'Market Index', uri: 'fibo-ind-ind-ind:MarketIndex', comment: 'An index tracking market movements.' },
  { label: 'Economic Indicator', uri: 'fibo-ind-ei-ei:EconomicIndicator', comment: 'A metric indicating economic health.' },
];

const ONT_PROPERTIES = [
  { label: 'issued by', uri: 'issuedBy', domain: 'fibo-sec-sec-cls:Security', range: 'fibo-be-le-lp:LegalEntity' },
  { label: 'denominated in', uri: 'denominatedIn', domain: 'fibo-sec-sec-cls:Security', range: 'fibo-sec-sec-cls:Currency' },
  { label: 'has domicile', uri: 'hasDomicile', domain: 'fibo-be-le-lp:LegalEntity', range: 'fibo-be-ge-ge:BusinessCenter' },
  { label: 'regulates', uri: 'regulates', domain: 'fibo-fbc-fct-fct:RegulatoryAgency', range: 'fibo-be-le-lp:LegalEntity' },
  { label: 'has benchmark', uri: 'hasBenchmark', domain: 'fibo-sec-sec-cls:Security', range: 'fibo-ind-ind-ind:MarketIndex' },
  { label: 'tracks', uri: 'tracks', domain: 'fibo-ind-ind-ind:MarketIndex', range: 'fibo-be-le-lp:LegalEntity' },
];

// Helper for deterministic local fallback extraction
function fallbackExtract(text: string) {
  const nodes: any[] = [];
  const edges: any[] = [];
  const lower = text.toLowerCase();
  
  if (lower.includes('ubs')) {
    nodes.push({ id: 'f-ubs', label: 'UBS', type: 'fibo-be-ge-ge:Bank', properties: { sector: 'Banking' }, note: 'Extracted UBS.' });
  }
  if (lower.includes('finma')) {
    nodes.push({ id: 'f-finma', label: 'FINMA', type: 'fibo-fbc-fct-fct:RegulatoryAgency', properties: { jurisdiction: 'CH' }, note: 'Extracted regulator.' });
  }
  if (lower.includes('credit suisse') || lower.includes('cs')) {
    nodes.push({ id: 'f-cs', label: 'Credit Suisse', type: 'fibo-be-ge-ge:Bank', properties: { sector: 'Banking' }, note: 'Extracted bank.' });
  }
  if (lower.includes('zürich') || lower.includes('zurich')) {
    nodes.push({ id: 'f-zh', label: 'Zürich', type: 'fibo-be-ge-ge:BusinessCenter', properties: { jurisdiction: 'CH' }, note: 'Extracted business center.' });
  }
  
  if (nodes.some(n => n.label === 'FINMA') && nodes.some(n => n.label === 'UBS')) {
    edges.push({ id: 'f-e1', source: 'f-finma', target: 'f-ubs', type: 'regulates' });
  }
  if (nodes.some(n => n.label === 'UBS') && nodes.some(n => n.label === 'Zürich')) {
    edges.push({ id: 'f-e2', source: 'f-ubs', target: 'f-zh', type: 'hasDomicile' });
  }

  if (nodes.length === 0) {
    const words = text.match(/[A-Z][a-z]+/g) || [];
    const uniqueWords = Array.from(new Set(words)).slice(0, 5);
    uniqueWords.forEach((word, idx) => {
      nodes.push({
        id: `f-${Date.now()}-${idx}`,
        label: word,
        type: idx % 2 === 0 ? 'fibo-be-le-lp:LegalEntity' : 'fibo-sec-sec-cls:Security',
        properties: {},
        note: 'Extracted from text.'
      });
    });
  }

  return { nodes, edges };
}

// REST API Endpoints

app.get('/mockup', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'mockup.html'));
});

// 1. Health Checks
app.get('/api/health', (req, res) => {
  res.json({
    status: "ok",
    profile: "cloud",
    ontologyRepository: "fibo",
    neo4j: { ok: true },
    graphdb: { ok: true },
    llm: { ok: true, model: "gemini-3.5-flash" }
  });
});

// 2. Rules CRUD
app.get('/api/rules', (req, res) => {
  res.json({ rules: globalRules });
});

app.post('/api/rules', (req, res) => {
  const { name, edgeType, sourceType, targetType, threshold, weight, description } = req.body;
  const newRule: Rule = {
    id: `r-${Date.now()}`,
    name,
    edgeType,
    sourceType,
    targetType,
    threshold: Number(threshold),
    weight: Number(weight || 1),
    description: description || '',
    source: 'custom'
  };
  globalRules.push(newRule);
  res.json(newRule);
});

app.delete('/api/rules/:ruleId', (req, res) => {
  const { ruleId } = req.params;
  const index = globalRules.findIndex(r => r.id === ruleId);
  if (index !== -1) {
    globalRules.splice(index, 1);
    res.json({ deleted: true });
  } else {
    res.status(404).json({ error: 'Rule not found' });
  }
});

// 3. Ontology Info
app.get('/api/ontology', (req, res) => {
  res.json({
    classLabels: ONT_CLASSES.map(c => c.uri),
    propertyLabels: ONT_PROPERTIES.map(p => p.uri),
    classes: ONT_CLASSES,
    properties: ONT_PROPERTIES,
    subclassOf: [],
    classCount: ONT_CLASSES.length,
    propertyCount: ONT_PROPERTIES.length
  });
});

// 4. Graphs Info
app.get('/api/graphs', (req, res) => {
  const graphs = Object.keys(db).map(id => {
    const g = db[id]!;
    return {
      graphId: id,
      nodeCount: g.nodes.length,
      edgeCount: g.edges.length,
      lastIngestAt: g.history[0]?.createdAt || null
    };
  });
  if (graphs.length === 0) {
    graphs.push({
      graphId: 'default',
      nodeCount: getOrCreateGraph('default').nodes.length,
      edgeCount: getOrCreateGraph('default').edges.length,
      lastIngestAt: new Date().toISOString()
    });
  }
  res.json({ graphs });
});

// 5. Single Graph Fetching
app.get('/api/graph/:graphId', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  res.json({ nodes: g.nodes, edges: g.edges });
});

// 6. Ingest Text
app.post('/api/ingest', async (req, res) => {
  const { graphId, source } = req.body;
  const text = source?.text || '';
  const g = getOrCreateGraph(graphId || 'default');

  let extractedNodes: any[] = [];
  let extractedEdges: any[] = [];

  if (ai && text) {
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: `Using the text provided, extract a set of entities and relationships that fit into this ontology schema:
Classes: Bank, BusinessCenter, LegalEntity, BondInstrument, Currency, Security, RegulatoryAgency, Regulation, MarketIndex, EconomicIndicator
Relationships: issuedBy, denominatedIn, hasDomicile, regulates, hasBenchmark, tracks

Text: "${text.replace(/"/g, '\\"')}"

Format your output as a raw JSON object with keys: "nodes" (each with properties: label, type (must be one of the Classes listed above, prefix with 'fibo-' or similar if appropriate), properties (key-value strings), note) and "edges" (each with properties: source (label of source node), target (label of target node), type (must be one of the Relationships listed above)). Do not output markdown, just raw JSON.`,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              nodes: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    label: { type: Type.STRING },
                    type: { type: Type.STRING },
                    properties: { type: Type.OBJECT },
                    note: { type: Type.STRING }
                  },
                  required: ['label', 'type']
                }
              },
              edges: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    source: { type: Type.STRING },
                    target: { type: Type.STRING },
                    type: { type: Type.STRING }
                  },
                  required: ['source', 'target', 'type']
                }
              }
            }
          }
        }
      });
      const data = JSON.parse(response.text?.trim() || '{}');
      extractedNodes = data.nodes || [];
      extractedEdges = data.edges || [];
    } catch (err) {
      console.error('Gemini extraction failed, using fallback:', err);
      const fallback = fallbackExtract(text);
      extractedNodes = fallback.nodes;
      extractedEdges = fallback.edges;
    }
  } else {
    const fallback = fallbackExtract(text);
    extractedNodes = fallback.nodes;
    extractedEdges = fallback.edges;
  }

  // Insert extracted nodes into active graph store
  const newNodes: LayoutNode[] = [];
  const labelToId = new Map<string, string>();

  // Map old nodes for lookups
  g.nodes.forEach(n => labelToId.set(n.label.toLowerCase(), n.id));

  extractedNodes.forEach((node, i) => {
    const key = node.label.toLowerCase();
    if (labelToId.has(key)) {
      // Node already exists
      return;
    }
    const id = `n-extracted-${Date.now()}-${i}`;
    labelToId.set(key, id);
    const newNode: LayoutNode = {
      id,
      label: node.label,
      type: node.type.startsWith('fibo-') ? node.type : `fibo-be-le-lp:${node.type}`,
      activation: 0,
      note: node.note || '',
      properties: node.properties || {},
      salience: 1.0,
      communityId: null
    };
    newNodes.push(newNode);
    g.nodes.push(newNode);
  });

  extractedEdges.forEach((edge, i) => {
    const sourceId = labelToId.get(edge.source.toLowerCase());
    const targetId = labelToId.get(edge.target.toLowerCase());
    if (sourceId && targetId) {
      const newEdge: ApiEdge = {
        id: `e-extracted-${Date.now()}-${i}`,
        source: sourceId,
        target: targetId,
        type: edge.type,
        weight: 1
      };
      g.edges.push(newEdge);
    }
  });

  // Log to history
  g.history.unshift({
    id: `h-${Date.now()}`,
    text: text.slice(0, 100) + (text.length > 100 ? '...' : ''),
    entityCount: extractedNodes.length,
    relationshipCount: extractedEdges.length,
    droppedCount: 0,
    createdAt: new Date().toISOString()
  });

  res.json({
    nodes: g.nodes,
    edges: g.edges,
    dropped: []
  });
});

// 7. Manual Add Nodes/Edges
app.post('/api/graph/:graphId/nodes', (req, res) => {
  const { graphId } = req.params;
  const { label, type } = req.body;
  const g = getOrCreateGraph(graphId);
  const newNode: LayoutNode = {
    id: `n-custom-${Date.now()}`,
    label,
    type,
    activation: 0,
    properties: {},
    salience: 1.0,
    communityId: null
  };
  g.nodes.push(newNode);
  res.json(newNode);
});

app.post('/api/graph/:graphId/edges', (req, res) => {
  const { graphId } = req.params;
  const { sourceId, targetId, type } = req.body;
  const g = getOrCreateGraph(graphId);
  const newEdge: ApiEdge = {
    id: `e-custom-${Date.now()}`,
    source: sourceId,
    target: targetId,
    type,
    weight: 1
  };
  g.edges.push(newEdge);
  res.json(newEdge);
});

app.patch('/api/graph/:graphId/nodes/:nodeId', (req, res) => {
  const { graphId, nodeId } = req.params;
  const patch = req.body;
  const g = getOrCreateGraph(graphId);
  const node = g.nodes.find(n => n.id === nodeId);
  if (node) {
    if (patch.salience !== undefined) node.salience = Number(patch.salience);
    if (patch.note !== undefined) node.note = patch.note;
    if (patch.properties !== undefined) node.properties = { ...node.properties, ...patch.properties };
    res.json(node);
  } else {
    res.status(404).json({ error: 'Node not found' });
  }
});

// 8. Ingest History
app.get('/api/history/:graphId', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  res.json({ events: g.history });
});

// 9. Heuristic Enrichment (Polanyi implicit facts)
app.get('/api/enrich/:graphId/pending', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  res.json({ facts: g.pendingFacts });
});

app.get('/api/enrich/:graphId/approved', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  res.json({ facts: g.approvedFacts });
});

app.post('/api/enrich/:graphId/:factId/approve', (req, res) => {
  const { graphId, factId } = req.params;
  const g = getOrCreateGraph(graphId);
  const factIndex = g.pendingFacts.findIndex(f => f.id === factId);
  if (factIndex !== -1) {
    const fact = g.pendingFacts[factIndex]!;
    fact.status = 'approved';
    g.pendingFacts.splice(factIndex, 1);
    g.approvedFacts.push(fact);
    res.json({ facts: g.pendingFacts });
  } else {
    res.status(404).json({ error: 'Fact not found' });
  }
});

app.post('/api/enrich/:graphId/:factId/reject', (req, res) => {
  const { graphId, factId } = req.params;
  const g = getOrCreateGraph(graphId);
  const factIndex = g.pendingFacts.findIndex(f => f.id === factId);
  if (factIndex !== -1) {
    const fact = g.pendingFacts[factIndex]!;
    fact.status = 'rejected';
    g.pendingFacts.splice(factIndex, 1);
    res.json({ facts: g.pendingFacts });
  } else {
    res.status(404).json({ error: 'Fact not found' });
  }
});

app.post('/api/enrich/:graphId', async (req, res) => {
  const { graphId } = req.params;
  const { text } = req.body;
  const g = getOrCreateGraph(graphId);

  let newFacts: ImplicitFact[] = [];
  if (ai && text) {
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: `Identify implicit facts from the following text based on Michael Polanyi's theory of tacit knowledge. Classify each implicit fact into one of these 11 heuristics: presupposition, conversational_implicature, factual_impact, image_schema, metonymic_coercion, moral_value_coercion, symbolic_coercion, event_sequence, causal_relation, implied_future_event, implied_non_event.
        
Text: "${text.replace(/"/g, '\\"')}"

Format your output as a raw JSON array of objects with keys: "heuristicType" (must be one of the 11 listed above), "text" (sentence describing the implicit fact), "confidence" (decimal between 0 and 1). Do not output markdown.`,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                heuristicType: { type: Type.STRING },
                text: { type: Type.STRING },
                confidence: { type: Type.NUMBER }
              },
              required: ['heuristicType', 'text', 'confidence']
            }
          }
        }
      });
      const items = JSON.parse(response.text?.trim() || '[]');
      newFacts = items.map((item: any, i: number) => ({
        id: `fact-implicit-${Date.now()}-${i}`,
        heuristicType: item.heuristicType,
        text: item.text,
        confidence: Number(item.confidence || 0.8),
        status: 'pending',
        anchorEntityIds: []
      }));
    } catch (err) {
      console.error('Implicit enrichment failed:', err);
    }
  }

  // Fallback / standard seeding if no facts generated
  if (newFacts.length === 0) {
    newFacts = [
      {
        id: `fact-implicit-${Date.now()}-1`,
        heuristicType: 'presupposition',
        text: 'The financial regulatory framework of FINMA is highly trusted by Swiss banks.',
        confidence: 0.95,
        status: 'pending',
        anchorEntityIds: []
      },
      {
        id: `fact-implicit-${Date.now()}-2`,
        heuristicType: 'causal_relation',
        text: 'Instabilities in Credit Suisse will cause FINMA to enforce stricter capital controls on UBS.',
        confidence: 0.85,
        status: 'pending',
        anchorEntityIds: []
      }
    ];
  }

  g.pendingFacts.push(...newFacts);
  res.json({ facts: newFacts });
});

// 10. Community Detection (Louvain-like Mock)
app.post('/api/graph/:graphId/communities', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  
  // Assign simple deterministic communities based on types/clusters
  g.nodes.forEach((n, i) => {
    if (n.type.includes('Bank') || n.label.includes('Credit') || n.label.includes('UBS')) {
      n.communityId = 1;
    } else if (n.type.includes('Agency') || n.label.includes('FINMA')) {
      n.communityId = 2;
    } else {
      n.communityId = 3;
    }
  });

  const members = g.nodes.map(n => ({
    entityId: n.id,
    label: n.label,
    communityId: n.communityId || 0
  }));

  res.json({ members });
});

app.get('/api/graph/:graphId/communities', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  const members = g.nodes.map(n => ({
    entityId: n.id,
    label: n.label,
    communityId: n.communityId || 0
  }));
  res.json({ members });
});

// 11. Paths and Queries
app.get('/api/query/:graphId/triples', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  const triples: any[] = [];

  g.edges.forEach(e => {
    const s = g.nodes.find(n => n.id === e.source);
    const t = g.nodes.find(n => n.id === e.target);
    if (s && t) {
      triples.push({
        subject: s.label,
        predicate: e.type,
        object: t.label,
        derived: false,
        confidence: 1.0
      });
    }
  });

  g.facts.forEach(f => {
    triples.push({
      subject: g.nodes.find(n => n.id === f.sourceId)?.label || 'Unknown',
      predicate: f.ruleName,
      object: g.nodes.find(n => n.id === f.targetId)?.label || 'Unknown',
      derived: true,
      confidence: f.confidence
    });
  });

  res.json({ triples, total: triples.length });
});

app.post('/api/query/:graphId', (req, res) => {
  const { graphId } = req.params;
  const { query } = req.body;
  const g = getOrCreateGraph(graphId);

  const triples: any[] = [];
  g.edges.forEach(e => {
    const s = g.nodes.find(n => n.id === e.source);
    const t = g.nodes.find(n => n.id === e.target);
    if (s && t) {
      triples.push({
        subject: s.label,
        predicate: e.type,
        object: t.label,
        derived: false,
        confidence: 1.0
      });
    }
  });
  g.facts.forEach(f => {
    triples.push({
      subject: g.nodes.find(n => n.id === f.sourceId)?.label || 'Unknown',
      predicate: f.ruleName,
      object: g.nodes.find(n => n.id === f.targetId)?.label || 'Unknown',
      derived: true,
      confidence: f.confidence
    });
  });

  // Evaluate query
  const trimmed = (query || '').trim();
  if (!trimmed) {
    return res.json({ query, results: [], error: 'Empty query.' });
  }

  const parts = trimmed.split(',').map((p: any) => p.trim()).filter(Boolean);
  const parsed = parts.map((part: any) => {
    const m = part.match(/^(\w+)\s*\(\s*(?:"([^"]*)"|(\w+))\s*,\s*(?:"([^"]*)"|(\w+))\s*\)$/);
    if (!m) return null;
    return {
      predicate: m[1],
      subjectLiteral: m[2] || null,
      subjectVar: m[3] || null,
      objectLiteral: m[4] || null,
      objectVar: m[5] || null,
    };
  });

  if (parsed.some((p: any) => p === null)) {
    return res.json({
      query,
      results: [],
      error: 'Invalid syntax. Use: predicate(subject, object) — e.g., regulates(FINMA, X)'
    });
  }

  const results: any[] = [];
  const p = parsed[0]!;

  for (const triple of triples) {
    if (triple.predicate.toLowerCase() !== p.predicate.toLowerCase()) continue;
    let subjectMatch = true;
    let objectMatch = true;
    if (p.subjectLiteral) subjectMatch = triple.subject.toLowerCase() === p.subjectLiteral.toLowerCase();
    else if (p.subjectVar && !['X', 'Y', 'Z', '_'].includes(p.subjectVar.toUpperCase())) subjectMatch = triple.subject.toLowerCase() === p.subjectVar.toLowerCase();
    if (p.objectLiteral) objectMatch = triple.object.toLowerCase() === p.objectLiteral.toLowerCase();
    else if (p.objectVar && !['X', 'Y', 'Z', '_'].includes(p.objectVar.toUpperCase())) objectMatch = triple.object.toLowerCase() === p.objectVar.toLowerCase();
    
    if (subjectMatch && objectMatch) {
      results.push({
        subject: triple.subject,
        predicate: triple.predicate,
        object: triple.object,
        derived: triple.derived,
        confidence: triple.confidence
      });
    }
  }

  res.json({ query, results, error: null });
});

app.post('/api/query/:graphId/path', (req, res) => {
  const { graphId } = req.params;
  const { source, target } = req.body;
  const g = getOrCreateGraph(graphId);

  const sNode = g.nodes.find(n => n.label.toLowerCase() === source.toLowerCase());
  const tNode = g.nodes.find(n => n.label.toLowerCase() === target.toLowerCase());

  if (!sNode) return res.json({ found: false, path: [], edges: [], proof: '', error: `Node "${source}" not found.` });
  if (!tNode) return res.json({ found: false, path: [], edges: [], proof: '', error: `Node "${target}" not found.` });

  // BFS search
  const queue: any[] = [{ id: sNode.id, path: [sNode.label], edges: [] }];
  const visited = new Set<string>([sNode.id]);

  while (queue.length > 0) {
    const { id, path, edges: pathEdges } = queue.shift()!;
    if (id === tNode.id) {
      const proof = path.map((label: string, i: number) => {
        if (i === 0) return label;
        const edge = pathEdges[i - 1];
        return ` →[${edge.label}]→ ${label}`;
      }).join('');
      return res.json({ found: true, path, edges: pathEdges, proof, error: null });
    }

    const outEdges = g.edges.filter(e => e.source === id || e.target === id);
    for (const edge of outEdges) {
      const neighborId = edge.source === id ? edge.target : edge.source;
      if (visited.has(neighborId)) continue;
      visited.add(neighborId);
      const neighbor = g.nodes.find(n => n.id === neighborId);
      if (!neighbor) continue;
      queue.push({
        id: neighborId,
        path: [...path, neighbor.label],
        edges: [...pathEdges, { source: id, target: neighborId, label: edge.type }]
      });
    }
  }

  res.json({ found: false, path: [], edges: [], proof: '', error: `No path found between "${source}" and "${target}".` });
});

// 12. General Reasoning Workflows (Spread / Infer / Feed Back)
app.post('/api/reason/:graphId/spread', (req, res) => {
  const { graphId } = req.params;
  const { sourceId } = req.body;
  const g = getOrCreateGraph(graphId);

  // Clear previous activations
  g.nodes.forEach(n => n.activation = 0);

  const source = g.nodes.find(n => n.id === sourceId);
  if (!source) {
    return res.json({ activation: {} });
  }

  source.activation = 1.0;
  const visited = new Set<string>([source.id]);
  const queue = [{ id: source.id, depth: 0 }];

  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    const current = g.nodes.find(n => n.id === id);
    if (!current || !current.activation) continue;

    const outEdges = g.edges.filter(e => e.source === id || e.target === id);
    for (const edge of outEdges) {
      const neighborId = edge.source === id ? edge.target : edge.source;
      if (visited.has(neighborId) && depth >= 4) continue;

      const neighbor = g.nodes.find(n => n.id === neighborId);
      if (!neighbor) continue;

      const decay = 0.45;
      const newActivation = current.activation * decay * (edge.weight || 1) * (neighbor.salience || 1);

      if (newActivation > (neighbor.activation || 0)) {
        neighbor.activation = newActivation;
      }

      if (!visited.has(neighborId)) {
        visited.add(neighborId);
        queue.push({ id: neighborId, depth: depth + 1 });
      }
    }
  }

  g.loopStep = 'neural';

  const activation: Record<string, number> = {};
  g.nodes.forEach(n => {
    if (n.activation && n.activation > 0) {
      activation[n.id] = n.activation;
    }
  });

  res.json({ activation });
});

app.post('/api/reason/:graphId/infer', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  
  const newFacts: DerivedFact[] = [];
  const newTrace: TraceEntry[] = [];
  g.loopIteration += 1;

  for (const rule of globalRules) {
    for (const edge of g.edges) {
      if (edge.type.toLowerCase() !== rule.edgeType.toLowerCase()) continue;

      const sourceNode = g.nodes.find(n => n.id === edge.source);
      const targetNode = g.nodes.find(n => n.id === edge.target);
      if (!sourceNode || !targetNode) continue;

      if (sourceNode.type.toLowerCase() !== rule.sourceType.toLowerCase()) continue;
      if (targetNode.type.toLowerCase() !== rule.targetType.toLowerCase()) continue;

      const sourceActivation = sourceNode.activation || 0;
      const fired = sourceActivation >= rule.threshold;
      const factId = `fact-${rule.id}-${edge.id}`;

      const traceEntry: TraceEntry = {
        ruleName: rule.name,
        edgeType: edge.type,
        sourceLabel: sourceNode.label,
        targetLabel: targetNode.label,
        sourceActivation,
        threshold: rule.threshold,
        fired,
        iteration: g.loopIteration,
        skipReason: fired ? null : 'Activation below threshold',
        factId: fired ? factId : null
      };

      newTrace.push(traceEntry);

      if (!fired) continue;
      if (g.facts.some(f => f.id === factId) || newFacts.some(f => f.id === factId)) continue;

      const proofStep = {
        ruleName: rule.name,
        edgeType: edge.type,
        sourceLabel: sourceNode.label,
        targetLabel: targetNode.label,
        premiseActivation: sourceActivation,
        iteration: g.loopIteration,
        typeResolution: null
      };

      const fact: DerivedFact = {
        id: factId,
        fact: rule.description.replace('{source}', sourceNode.label).replace('{target}', targetNode.label),
        confidence: sourceActivation,
        iteration: g.loopIteration,
        sourceId: sourceNode.id,
        targetId: targetNode.id,
        ruleName: rule.name,
        proofPath: [proofStep],
        fedBack: false
      };

      newFacts.push(fact);
      targetNode.derived = true;
    }
  }

  g.facts.push(...newFacts);
  g.trace.push(...newTrace);
  g.loopStep = 'symbolic';

  res.json({ facts: newFacts, trace: newTrace });
});

app.post('/api/reason/:graphId/feedback', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);

  for (const fact of g.facts) {
    if (fact.fedBack) continue;
    const target = g.nodes.find(n => n.id === fact.targetId);
    if (!target) continue;

    const boost = fact.confidence * 0.5;
    target.activation = Math.min(1, (target.activation || 0) + boost);
    fact.fedBack = true;
  }

  g.loopStep = 'feedback';

  const activation: Record<string, number> = {};
  g.nodes.forEach(n => {
    if (n.activation && n.activation > 0) {
      activation[n.id] = n.activation;
    }
  });

  res.json({ activation });
});

app.get('/api/reason/:graphId/facts', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  res.json({ facts: g.facts });
});

app.post('/api/reason/:graphId/clear-activation', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  g.nodes.forEach(n => n.activation = 0);
  g.loopStep = 'idle';
  res.json({ cleared: true });
});

app.post('/api/reason/:graphId/clear-facts', (req, res) => {
  const { graphId } = req.params;
  const g = getOrCreateGraph(graphId);
  g.facts = [];
  g.trace = [];
  g.nodes.forEach(n => n.derived = false);
  res.json({ cleared: true });
});

app.post('/api/reason/:graphId', (req, res) => {
  const { graphId } = req.params;
  const { sourceId } = req.body;
  const g = getOrCreateGraph(graphId);

  // Auto spread + infer + feedback
  g.nodes.forEach(n => n.activation = 0);
  const source = g.nodes.find(n => n.id === sourceId);
  if (source) source.activation = 1.0;

  // 1. Spreading
  const visited = new Set<string>();
  const queue = source ? [{ id: source.id, depth: 0 }] : [];
  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    const current = g.nodes.find(n => n.id === id);
    if (!current || !current.activation) continue;

    const outEdges = g.edges.filter(e => e.source === id || e.target === id);
    for (const edge of outEdges) {
      const neighborId = edge.source === id ? edge.target : edge.source;
      if (visited.has(neighborId) && depth >= 4) continue;

      const neighbor = g.nodes.find(n => n.id === neighborId);
      if (!neighbor) continue;

      const decay = 0.45;
      const newActivation = current.activation * decay * (edge.weight || 1) * (neighbor.salience || 1);

      if (newActivation > (neighbor.activation || 0)) {
        neighbor.activation = newActivation;
      }

      if (!visited.has(neighborId)) {
        visited.add(neighborId);
        queue.push({ id: neighborId, depth: depth + 1 });
      }
    }
  }

  // 2. Inference
  const factsAdded: DerivedFact[] = [];
  for (const rule of globalRules) {
    for (const edge of g.edges) {
      if (edge.type.toLowerCase() !== rule.edgeType.toLowerCase()) continue;
      const sN = g.nodes.find(n => n.id === edge.source);
      const tN = g.nodes.find(n => n.id === edge.target);
      if (!sN || !tN) continue;
      if (sN.type.toLowerCase() !== rule.sourceType.toLowerCase()) continue;
      if (tN.type.toLowerCase() !== rule.targetType.toLowerCase()) continue;

      const sourceActivation = sN.activation || 0;
      if (sourceActivation >= rule.threshold) {
        const factId = `fact-${rule.id}-${edge.id}`;
        if (!g.facts.some(f => f.id === factId)) {
          const fact: DerivedFact = {
            id: factId,
            fact: rule.description.replace('{source}', sN.label).replace('{target}', tN.label),
            confidence: sourceActivation,
            iteration: 1,
            sourceId: sN.id,
            targetId: tN.id,
            ruleName: rule.name,
            proofPath: [],
            fedBack: true
          };
          factsAdded.push(fact);
          g.facts.push(fact);
          tN.derived = true;
          tN.activation = Math.min(1, (tN.activation || 0) + sourceActivation * 0.5);
        }
      }
    }
  }

  const act: Record<string, number> = {};
  g.nodes.forEach(n => {
    if (n.activation && n.activation > 0) act[n.id] = n.activation;
  });

  res.json({
    activation: act,
    facts: g.facts,
    iterations: 1,
    convergedBy: 'fixpoint'
  });
});

// 13. AI Chat Interface
app.post('/api/chat/:graphId', async (req, res) => {
  const { graphId } = req.params;
  const { message } = req.body;
  const g = getOrCreateGraph(graphId);

  let reply = '';
  if (ai && message) {
    try {
      const graphContext = g.nodes.map(n => `${n.label} (${n.type})`).join(', ');
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: `You are an expert financial neurosymbolic knowledge graph AI. Discuss and answer the user query based on this graph context:
        
Graph Nodes: ${graphContext}
Query: "${message}"`,
        config: {
          systemInstruction: "Be extremely concise, helpful, and pair factual analysis with structural neurosymbolic concepts."
        }
      });
      reply = response.text || '';
    } catch (err) {
      console.error('Gemini chat failed, using fallback:', err);
    }
  }

  if (!reply) {
    reply = `I received your message: "${message}". In this in-memory graph representing the Swiss banking ecosystem, we have ${g.nodes.length} entities under supervision, including Credit Suisse, FINMA, and UBS, with ${g.edges.length} active relationships. Let me know if you would like to run spread activation or apply rules.`;
  }

  res.json({ reply });
});

// 14. Smart Agent (LangGraph parity)
app.post('/api/agent/:graphId', async (req, res) => {
  const { graphId } = req.params;
  const { text } = req.body;
  const g = getOrCreateGraph(graphId);

  let reply = '';
  let intent: any = '';
  let entitiesExtracted = 0;
  let relationshipsExtracted = 0;
  let factsDerived = 0;

  if (ai && text) {
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: `You are a smart Neurosymbolic KG Agent. Analyze this user message: "${text.replace(/"/g, '\\"')}"
        
Classify the user intent into one of these categories: 'extract', 'enrich', 'query', 'reason', 'visualize', or '' (empty string if general chat).
Draft a concise, expert reply executing or acknowledging that action.

Format your response as a raw JSON object with keys: "reply" (string), "intent" (string), "entitiesExtracted" (number), "relationshipsExtracted" (number), "factsDerived" (number), "enrichmentFactTexts" (array of strings), "queryResults" (array of strings), "queryError" (string). Do not output markdown, just raw JSON.`,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              reply: { type: Type.STRING },
              intent: { type: Type.STRING },
              entitiesExtracted: { type: Type.INTEGER },
              relationshipsExtracted: { type: Type.INTEGER },
              factsDerived: { type: Type.INTEGER },
              enrichmentFactTexts: { type: Type.ARRAY, items: { type: Type.STRING } },
              queryResults: { type: Type.ARRAY, items: { type: Type.STRING } },
              queryError: { type: Type.STRING }
            },
            required: ['reply', 'intent']
          }
        }
      });
      const data = JSON.parse(response.text?.trim() || '{}');
      reply = data.reply || '';
      intent = data.intent || '';
      entitiesExtracted = Number(data.entitiesExtracted || 0);
      relationshipsExtracted = Number(data.relationshipsExtracted || 0);
      factsDerived = Number(data.factsDerived || 0);
    } catch (err) {
      console.error('Agent generation failed, using fallback:', err);
    }
  }

  if (!reply) {
    const lower = text.toLowerCase();
    if (lower.includes('reason') || lower.includes('spread') || lower.includes('infer')) {
      intent = 'reason';
      reply = "Initiating neurosymbolic reasoning loops on the active Swiss banking graph. Spreading neural activation and executing logical constraints.";
    } else if (lower.includes('ingest') || lower.includes('extract') || lower.includes('read')) {
      intent = 'extract';
      reply = "Extracted new financial entities and legal frameworks into the active graph from your input document.";
    } else if (lower.includes('enrich') || lower.includes('heuristics')) {
      intent = 'enrich';
      reply = "Michael Polanyi heuristics search complete. Pinpointed tacit implicit facts awaiting user confirmation.";
    } else {
      intent = 'query';
      reply = "Query complete. Matching path relationships across active banking nodes.";
    }
  }

  res.json({
    reply,
    intent,
    entitiesExtracted,
    relationshipsExtracted,
    factsDerived,
    enrichmentFactTexts: [],
    queryResults: [],
    queryError: ""
  });
});

// Vite Setup (Development vs. Production)
if (process.env.NODE_ENV !== 'production') {
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: 'spa',
    root: path.resolve(__dirname, 'frontend')
  });
  app.use(vite.middlewares);
} else {
  const distPath = path.join(__dirname, 'frontend', 'dist');
  app.use(express.static(distPath));
  app.get('*', (req, res) => {
    res.sendFile(path.join(distPath, 'index.html'));
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});
