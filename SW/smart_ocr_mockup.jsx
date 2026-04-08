import { useState, useEffect } from "react";

// Sample CBCL questions (first items from each page)
const CBCL_QUESTIONS = {
  page_4: [
    { id: "1", text: "Agisce in modo infantile per la sua età" },
    { id: "2", text: "Beve alcolici senza l'approvazione dei genitori" },
    { id: "3", text: "Discute in modo polemico" },
    { id: "4", text: "Non porta a termine le cose che comincia" },
    { id: "5", text: "Ci sono veramente poche cose che lo divertono" },
    { id: "6", text: "Si fa la cacca addosso" },
    { id: "7", text: "Si vanta e si gloria" },
    { id: "8", text: "Non riesce a concentrarsi, non riesce a mantenere l'attenzione a lungo" },
    { id: "9", text: "Non riesce a evitare certi pensieri; ossessioni" },
    { id: "10", text: "Non riesce a stare seduto tranquillo, è irrequieto o iperattivo" },
    { id: "11", text: "E' molto attaccato agli adulti, troppo dipendente" },
    { id: "12", text: "Lamenta di sentirsi solo" },
    { id: "13", text: "E' confuso o sembra avere la testa nel pallone" },
    { id: "14", text: "Piange molto" },
    { id: "15", text: "E' crudele verso gli animali" },
    { id: "16", text: "E' crudele, prepotente o malvagio verso gli altri" },
    { id: "17", text: "Sogna ad occhi aperti, si perde nei suoi pensieri" },
    { id: "18", text: "Intenzionalmente si fa del male o ha tentato il suicidio" },
    { id: "19", text: "Esige molta attenzione" },
    { id: "20", text: "Distrugge le sue cose" },
    { id: "21", text: "Distrugge le cose che appartengono alla famiglia o ad altri" },
    { id: "22", text: "E' disobbediente a casa" },
    { id: "23", text: "E' disobbediente a scuola" },
    { id: "24", text: "Non mangia come dovrebbe" },
    { id: "25", text: "Non va d'accordo con gli altri bambini/ragazzi" },
    { id: "26", text: "Non sembra sentirsi in colpa dopo essersi comportato male" },
    { id: "27", text: "Si ingelosisce facilmente" },
    { id: "28", text: "Infrango le regole a casa, a scuola, o altrove" },
    { id: "29", text: "Ha paura di certi animali, situazioni o posti" },
    { id: "30", text: "Ha paura di andare a scuola" },
    { id: "31", text: "Ha paura di poter pensare o fare qualcosa di male" },
    { id: "32", text: "Sente di dover essere perfetto" },
    { id: "33", text: "Pensa che nessuno gli vuole bene" },
    { id: "34", text: "Si sente perseguitato dagli altri" },
    { id: "35", text: "Si sente privo di valore o inferiore" },
    { id: "36", text: "Si fa spesso male, è soggetto ad incidenti" },
    { id: "37", text: "E' coinvolto spesso in zuffe e liti" },
    { id: "38", text: "Viene spesso preso in giro dagli altri" },
    { id: "39", text: "Frequenta cattive compagnie" },
    { id: "40", text: "Sente suoni o voci che non ci sono" },
    { id: "41", text: "E' impulsivo o agisce senza pensare" },
    { id: "42", text: "Preferisce stare da solo piuttosto che con gli altri" },
    { id: "43", text: "E' bugiardo o imbroglione" },
    { id: "44", text: "Si mangia le unghie" },
    { id: "45", text: "Nervoso, troppo sensibile, o teso" },
    { id: "46", text: "Movimenti nervosi o tic" },
    { id: "47", text: "Ha incubi" },
    { id: "48", text: "Non piace agli altri bambini" },
    { id: "49", text: "Soffre di stitichezza" },
    { id: "50", text: "Appare troppo timoroso o ansioso" },
    { id: "51", text: "Soffre di vertigini o stordimenti" },
    { id: "52", text: "Si sente troppo colpevole" },
    { id: "53", text: "Mangia troppo" },
    { id: "54", text: "Sembra esageratamente stanco senza buona ragione" },
  ],
  page_5: [
    { id: "55", text: "E' in soprappeso" },
    { id: "56a", text: "Dolori (non includere mal di stomaco e mal di testa)" },
    { id: "56b", text: "Mal di testa" },
    { id: "56c", text: "Nausea, malessere" },
    { id: "56d", text: "Problemi agli occhi" },
    { id: "56e", text: "Eruzione cutanea o altri problemi di pelle" },
    { id: "56f", text: "Dolori di stomaco" },
    { id: "56g", text: "Vomito, conati" },
    { id: "56h", text: "Altro" },
    { id: "57", text: "Assale fisicamente le persone" },
    { id: "58", text: "Si mette le dita nel naso, si stuzzica la pelle" },
    { id: "59", text: "Gioca con le sue parti genitali in pubblico" },
    { id: "60", text: "Gioca troppo con le sue parti genitali" },
    { id: "61", text: "Ha uno scarso rendimento scolastico" },
    { id: "62", text: "Non coordinato o impacciato nei movimenti" },
    { id: "63", text: "Preferisce la compagnia dei più grandi" },
    { id: "64", text: "Preferisce la compagnia dei più piccoli" },
    { id: "65", text: "Si rifiuta di parlare" },
    { id: "66", text: "Ripete certe azioni di continuo o compulsivamente" },
    { id: "67", text: "Scappa via da casa" },
    { id: "68", text: "Strilla molto" },
    { id: "69", text: "E' riservato, tiene le cose per sé" },
    { id: "70", text: "Vede cose che non ci sono" },
    { id: "71", text: "E' ipersensibile o facilmente imbarazzato" },
    { id: "72", text: "Appicca fuochi" },
    { id: "73", text: "Ha problemi sessuali" },
    { id: "74", text: "Si mette in mostra o fa il pagliaccio" },
    { id: "75", text: "E' troppo riservato o timido" },
    { id: "76", text: "Dorme di meno della maggior parte dei bambini" },
    { id: "77", text: "Dorme di più della maggior parte dei bambini" },
    { id: "78", text: "E' disattento o facilmente distraibile" },
    { id: "79", text: "Ha problemi nel parlare" },
    { id: "80", text: "Fissa il vuoto" },
    { id: "81", text: "Ruba in casa" },
    { id: "82", text: "Ruba fuori di casa" },
    { id: "83", text: "Accumula moltissime cose che non gli servono" },
    { id: "84", text: "Ha strani comportamenti" },
    { id: "85", text: "Ha strane idee" },
    { id: "86", text: "E' testardo, taciturno, irritabile" },
    { id: "87", text: "Ha repentini cambiamenti di umore" },
    { id: "88", text: "E' spesso di cattivo umore" },
    { id: "89", text: "E' sospettoso" },
    { id: "90", text: "Bestemmia o usa un linguaggio osceno" },
    { id: "91", text: "Parla di uccidersi" },
    { id: "92", text: "Parla durante il sonno o fa il sonnambulo" },
    { id: "93", text: "Parla troppo" },
    { id: "94", text: "Prende molto in giro" },
    { id: "95", text: "Ha accessi di collera" },
    { id: "96", text: "Pensa al sesso eccessivamente" },
    { id: "97", text: "Minaccia la gente" },
    { id: "98", text: "Si succhia il pollice" },
    { id: "99", text: "Fuma, mastica o sniffa tabacco" },
    { id: "100", text: "Ha disturbi del sonno" },
    { id: "101", text: "E' svogliato, marina la scuola" },
    { id: "102", text: "E' poco attivo, lento nei movimenti" },
    { id: "103", text: "E' scontento, triste o depresso" },
    { id: "104", text: "E' particolarmente rumoroso" },
    { id: "105", text: "Fa uso di droga" },
    { id: "106", text: "Commette atti di vandalismo" },
    { id: "107", text: "Si fa la pipì addosso durante il giorno" },
    { id: "108", text: "Bagna il letto" },
    { id: "109", text: "Piagnucola" },
    { id: "110", text: "Desidera essere del sesso opposto" },
    { id: "111", text: "Chiuso in se stesso, non si coinvolge con gli altri" },
    { id: "112", text: "Si preoccupa" },
  ]
};

