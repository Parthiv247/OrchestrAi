"""Generate the OrchestrAI architecture diagram as an SVG."""
from pathlib import Path

content = '''<svg width="1200" height="700" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0f172a"/>
      <stop offset="100%" style="stop-color:#1e1b4b"/>
    </linearGradient>
    <linearGradient id="blue" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#3b82f6"/>
      <stop offset="100%" style="stop-color:#8b5cf6"/>
    </linearGradient>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6"/>
    </marker>
  </defs>

  <!-- Background -->
  <rect width="1200" height="700" fill="url(#bg)" rx="16"/>

  <!-- Title -->
  <text x="600" y="40" text-anchor="middle" fill="white" font-size="22" font-weight="bold">OrchestrAI &#8212; Architecture</text>
  <text x="600" y="62" text-anchor="middle" fill="#94a3b8" font-size="12">Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines</text>

  <!-- SOURCES -->
  <rect x="30" y="90" width="170" height="160" rx="12" fill="#1e293b" stroke="#3b82f6" stroke-width="1.5"/>
  <text x="115" y="112" text-anchor="middle" fill="#3b82f6" font-size="11" font-weight="bold">SOURCES</text>
  <rect x="45" y="120" width="140" height="28" rx="6" fill="#0f172a"/>
  <text x="115" y="139" text-anchor="middle" fill="#e2e8f0" font-size="11">PostgreSQL</text>
  <rect x="45" y="154" width="140" height="28" rx="6" fill="#0f172a"/>
  <text x="115" y="173" text-anchor="middle" fill="#e2e8f0" font-size="11">REST API</text>
  <rect x="45" y="188" width="140" height="28" rx="6" fill="#0f172a"/>
  <text x="115" y="207" text-anchor="middle" fill="#e2e8f0" font-size="11">Google Sheets</text>
  <rect x="45" y="222" width="140" height="28" rx="6" fill="#0f172a"/>
  <text x="115" y="241" text-anchor="middle" fill="#e2e8f0" font-size="11">CSV / S3</text>

  <!-- SOURCES -> AIRFLOW -->
  <line x1="200" y1="170" x2="255" y2="170" stroke="#3b82f6" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- AIRFLOW -->
  <rect x="255" y="120" width="140" height="100" rx="12" fill="#1e293b" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="325" y="150" text-anchor="middle" fill="#f59e0b" font-size="11" font-weight="bold">AIRFLOW</text>
  <text x="325" y="170" text-anchor="middle" fill="#94a3b8" font-size="10">4 ETL DAGs</text>
  <text x="325" y="188" text-anchor="middle" fill="#94a3b8" font-size="10">LocalExecutor</text>

  <!-- AIRFLOW -> DESTINATION -->
  <line x1="395" y1="170" x2="450" y2="170" stroke="#3b82f6" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- DESTINATION -->
  <rect x="450" y="110" width="160" height="120" rx="12" fill="#1e293b" stroke="#8b5cf6" stroke-width="1.5"/>
  <text x="530" y="135" text-anchor="middle" fill="#8b5cf6" font-size="11" font-weight="bold">DESTINATION</text>
  <text x="530" y="158" text-anchor="middle" fill="#e2e8f0" font-size="13">Snowflake</text>
  <text x="530" y="178" text-anchor="middle" fill="#94a3b8" font-size="10">RAW schema</text>
  <text x="530" y="198" text-anchor="middle" fill="#94a3b8" font-size="10">+ Local PG fallback</text>

  <!-- SELF-HEALING AGENTS (Phase 2) -->
  <rect x="30" y="310" width="500" height="175" rx="12" fill="#1e293b" stroke="#ef4444" stroke-width="1.5"/>
  <text x="280" y="335" text-anchor="middle" fill="#ef4444" font-size="12" font-weight="bold">SELF-HEALING AGENTS (LangGraph StateGraph)</text>

  <rect x="45" y="345" width="88" height="50" rx="8" fill="#0f172a"/>
  <text x="89" y="367" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 1</text>
  <text x="89" y="382" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Monitor</text>
  <text x="140" y="373" text-anchor="middle" fill="#3b82f6" font-size="14">&#8594;</text>
  <rect x="143" y="345" width="88" height="50" rx="8" fill="#0f172a"/>
  <text x="187" y="367" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 2</text>
  <text x="187" y="382" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Diagnose</text>
  <text x="238" y="373" text-anchor="middle" fill="#3b82f6" font-size="14">&#8594;</text>
  <rect x="241" y="345" width="88" height="50" rx="8" fill="#0f172a"/>
  <text x="285" y="367" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 3</text>
  <text x="285" y="382" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Fix Writer</text>
  <text x="336" y="373" text-anchor="middle" fill="#3b82f6" font-size="14">&#8594;</text>
  <rect x="339" y="345" width="88" height="50" rx="8" fill="#0f172a"/>
  <text x="383" y="367" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 4</text>
  <text x="383" y="382" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Sandbox</text>
  <text x="434" y="373" text-anchor="middle" fill="#3b82f6" font-size="14">&#8594;</text>
  <rect x="437" y="345" width="88" height="50" rx="8" fill="#0f172a"/>
  <text x="481" y="367" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 5</text>
  <text x="481" y="382" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Deploy</text>

  <text x="280" y="425" text-anchor="middle" fill="#94a3b8" font-size="10">IsolationForest anomaly detection  &#183;  Groq LLM  &#183;  Docker sandbox  &#183;  Email approval</text>
  <text x="280" y="445" text-anchor="middle" fill="#94a3b8" font-size="10">ChromaDB RAG (Learning Agent)  &#183;  12-point test suite  &#183;  Airflow restart</text>
  <text x="280" y="465" text-anchor="middle" fill="#94a3b8" font-size="10">Confidence threshold: 75% auto-approve  &#183;  Human-in-the-loop below threshold</text>

  <!-- ANALYTICS AGENTS -->
  <rect x="550" y="310" width="360" height="175" rx="12" fill="#1e293b" stroke="#10b981" stroke-width="1.5"/>
  <text x="730" y="335" text-anchor="middle" fill="#10b981" font-size="12" font-weight="bold">ANALYTICS + TRANSFORMATION AGENTS</text>

  <rect x="565" y="345" width="155" height="50" rx="8" fill="#0f172a"/>
  <text x="642" y="363" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 6</text>
  <text x="642" y="378" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">dbt Modeling</text>
  <text x="642" y="392" text-anchor="middle" fill="#64748b" font-size="9">Star schema + SQL gen</text>

  <rect x="565" y="405" width="155" height="50" rx="8" fill="#0f172a"/>
  <text x="642" y="423" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 7</text>
  <text x="642" y="438" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Cost Optimizer</text>
  <text x="642" y="452" text-anchor="middle" fill="#64748b" font-size="9">EXPLAIN ANALYZE + rewrite</text>

  <rect x="730" y="345" width="165" height="50" rx="8" fill="#0f172a"/>
  <text x="812" y="363" text-anchor="middle" fill="#94a3b8" font-size="9">Agent 8</text>
  <text x="812" y="378" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Query Agent</text>
  <text x="812" y="392" text-anchor="middle" fill="#64748b" font-size="9">NL&#8594;SQL + chart suggest</text>

  <rect x="730" y="405" width="165" height="50" rx="8" fill="#0f172a"/>
  <text x="812" y="423" text-anchor="middle" fill="#94a3b8" font-size="9">Agents 9 + 10</text>
  <text x="812" y="438" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Insights + RAG</text>
  <text x="812" y="452" text-anchor="middle" fill="#64748b" font-size="9">10 insights &#183; ChromaDB</text>

  <!-- FRONTEND + API column -->
  <rect x="930" y="90" width="240" height="395" rx="12" fill="#1e293b" stroke="#3b82f6" stroke-width="1.5"/>
  <text x="1050" y="112" text-anchor="middle" fill="#3b82f6" font-size="11" font-weight="bold">PRESENTATION</text>
  <rect x="945" y="125" width="210" height="60" rx="8" fill="#0f172a"/>
  <text x="1050" y="150" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">Next.js 14 Frontend</text>
  <text x="1050" y="168" text-anchor="middle" fill="#64748b" font-size="9">7 pages &#183; shadcn/ui &#183; Recharts</text>
  <rect x="945" y="195" width="210" height="60" rx="8" fill="#0f172a"/>
  <text x="1050" y="220" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">FastAPI Backend</text>
  <text x="1050" y="238" text-anchor="middle" fill="#64748b" font-size="9">REST + WebSocket &#183; JWT/RBAC</text>
  <rect x="945" y="265" width="210" height="60" rx="8" fill="#0f172a"/>
  <text x="1050" y="290" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">ChromaDB Vector Store</text>
  <text x="1050" y="308" text-anchor="middle" fill="#64748b" font-size="9">RAG memory &#183; MiniLM embeddings</text>
  <rect x="945" y="335" width="210" height="60" rx="8" fill="#0f172a"/>
  <text x="1050" y="360" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">PostgreSQL</text>
  <text x="1050" y="378" text-anchor="middle" fill="#64748b" font-size="9">runs &#183; incidents &#183; metrics</text>
  <rect x="945" y="405" width="210" height="60" rx="8" fill="#0f172a"/>
  <text x="1050" y="430" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">Groq LLM</text>
  <text x="1050" y="448" text-anchor="middle" fill="#64748b" font-size="9">llama-3.3-70b-versatile</text>

  <!-- TECH STACK FOOTER -->
  <rect x="30" y="510" width="1140" height="55" rx="10" fill="#0f172a" stroke="#1e293b" stroke-width="1"/>
  <text x="600" y="532" text-anchor="middle" fill="#64748b" font-size="10" font-weight="bold">TECH STACK</text>
  <text x="600" y="552" text-anchor="middle" fill="#475569" font-size="10">LangChain &#183; LangGraph &#183; Groq (llama-3.3-70b) &#183; FastAPI &#183; Next.js 14 &#183; shadcn/ui &#183; Airflow &#183; PostgreSQL &#183; Snowflake &#183; ChromaDB &#183; Docker &#183; Fernet</text>

  <!-- 10 AGENTS badge -->
  <rect x="30" y="585" width="1140" height="90" rx="10" fill="#0f172a" stroke="#1e293b" stroke-width="1"/>
  <text x="600" y="610" text-anchor="middle" fill="#8b5cf6" font-size="12" font-weight="bold">10 AUTONOMOUS AGENTS &#183; 4 PHASES</text>
  <text x="600" y="632" text-anchor="middle" fill="#94a3b8" font-size="10">Phase 1: ETL Pipelines (4 connectors + Airflow DAGs)  &#183;  Phase 2: Self-Healing (Monitor, Diagnose, Fix, Sandbox, Deploy)</text>
  <text x="600" y="650" text-anchor="middle" fill="#94a3b8" font-size="10">Phase 3: Transformation + Optimization (dbt Modeling, Cost Optimizer)  &#183;  Phase 4: Analytics (Query, Insights, Learning/RAG)</text>
  <text x="600" y="668" text-anchor="middle" fill="#64748b" font-size="9">100% on-premise &#183; human-in-the-loop approval gates &#183; 91% avg heal confidence</text>

  <!-- cross-layer arrows -->
  <line x1="280" y1="295" x2="280" y2="310" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4" marker-end="url(#arrow)"/>
  <line x1="530" y1="230" x2="530" y2="310" stroke="#10b981" stroke-width="1.5" stroke-dasharray="4" marker-end="url(#arrow)"/>
</svg>
'''

out = Path('/Users/parthivpatel/OrchetraAI/docs/architecture.svg')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(content)
print(f"✅ Architecture diagram saved to {out}")