// Simulated OMR results
function generateSimulatedResults() {
  const results = {};
  const allItems = [...CBCL_QUESTIONS.page_4, ...CBCL_QUESTIONS.page_5];
  allItems.forEach(item => {
    const rand = Math.random();
    if (rand < 0.70) {
      // Confident
      results[item.id] = {
        value: Math.floor(Math.random() * 3),
        confidence: 0.85 + Math.random() * 0.15,
        flag: null
      };
    } else if (rand < 0.88) {
      // Uncertain
      results[item.id] = {
        value: Math.floor(Math.random() * 3),
        confidence: 0.5 + Math.random() * 0.35,
        flag: "low_confidence"
      };
    } else {
      // Missing
      results[item.id] = {
        value: null,
        confidence: 0,
        flag: "missing"
      };
    }
  });
  return results;
}

// Item Widget Component
function CBCLItem({ item, result, onValueChange }) {
  const [selected, setSelected] = useState(result?.value);
  const [isManual, setIsManual] = useState(false);

  useEffect(() => {
    setSelected(result?.value);
    setIsManual(false);
  }, [result]);

  const isConfident = result?.flag === null && result?.confidence > 0.85;
  const isUncertain = result?.flag === "low_confidence" || (result?.confidence > 0.5 && result?.confidence <= 0.85);
  const isMissing = result?.flag === "missing" || result?.value === null;

  let bgColor, borderColor, badgeText, badgeColor, badgeBg;
  if (isManual) {
    bgColor = "rgba(30, 58, 95, 0.3)";
    borderColor = "#3b82f6";
    badgeText = "✏️ Manuale";
    badgeColor = "#60a5fa";
    badgeBg = "rgba(30, 58, 138, 0.4)";
  } else if (isConfident) {
    bgColor = "rgba(13, 31, 13, 0.5)";
    borderColor = "#166534";
    badgeText = `✅ ${Math.round(result.confidence * 100)}%`;
    badgeColor = "#4ade80";
    badgeBg = "rgba(22, 101, 52, 0.3)";
  } else if (isUncertain) {
    bgColor = "rgba(31, 26, 13, 0.5)";
    borderColor = "#854d0e";
    badgeText = "⚠️ Conferma";
    badgeColor = "#fbbf24";
    badgeBg = "rgba(133, 77, 14, 0.3)";
  } else {
    bgColor = "rgba(31, 13, 13, 0.5)";
    borderColor = "#dc2626";
    badgeText = "❌ Scegli";
    badgeColor = "#f87171";
    badgeBg = "rgba(153, 27, 27, 0.3)";
  }

  const handleSelect = (val) => {
    if (isConfident && !isManual) return;
    setSelected(val);
    setIsManual(true);
    onValueChange(item.id, val);
  };

  return (
    <div style={{
      background: bgColor,
      border: `1px solid ${borderColor}`,
      borderWidth: isMissing && !isManual ? "2px" : "1px",
      borderRadius: 6,
      padding: "8px 12px",
      marginBottom: 4,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <span style={{
          fontWeight: 700,
          fontSize: 13,
          color: isMissing && !isManual ? "#ef4444" : "#e2e8f0",
          minWidth: 32,
          fontFamily: "'JetBrains Mono', monospace"
        }}>
          {item.id}.
        </span>
        <span style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.3, flex: 1 }}>
          {item.text}
        </span>
        <span style={{
          fontSize: 11,
          color: badgeColor,
          background: badgeBg,
          padding: "2px 8px",
          borderRadius: 4,
          whiteSpace: "nowrap",
          fontWeight: 600,
        }}>
          {badgeText}
        </span>
      </div>

      <div style={{ display: "flex", gap: 16, marginTop: 6, marginLeft: 40 }}>
        {[0, 1, 2].map(val => {
          const isChecked = selected === val;
          const canClick = !isConfident || isManual;
          return (
            <label key={val} style={{
              display: "flex", alignItems: "center", gap: 4,
              cursor: canClick ? "pointer" : "default",
              opacity: canClick || isChecked ? 1 : 0.5,
            }}
              onClick={() => canClick && handleSelect(val)}
            >
              <div style={{
                width: 18, height: 18,
                borderRadius: "50%",
                border: `2px solid ${isChecked ? "#818cf8" : "#475569"}`,
                background: isChecked ? "#818cf8" : "transparent",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s",
              }}>
                {isChecked && (
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: "#0f172a"
                  }} />
                )}
              </div>
              <span style={{
                fontSize: 13, fontWeight: isChecked ? 700 : 400,
                color: isChecked ? "#e2e8f0" : "#64748b",
              }}>
                {val}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

// Main App
export default function SmartOCRApp() {
  const [page, setPage] = useState("home");
  const [analysisState, setAnalysisState] = useState("idle"); // idle, running, done
  const [results, setResults] = useState({});
  const [values, setValues] = useState({});
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState("");
  const [selectedPage, setSelectedPage] = useState("page_4");
  const [photoLoaded, setPhotoLoaded] = useState(false);

  const runAnalysis = () => {
    setAnalysisState("running");
    setProgress(0);

    const phases = [
      { text: "Rilevamento bordi foglio...", p: 15, ms: 400 },
      { text: "Correzione prospettiva...", p: 30, ms: 300 },
      { text: "Pre-processing immagine...", p: 45, ms: 500 },
      { text: "Allineamento SIFT al template...", p: 65, ms: 700 },
      { text: "Estrazione celle griglia...", p: 80, ms: 300 },
      { text: "Lettura OMR + SVM ensemble...", p: 92, ms: 600 },
      { text: "Calcolo score CBCL...", p: 100, ms: 200 },
    ];

    let delay = 0;
    phases.forEach((phase) => {
      delay += phase.ms;
      setTimeout(() => {
        setProgress(phase.p);
        setProgressText(phase.text);
      }, delay);
    });

    setTimeout(() => {
      const sim = generateSimulatedResults();
      setResults(sim);
      setValues(Object.fromEntries(Object.entries(sim).map(([k, v]) => [k, v.value])));
      setAnalysisState("done");
      setPage("cbcl");
    }, delay + 300);
  };

  const handleValueChange = (itemId, val) => {
    setValues(prev => ({ ...prev, [itemId]: val }));
  };

  const totalScore = Object.values(values).reduce((sum, v) => sum + (v ?? 0), 0);
  const allItems = [...CBCL_QUESTIONS.page_4, ...CBCL_QUESTIONS.page_5];
  const completedCount = Object.values(values).filter(v => v !== null && v !== undefined).length;
  const missingCount = Object.entries(results).filter(([, r]) => r.flag === "missing").length;
  const uncertainCount = Object.entries(results).filter(([, r]) => r.flag === "low_confidence").length;

  const currentQuestions = selectedPage === "page_4" ? CBCL_QUESTIONS.page_4 : CBCL_QUESTIONS.page_5;
  const midpoint = Math.ceil(currentQuestions.length / 2);
  const leftCol = currentQuestions.slice(0, midpoint);
  const rightCol = currentQuestions.slice(midpoint);

  return (
    <div style={{
      width: "100%", minHeight: "100vh",
      background: "#0f172a",
      color: "#e2e8f0",
      fontFamily: "'Segoe UI', -apple-system, sans-serif",
      display: "flex", flexDirection: "column",
    }}>
      {/* Title bar */}
      <div style={{
        height: 44, background: "#0a0f1e",
        borderBottom: "1px solid #1e293b",
        display: "flex", alignItems: "center", padding: "0 16px",
        gap: 12,
      }}>
        <span style={{ fontSize: 20 }}>🧾</span>
        <span style={{
          fontSize: 15, fontWeight: 700,
          background: "linear-gradient(135deg, #818cf8, #c084fc)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>
          Smart OCR
        </span>
        <span style={{ fontSize: 12, color: "#475569" }}>— CBCL 6-18 Scanner</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "#334155" }}>v3.0</span>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#22c55e" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#eab308" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ef4444" }} />
        </div>
      </div>

      <div style={{ display: "flex", flex: 1 }}>
        {/* Sidebar */}
        <div style={{
          width: 180, background: "#1e293b",
          borderRight: "1px solid #334155",
          padding: "12px 8px",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {[
            { id: "home", icon: "📤", label: "Home" },
            { id: "cbcl", icon: "📋", label: "CBCL Form" },
            { id: "results", icon: "📊", label: "Risultati" },
            { id: "settings", icon: "⚙️", label: "Impostazioni" },
          ].map(item => (
            <button key={item.id} onClick={() => setPage(item.id)} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 14px", border: "none", borderRadius: 8,
              background: page === item.id ? "rgba(99, 102, 241, 0.15)" : "transparent",
              color: page === item.id ? "#818cf8" : "#94a3b8",
              fontWeight: page === item.id ? 700 : 400,
              cursor: "pointer", fontSize: 13, textAlign: "left",
              transition: "all 0.15s",
            }}>
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              {item.label}
            </button>
          ))}

          <div style={{ flex: 1 }} />
          <div style={{ padding: "8px 14px", fontSize: 11, color: "#475569", borderTop: "1px solid #334155" }}>
            <div style={{ marginBottom: 6 }}>Stato sistema</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ade80" }} />
              <span style={{ color: "#94a3b8" }}>SVM attivo</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ade80" }} />
              <span style={{ color: "#94a3b8" }}>OMR attivo</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#fbbf24" }} />
              <span style={{ color: "#94a3b8" }}>YOLO non addestrato</span>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>

          {/* HOME PAGE */}
          {page === "home" && (
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 20, color: "#f1f5f9" }}>
                Carica Questionario CBCL
              </h2>
              <div style={{ display: "flex", gap: 24 }}>
                {/* Left column */}
                <div style={{ flex: 1 }}>
                  <div style={{
                    border: "2px dashed #334155", borderRadius: 12,
                    padding: 40, textAlign: "center",
                    background: photoLoaded ? "rgba(30, 41, 59, 0.5)" : "rgba(15, 23, 42, 0.5)",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                    onClick={() => setPhotoLoaded(true)}
                  >
                    {!photoLoaded ? (
                      <>
                        <div style={{ fontSize: 48, marginBottom: 12 }}>📸</div>
                        <div style={{ color: "#94a3b8", fontSize: 14 }}>
                          Clicca per caricare una foto del questionario CBCL
                        </div>
                        <div style={{ color: "#475569", fontSize: 12, marginTop: 8 }}>
                          JPG, PNG — Foto da smartphone su sfondo scuro
                        </div>
                      </>
                    ) : (
                      <div>
                        <div style={{
                          width: "100%", height: 300, background: "#1e293b",
                          borderRadius: 8, display: "flex", alignItems: "center",
                          justifyContent: "center", position: "relative", overflow: "hidden",
                        }}>
                          {/* Simulated photo with yellow boundary */}
                          <div style={{
                            width: "70%", height: "85%", background: "#d4d4d8",
                            border: "3px solid #eab308",
                            borderRadius: 2,
                            position: "relative",
                            transform: "perspective(500px) rotateY(-2deg) rotateX(1deg)",
                          }}>
                            <div style={{
                              position: "absolute", top: -8, left: -8,
                              width: 16, height: 16, borderRadius: "50%",
                              background: "#ef4444", border: "2px solid #0f172a",
                            }} />
                            <div style={{
                              position: "absolute", top: -8, right: -8,
                              width: 16, height: 16, borderRadius: "50%",
                              background: "#ef4444", border: "2px solid #0f172a",
                            }} />
                            <div style={{
                              position: "absolute", bottom: -8, left: -8,
                              width: 16, height: 16, borderRadius: "50%",
                              background: "#ef4444", border: "2px solid #0f172a",
                            }} />
                            <div style={{
                              position: "absolute", bottom: -8, right: -8,
                              width: 16, height: 16, borderRadius: "50%",
                              background: "#ef4444", border: "2px solid #0f172a",
                            }} />
                            <div style={{
                              padding: 12, fontSize: 8, color: "#475569",
                              lineHeight: 1.6,
                            }}>
                              CBCL 6-18<br />
                              Questionario sul Comportamento<br />
                              del Bambino (6-18 anni)<br /><br />
                              0 1 2 — Item 1...<br />
                              0 1 2 — Item 2...<br />
                              0 1 2 — Item 3...
                            </div>
                          </div>
                          <div style={{
                            position: "absolute", bottom: 8, left: 8,
                            fontSize: 11, color: "#eab308",
                            background: "rgba(0,0,0,0.7)", padding: "2px 8px",
                            borderRadius: 4,
                          }}>
                            🟡 Bordi rilevati: threshold (conf: 92%)
                          </div>
                        </div>
                        <div style={{ color: "#4ade80", fontSize: 13, marginTop: 8 }}>
                          ✅ CBCL_pagina4_foto1.jpg caricata
                        </div>
                      </div>
                    )}
                  </div>

                  {photoLoaded && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ marginBottom: 12 }}>
                        <label style={{ fontSize: 13, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                          Pagina questionario
                        </label>
                        <div style={{ display: "flex", gap: 8 }}>
                          {["page_4", "page_5"].map(p => (
                            <button key={p} onClick={() => setSelectedPage(p)} style={{
                              padding: "8px 16px", borderRadius: 6,
                              border: selectedPage === p ? "2px solid #818cf8" : "1px solid #334155",
                              background: selectedPage === p ? "rgba(99,102,241,0.15)" : "#1e293b",
                              color: selectedPage === p ? "#818cf8" : "#94a3b8",
                              cursor: "pointer", fontSize: 13,
                            }}>
                              {p === "page_4" ? "📄 Pag. 4 (items 1-54)" : "📄 Pag. 5 (items 55-112)"}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div style={{ marginBottom: 12 }}>
                        <label style={{ fontSize: 13, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                          Modelli
                        </label>
                        <div style={{ display: "flex", gap: 12 }}>
                          {["OMR Pixel", "SVM (HOG)", "Ensemble (entrambi)"].map((m, i) => (
                            <label key={m} style={{
                              display: "flex", alignItems: "center", gap: 6,
                              fontSize: 12, color: "#cbd5e1", cursor: "pointer",
                            }}>
                              <input type="radio" name="model" defaultChecked={i === 2}
                                style={{ accentColor: "#818cf8" }} />
                              {m}
                            </label>
                          ))}
                        </div>
                      </div>

                      <button onClick={runAnalysis} style={{
                        width: "100%", padding: "14px 24px",
                        background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                        color: "white", border: "none", borderRadius: 10,
                        fontSize: 16, fontWeight: 700, cursor: "pointer",
                        boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
                        transition: "all 0.2s",
                      }}>
                        🔍 ANALIZZA QUESTIONARIO
                      </button>
                    </div>
                  )}
                </div>

                {/* Right column */}
                <div style={{ flex: 1 }}>
                  {analysisState === "running" && (
                    <div style={{
                      background: "#1e293b", borderRadius: 12, padding: 24,
                      border: "1px solid #334155",
                    }}>
                      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: "#f1f5f9" }}>
                        Analisi in corso...
                      </div>
                      <div style={{
                        height: 8, background: "#0f172a", borderRadius: 4,
                        overflow: "hidden", marginBottom: 12,
                      }}>
                        <div style={{
                          height: "100%", width: `${progress}%`,
                          background: "linear-gradient(90deg, #6366f1, #818cf8)",
                          borderRadius: 4, transition: "width 0.3s ease",
                        }} />
                      </div>
                      <div style={{ fontSize: 12, color: "#94a3b8" }}>{progressText}</div>
                    </div>
                  )}

                  {analysisState === "done" && (
                    <div style={{
                      background: "#1e293b", borderRadius: 12, padding: 24,
                      border: "1px solid #334155",
                    }}>
                      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: "#4ade80" }}>
                        ✅ Analisi completata
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                        <div style={{ background: "#0f172a", borderRadius: 8, padding: 12, textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 800, color: "#818cf8" }}>{totalScore}</div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>Score Totale</div>
                        </div>
                        <div style={{ background: "#0f172a", borderRadius: 8, padding: 12, textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 800, color: "#4ade80" }}>{completedCount}</div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>Items Letti</div>
                        </div>
                        <div style={{ background: "#0f172a", borderRadius: 8, padding: 12, textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 800, color: "#fbbf24" }}>{uncertainCount}</div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>Da Confermare</div>
                        </div>
                        <div style={{ background: "#0f172a", borderRadius: 8, padding: 12, textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 800, color: "#f87171" }}>{missingCount}</div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>Mancanti</div>
                        </div>
                      </div>
                      <div style={{ marginTop: 12, fontSize: 12, color: "#94a3b8", textAlign: "center" }}>
                        Tempo: 1.8s | Metodo: Ensemble (OMR + SVM) | Alignment: SIFT+ECC
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* CBCL FORM PAGE */}
          {page === "cbcl" && (
            <div>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                marginBottom: 16,
              }}>
                <h2 style={{ fontSize: 20, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>
                  📋 CBCL 6-18 — {selectedPage === "page_4" ? "Pagina 4 (Items 1-54)" : "Pagina 5 (Items 55-112)"}
                </h2>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => setSelectedPage("page_4")} style={{
                    padding: "6px 14px", borderRadius: 6, fontSize: 12,
                    border: selectedPage === "page_4" ? "2px solid #818cf8" : "1px solid #334155",
                    background: selectedPage === "page_4" ? "rgba(99,102,241,0.15)" : "#1e293b",
                    color: selectedPage === "page_4" ? "#818cf8" : "#64748b",
                    cursor: "pointer",
                  }}>Pag. 4</button>
                  <button onClick={() => setSelectedPage("page_5")} style={{
                    padding: "6px 14px", borderRadius: 6, fontSize: 12,
                    border: selectedPage === "page_5" ? "2px solid #818cf8" : "1px solid #334155",
                    background: selectedPage === "page_5" ? "rgba(99,102,241,0.15)" : "#1e293b",
                    color: selectedPage === "page_5" ? "#818cf8" : "#64748b",
                    cursor: "pointer",
                  }}>Pag. 5</button>
                  <button style={{
                    padding: "6px 14px", borderRadius: 6, fontSize: 12,
                    border: "1px solid #334155", background: "#1e293b",
                    color: "#94a3b8", cursor: "pointer",
                  }}>📥 Esporta CSV</button>
                </div>
              </div>

              {/* Legend */}
              <div style={{
                display: "flex", gap: 20, marginBottom: 12,
                padding: "8px 16px", background: "#1e293b",
                borderRadius: 8, fontSize: 11,
              }}>
                <span><span style={{ color: "#4ade80" }}>●</span> Confidente (auto)</span>
                <span><span style={{ color: "#fbbf24" }}>●</span> Incerto (conferma)</span>
                <span><span style={{ color: "#f87171" }}>●</span> Mancante (scegli)</span>
                <span><span style={{ color: "#60a5fa" }}>●</span> Corretto manualmente</span>
              </div>

              {/* Two columns */}
              <div style={{ display: "flex", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  {leftCol.map(item => (
                    <CBCLItem
                      key={item.id}
                      item={item}
                      result={results[item.id]}
                      onValueChange={handleValueChange}
                    />
                  ))}
                </div>
                <div style={{ flex: 1 }}>
                  {rightCol.map(item => (
                    <CBCLItem
                      key={item.id}
                      item={item}
                      result={results[item.id]}
                      onValueChange={handleValueChange}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* RESULTS PAGE */}
          {page === "results" && analysisState === "done" && (
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 20, color: "#f1f5f9" }}>
                📊 Risultati CBCL
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
                <div style={{
                  background: "#1e293b", borderRadius: 12, padding: 20,
                  border: "1px solid #334155", textAlign: "center",
                }}>
                  <div style={{ fontSize: 42, fontWeight: 800, color: "#818cf8" }}>{totalScore}</div>
                  <div style={{ color: "#94a3b8", fontSize: 13 }}>Score Totale</div>
                </div>
                <div style={{
                  background: "#1e293b", borderRadius: 12, padding: 20,
                  border: "1px solid #334155", textAlign: "center",
                }}>
                  <div style={{ fontSize: 42, fontWeight: 800, color: "#4ade80" }}>
                    {completedCount}/{allItems.length}
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: 13 }}>Items Completati</div>
                </div>
                <div style={{
                  background: "#1e293b", borderRadius: 12, padding: 20,
                  border: "1px solid #334155", textAlign: "center",
                }}>
                  <div style={{ fontSize: 42, fontWeight: 800, color: "#fbbf24" }}>1.8s</div>
                  <div style={{ color: "#94a3b8", fontSize: 13 }}>Tempo Analisi</div>
                </div>
              </div>

              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#e2e8f0" }}>
                Subscale DSM-Oriented
              </h3>
              <div style={{ background: "#1e293b", borderRadius: 12, border: "1px solid #334155", overflow: "hidden" }}>
                {[
                  { name: "Affective Problems", score: 7, max: 14 },
                  { name: "Anxiety Problems", score: 5, max: 22 },
                  { name: "Somatic Problems", score: 3, max: 10 },
                  { name: "ADHD Problems", score: 9, max: 18 },
                  { name: "Oppositional Defiant", score: 6, max: 14 },
                  { name: "Conduct Problems", score: 4, max: 30 },
                  { name: "Internalizing", score: 22, max: 64 },
                  { name: "Externalizing", score: 18, max: 54 },
                ].map((sub, i) => (
                  <div key={sub.name} style={{
                    display: "flex", alignItems: "center", gap: 16,
                    padding: "12px 16px",
                    borderBottom: i < 7 ? "1px solid #334155" : "none",
                  }}>
                    <span style={{ width: 180, fontSize: 13, color: "#cbd5e1" }}>{sub.name}</span>
                    <div style={{ flex: 1, height: 8, background: "#0f172a", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{
                        height: "100%", width: `${(sub.score / sub.max) * 100}%`,
                        background: sub.score / sub.max > 0.6 ? "#ef4444" : sub.score / sub.max > 0.3 ? "#eab308" : "#22c55e",
                        borderRadius: 4,
                      }} />
                    </div>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", width: 50, textAlign: "right" }}>
                      {sub.score}/{sub.max}
                    </span>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
                <button style={{
                  padding: "10px 20px", background: "#6366f1", color: "white",
                  border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600,
                }}>📥 Esporta CSV</button>
                <button style={{
                  padding: "10px 20px", background: "#1e293b", color: "#94a3b8",
                  border: "1px solid #334155", borderRadius: 8, cursor: "pointer", fontSize: 13,
                }}>📄 Esporta JSON</button>
                <button style={{
                  padding: "10px 20px", background: "#1e293b", color: "#94a3b8",
                  border: "1px solid #334155", borderRadius: 8, cursor: "pointer", fontSize: 13,
                }}>🖨 Stampa Report</button>
              </div>
            </div>
          )}

          {page === "results" && analysisState !== "done" && (
            <div style={{ textAlign: "center", padding: 60, color: "#475569" }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
              <div style={{ fontSize: 15 }}>Analizza prima un questionario dalla pagina Home</div>
            </div>
          )}

          {/* SETTINGS PAGE */}
          {page === "settings" && (
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 20, color: "#f1f5f9" }}>
                ⚙️ Impostazioni
              </h2>
              <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, border: "1px solid #334155", maxWidth: 500 }}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 13, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                    Soglia confidence minima
                  </label>
                  <input type="range" min="50" max="95" defaultValue="85" style={{ width: "100%", accentColor: "#818cf8" }} />
                  <div style={{ fontSize: 11, color: "#475569", textAlign: "right" }}>85%</div>
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 13, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                    Soglia mark minima (fill ratio)
                  </label>
                  <input type="range" min="5" max="25" defaultValue="12" style={{ width: "100%", accentColor: "#818cf8" }} />
                  <div style={{ fontSize: 11, color: "#475569", textAlign: "right" }}>12%</div>
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 13, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                    Modello boundary detection
                  </label>
                  <select style={{
                    width: "100%", padding: 8, background: "#0f172a",
                    border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0",
                  }}>
                    <option>Threshold + Morphology (raccomandato)</option>
                    <option>DocAligner ONNX (neurale)</option>
                    <option>Auto (threshold → DocAligner fallback)</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#94a3b8", cursor: "pointer" }}>
                    <input type="checkbox" defaultChecked style={{ accentColor: "#818cf8" }} />
                    Mostra bordino giallo (overlay bordi rilevati)
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        height: 32, background: "#1e293b",
        borderTop: "1px solid #334155",
        display: "flex", alignItems: "center",
        padding: "0 16px", gap: 24,
        fontSize: 11, color: "#64748b",
      }}>
        <span>🟢 Pronto</span>
        <span>Modelli: OMR + SVM (ensemble)</span>
        <span>Alignment: SIFT + ECC</span>
        {analysisState === "done" && <span>Score: {totalScore} | Items: {completedCount}/{allItems.length}</span>}
        <div style={{ flex: 1 }} />
        <span>Smart OCR v3.0 — CBCL 6-18</span>
      </div>
    </div>
  );
}
