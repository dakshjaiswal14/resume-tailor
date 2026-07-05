"use client";

import { useState, useCallback, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeSummary {
  resume_id: string;
  filename: string;
  display_name: string;
  companies: string[];
  bullet_count: number;
  skill_count: number;
  uploaded_at: string;
}

interface ParsedResume {
  resume_id: string;
  skills: string[];
  experience: { id: string; company: string; role: string; duration?: string; bullets: { id: string; text: string; raw_latex?: string }[] }[];
  projects: { id: string; name: string; bullets: { id: string; text: string; raw_latex?: string }[] }[];
  education: { id: string; institution: string; degree: string; details?: string }[];
}

interface Suggestion {
  bullet_id: string;
  section: string;
  parent: string;
  original_text: string;
  suggested_text: string;
  added_keywords: string[];
  reason: string;
  confidence: "high" | "medium" | "low";
}

interface JDResult {
  resume_id: string;
  jd_keywords: string[];
  missing_keywords: string[];
  suggestions: Suggestion[];
  source: string;
}

interface ApplyResult {
  updated_tex_path: string;
  applied_count: number;
  applied_suggestions: { bullet_id: string; status: string }[];
}

type Step = "resume" | "jd" | "review" | "result";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const confColor = (c: string) => {
  switch (c) {
    case "high": return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "medium": return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
    default: return "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300";
  }
};

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
export default function Home() {
  const [step, setStep] = useState<Step>("resume");

  // resume list
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);

  // upload
  const [latexCode, setLatexCode] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeFileName, setResumeFileName] = useState("");
  const [customFilename, setCustomFilename] = useState("");
  const [parsedResume, setParsedResume] = useState<ParsedResume | null>(null);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [resumeError, setResumeError] = useState("");

  // jd
  const [jdText, setJdText] = useState("");
  const [jdResult, setJdResult] = useState<JDResult | null>(null);
  const [jdLoading, setJdLoading] = useState(false);
  const [jdError, setJdError] = useState("");

  // suggestions
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());

  // result
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [tailoredTex, setTailoredTex] = useState("");
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [copied, setCopied] = useState(false);

  // cover letter
  const [coverLetterText, setCoverLetterText] = useState("");
  const [coverLoading, setCoverLoading] = useState(false);
  const [coverError, setCoverError] = useState("");
  const [coverCopied, setCoverCopied] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  // candidate name
  const [candidateName, setCandidateName] = useState("");
  const [candidateLoading, setCandidateLoading] = useState(true);

  // delete
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [clearAllConfirm, setClearAllConfirm] = useState(false);

  // ---- load initial data ----
  useEffect(() => {
    fetchResumeList();
    fetchCandidateName();
  }, []);

  const fetchCandidateName = async () => {
    try {
      const res = await fetch(`${API_BASE}/resume/config/candidate-name`);
      if (res.ok) setCandidateName((await res.json()).candidate_name);
    } catch { /* ignore */ }
    setCandidateLoading(false);
  };

  const saveCandidateName = async (name: string) => {
    setCandidateName(name);
    try {
      await fetch(`${API_BASE}/resume/config/candidate-name`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: name }),
      });
    } catch { /* ignore */ }
  };

  const fetchResumeList = async () => {
    setListLoading(true);
    try { const res = await fetch(`${API_BASE}/resume/list`); if (res.ok) setResumes(await res.json()); } catch { /* ignore */ }
    setListLoading(false);
  };

  // ---- actions ----
  const handleSelectResume = async (id: string) => {
    setResumeLoading(true); setResumeError("");
    try {
      const res = await fetch(`${API_BASE}/resume/parsed/${id}`);
      if (!res.ok) throw new Error("Failed");
      setParsedResume(await res.json());
      setStep("jd");
    } catch (e: any) { setResumeError(e.message); }
    finally { setResumeLoading(false); }
  };

  const handleDeleteResume = async (id: string) => {
    try { await fetch(`${API_BASE}/resume/${id}`, { method: "DELETE" }); } catch { /* ignore */ }
    setResumes((p) => p.filter((r) => r.resume_id !== id));
    if (parsedResume?.resume_id === id) { setParsedResume(null); setStep("resume"); }
    setDeleteTarget(null);
  };

  const handleClearAll = async () => {
    try { await fetch(`${API_BASE}/resume/admin/clear-all`, { method: "DELETE" }); } catch { /* ignore */ }
    setResumes([]);
    setParsedResume(null);
    setStep("resume");
    setClearAllConfirm(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setResumeFile(f);
      setResumeFileName(f.name);
      // Auto-fill filename from uploaded file (strip .tex extension)
      const base = f.name.replace(/\.tex$/i, "");
      setCustomFilename(base);
      setResumeError("");
    }
  };

  const handleParseResume = useCallback(async () => {
    if (!resumeFile && !latexCode.trim()) { setResumeError("Please paste LaTeX or upload a .tex file."); return; }
    if (!customFilename.trim() && !resumeFile) { setResumeError("Please provide a filename."); return; }
    setResumeLoading(true); setResumeError("");
    try {
      // Use custom filename or fall back to uploaded file's name
      const fname = customFilename.trim() || (resumeFile ? resumeFile.name.replace(/\.tex$/i, "") : "resume");
      let form = new FormData();
      if (resumeFile) form.append("tex_file", resumeFile);
      else form.append("tex_file", new Blob([latexCode], { type: "text/plain" }), fname + ".tex");
      form.append("custom_filename", fname);
      const res = await fetch(`${API_BASE}/resume/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
      const data = await res.json();
      setParsedResume({ resume_id: data.resume_id, skills: [], experience: [], projects: [], education: [] });
      fetchResumeList();
      setStep("jd");
    } catch (e: any) { setResumeError(e.message || "Failed"); }
    finally { setResumeLoading(false); }
  }, [latexCode, resumeFile]);

  const handleAnalyzeJD = useCallback(async () => {
    if (!jdText.trim()) { setJdError("Please paste a job description."); return; }
    if (!parsedResume) { setJdError("Select a resume first."); return; }
    setJdLoading(true); setJdError("");
    try {
      const res = await fetch(`${API_BASE}/jd/suggest-rewrites`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_id: parsedResume.resume_id, jd_text: jdText }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Analysis failed");
      const data: JDResult = await res.json();
      setJdResult(data);
      setAcceptedIds(new Set(data.suggestions.map((s) => s.bullet_id)));
      setRejectedIds(new Set());
      setStep("review");
    } catch (e: any) { setJdError(e.message); }
    finally { setJdLoading(false); }
  }, [jdText, parsedResume]);

  const toggleAccept = (id: string) => {
    setAcceptedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); setRejectedIds((r) => new Set([...r, id])); }
      else { next.add(id); setRejectedIds((r) => { const nr = new Set(r); nr.delete(id); return nr; }); }
      return next;
    });
  };

  const handleApply = useCallback(async () => {
    if (!parsedResume || !jdResult) return;
    const accepted = jdResult.suggestions.filter((s) => acceptedIds.has(s.bullet_id)).map((s) => ({ bullet_id: s.bullet_id, new_text: s.suggested_text }));
    if (accepted.length === 0) { setApplyError("No suggestions accepted."); return; }
    setApplyLoading(true); setApplyError("");
    try {
      const res = await fetch(`${API_BASE}/resume/apply-suggestions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_id: parsedResume.resume_id, accepted_suggestions: accepted }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Apply failed");
      const data: ApplyResult = await res.json();
      setApplyResult(data);
      try {
        const tr = await fetch(`${API_BASE}/resume/generated/${parsedResume.resume_id}_tailored.tex`);
        setTailoredTex(tr.ok ? await tr.text() : "% Could not load");
      } catch { setTailoredTex("% Could not load"); }
      setStep("result");
    } catch (e: any) { setApplyError(e.message); }
    finally { setApplyLoading(false); }
  }, [parsedResume, jdResult, acceptedIds]);

  const handleGenerateCoverLetter = async () => {
    if (!parsedResume) return;
    setCoverLoading(true); setCoverError("");
    try {
      const res = await fetch(`${API_BASE}/resume/${parsedResume.resume_id}/cover-letter`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText, company_name: "", hiring_manager: "Hiring Manager", candidate_name: candidateName }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Failed");
      setCoverLetterText((await res.json()).text);
    } catch (e: any) { setCoverError(e.message); }
    finally { setCoverLoading(false); }
  };

  const handleDownloadCoverPDF = async () => {
    if (!parsedResume || !coverLetterText) return;
    setPdfLoading(true);
    try {
      const res = await fetch(`${API_BASE}/resume/${parsedResume.resume_id}/cover-letter/pdf`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: coverLetterText }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "PDF failed");
      const data = await res.json();
      // Decode base64 and download
      const raw = Uint8Array.from(atob(data.pdf_base64), (c) => c.charCodeAt(0));
      const blob = new Blob([raw], { type: "application/pdf" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "cover_letter.pdf";
      a.click();
    } catch (e: any) { setCoverError(e.message); }
    finally { setPdfLoading(false); }
  };

  const handleCopy = async (text: string, setter: (v: boolean) => void) => {
    await navigator.clipboard.writeText(text); setter(true); setTimeout(() => setter(false), 2000);
  };

  const handleDownload = (tex: string, filename: string) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([tex], { type: "text/plain" }));
    a.download = filename; a.click();
  };

  const handleReset = () => {
    setStep("resume"); setLatexCode(""); setResumeFile(null); setResumeFileName(""); setCustomFilename("");
    setParsedResume(null); setJdText(""); setJdResult(null);
    setAcceptedIds(new Set()); setRejectedIds(new Set());
    setApplyResult(null); setTailoredTex("");
    setCoverLetterText(""); setCoverError(""); setApplyError(""); setResumeError(""); setJdError("");
    fetchResumeList();
  };

  // ---- step indicator ----
  const steps: Step[] = ["resume", "jd", "review", "result"];
  const stepLabels: Record<Step, string> = { resume: "Resume", jd: "Job Desc", review: "Review", result: "Download" };

  // ---- render ----
  return (
    <div className="flex-1 flex flex-col items-center px-4 py-8">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">RoleTailor <span className="text-indigo-600">AI</span></h1>
        <p className="text-zinc-500 mt-1 text-sm">Tailor your LaTeX resume & cover letter to any job description</p>
        {/* Candidate name */}
        <div className="mt-4 flex items-center justify-center gap-2">
          <label className="text-xs text-zinc-400 font-medium">Candidate:</label>
          <input
            type="text"
            className="w-48 px-3 py-1.5 text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 text-center focus:ring-2 focus:ring-indigo-500 outline-none"
            placeholder="Your Name"
            value={candidateName}
            onChange={(e) => saveCandidateName(e.target.value)}
          />
        </div>
      </header>

      <div className="w-full max-w-3xl">
        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                step === s ? "bg-indigo-600 text-white" : steps.indexOf(step) > i ? "bg-emerald-500 text-white" : "bg-zinc-200 dark:bg-zinc-700 text-zinc-500"
              }`}>{steps.indexOf(step) > i ? "✓" : i + 1}</div>
              <span className={`text-sm hidden sm:inline ${step === s ? "text-indigo-600 font-medium" : "text-zinc-400"}`}>{stepLabels[s]}</span>
              {i < 3 && <div className="w-8 h-px bg-zinc-300 dark:bg-zinc-600 hidden sm:block" />}
            </div>
          ))}
        </div>

        {/* STEP 1: Library + Upload */}
        {step === "resume" && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-lg font-semibold">Your Resumes</h2>
                {resumes.length > 0 && (
                  <button onClick={() => setClearAllConfirm(true)}
                    className="text-xs text-red-500 hover:text-red-600 font-medium px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-950 transition-colors">
                    Clear All
                  </button>
                )}
              </div>
              <p className="text-sm text-zinc-500 mb-4">Select a resume or add a new one below.</p>
              {listLoading ? <div className="flex items-center gap-2 text-sm text-zinc-400"><Spinner /> Loading...</div>
               : resumes.length === 0 ? <p className="text-sm text-zinc-400 italic">No resumes yet. Upload your first one below.</p>
               : <div className="grid gap-3 sm:grid-cols-2">
                  {resumes.map((r) => (
                    <div key={r.resume_id} onClick={() => handleSelectResume(r.resume_id)}
                      className="relative group border border-zinc-200 dark:border-zinc-700 rounded-lg p-4 hover:border-indigo-400 cursor-pointer transition-colors bg-zinc-50 dark:bg-zinc-950">
                      <button onClick={(e) => { e.stopPropagation(); setDeleteTarget(r.resume_id); }}
                        className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded-full text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 opacity-0 group-hover:opacity-100 transition-opacity" title="Delete">&times;</button>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate mb-1.5">{r.display_name}</p>
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {r.companies.slice(0, 3).map((c) => <span key={c} className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">{c}</span>)}
                        {r.companies.length > 3 && <span className="text-xs text-zinc-400">+{r.companies.length - 3}</span>}
                      </div>
                      <div className="text-xs text-zinc-400">{r.bullet_count} bullets &middot; {r.skill_count} skills<br />{new Date(r.uploaded_at).toLocaleDateString()}</div>
                    </div>
                  ))}
                </div>
              }
            </div>

            {/* Delete single modal */}
            {deleteTarget && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDeleteTarget(null)}>
                <div className="bg-white dark:bg-zinc-900 rounded-xl p-6 shadow-xl border border-zinc-200 max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-lg font-semibold mb-2">Delete Resume?</h3>
                  <p className="text-sm text-zinc-500 mb-4">This deletes the master .tex, parsed data, and all generated files.</p>
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => setDeleteTarget(null)} className="px-4 py-2 text-sm rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200">Cancel</button>
                    <button onClick={() => handleDeleteResume(deleteTarget)} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">Delete</button>
                  </div>
                </div>
              </div>
            )}

            {/* Clear All modal */}
            {clearAllConfirm && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setClearAllConfirm(false)}>
                <div className="bg-white dark:bg-zinc-900 rounded-xl p-6 shadow-xl border border-zinc-200 max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-lg font-semibold mb-2">Clear All Data?</h3>
                  <p className="text-sm text-zinc-500 mb-4">This will permanently delete <strong>all</strong> master resumes, parsed data, and generated files. This cannot be undone.</p>
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => setClearAllConfirm(false)} className="px-4 py-2 text-sm rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200">Cancel</button>
                    <button onClick={handleClearAll} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">Clear Everything</button>
                  </div>
                </div>
              </div>
            )}

            {/* Upload */}
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold mb-1">Add New Resume</h2>
              <p className="text-sm text-zinc-500 mb-4">Upload a <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1 rounded">.tex</code> file or paste LaTeX.</p>
              <div className="mb-4">
                <label className={`flex flex-col items-center justify-center w-full h-28 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                  resumeFileName ? "border-emerald-400 bg-emerald-50 dark:bg-emerald-950/20" : "border-zinc-300 dark:border-zinc-700 hover:border-indigo-400 bg-zinc-50 dark:bg-zinc-950"
                }`}>
                  <input type="file" accept=".tex,text/plain" onChange={handleFileChange} className="hidden" />
                  {resumeFileName ? (
                    <div className="text-center"><span className="text-emerald-600 font-medium text-sm">&check; {resumeFileName}</span>
                      <button type="button" onClick={(e) => { e.preventDefault(); setResumeFile(null); setResumeFileName(""); }} className="block text-xs text-zinc-400 hover:text-red-500 mt-1 mx-auto">Remove</button></div>
                  ) : <div className="text-center"><svg className="mx-auto h-8 w-8 text-zinc-400 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                    <span className="text-sm text-zinc-500"><span className="text-indigo-600 font-medium">Upload a .tex file</span> or drag & drop</span></div>}
                </label>
              </div>
              {/* Filename input */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Resume Name</label>
                <input type="text"
                  className="w-full px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg bg-zinc-50 dark:bg-zinc-950 focus:ring-2 focus:ring-indigo-500 outline-none"
                  placeholder="e.g. daksh_backend_resume"
                  value={customFilename}
                  onChange={(e) => setCustomFilename(e.target.value)}
                />
                <p className="text-xs text-zinc-400 mt-1">Auto-filled from file name. Edit if needed. Required for pasted LaTeX.</p>
              </div>

              <div className="flex items-center gap-3 mb-4"><div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" /><span className="text-xs text-zinc-400 font-medium">OR paste LaTeX</span><div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" /></div>
              <textarea className="w-full h-40 p-4 font-mono text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg bg-zinc-50 dark:bg-zinc-950 resize-y focus:ring-2 focus:ring-indigo-500 outline-none"
                placeholder="\\documentclass[letterpaper,11pt]{article}% ... paste LaTeX ..." value={latexCode} onChange={(e) => setLatexCode(e.target.value)} disabled={!!resumeFile} />
              {resumeError && <p className="text-red-600 text-sm mt-2">{resumeError}</p>}
              <button onClick={handleParseResume} disabled={resumeLoading} className="mt-4 w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
                {resumeLoading ? <><Spinner /> Parsing...</> : "Parse Resume →"}
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: JD */}
        {step === "jd" && (
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
            <div className="flex justify-between mb-1"><h2 className="text-lg font-semibold">Paste Job Description</h2><button onClick={() => setStep("resume")} className="text-sm text-zinc-400 hover:text-zinc-600">&larr; Back</button></div>
            <p className="text-sm text-zinc-500 mb-4">We'll extract keywords and match them against your resume.</p>
            <textarea className="w-full h-64 p-4 text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg bg-zinc-50 dark:bg-zinc-950 resize-y focus:ring-2 focus:ring-indigo-500 outline-none"
              placeholder="Paste the job description here..." value={jdText} onChange={(e) => setJdText(e.target.value)} />
            {jdError && <p className="text-red-600 text-sm mt-2">{jdError}</p>}
            <button onClick={handleAnalyzeJD} disabled={jdLoading} className="mt-4 w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
              {jdLoading ? <><Spinner /> Analyzing...</> : "Analyze & Get Suggestions →"}
            </button>
          </div>
        )}

        {/* STEP 3: Review */}
        {step === "review" && jdResult && (
          <div className="space-y-4">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <div className="flex justify-between"><div><h2 className="text-lg font-semibold">Review Suggestions</h2><p className="text-sm text-zinc-500">{jdResult.suggestions.length} suggestions &middot; {acceptedIds.size} accepted &middot; {rejectedIds.size} rejected</p></div><button onClick={() => setStep("jd")} className="text-sm text-zinc-400 hover:text-zinc-600">&larr; Back</button></div>
              {jdResult.missing_keywords.length > 0 && <div className="mt-4 flex flex-wrap gap-2"><span className="text-xs text-zinc-500 font-medium">Missing:</span>{jdResult.missing_keywords.map((kw) => <span key={kw} className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{kw}</span>)}</div>}
            </div>
            {jdResult.suggestions.map((s) => {
              const ok = acceptedIds.has(s.bullet_id), no = rejectedIds.has(s.bullet_id);
              return (
                <div key={s.bullet_id} className={`bg-white dark:bg-zinc-900 border rounded-xl p-5 shadow-sm ${ok ? "border-emerald-300 ring-1 ring-emerald-200" : no ? "border-red-200 opacity-60" : "border-zinc-200 dark:border-zinc-800"}`}>
                  <div className="flex items-center gap-3 mb-3 flex-wrap">
                    <span className="text-xs font-mono text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">{s.bullet_id}</span>
                    <span className="text-xs text-zinc-500">{s.parent} &middot; {s.section}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${confColor(s.confidence)}`}>{s.confidence}</span>
                  </div>
                  <div className="mb-3"><span className="text-xs font-medium text-zinc-400 uppercase">Original</span><p className="text-sm text-zinc-500 mt-1 line-through">{s.original_text}</p></div>
                  <div className="mb-3"><span className="text-xs font-medium text-emerald-600 uppercase">Suggested</span><p className="text-sm text-zinc-900 dark:text-zinc-100 mt-1">{s.suggested_text}</p></div>
                  {s.added_keywords.length > 0 && <div className="flex flex-wrap gap-1 mb-2">{s.added_keywords.map((kw) => <span key={kw} className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">+ {kw}</span>)}</div>}
                  <p className="text-xs text-zinc-400 mb-4">{s.reason}</p>
                  <div className="flex gap-2">
                    <button onClick={() => toggleAccept(s.bullet_id)} className={`px-4 py-2 text-sm font-medium rounded-lg ${ok ? "bg-emerald-600 text-white" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 hover:bg-zinc-200"}`}>{ok ? "✓ Accepted" : "Accept"}</button>
                    <button onClick={() => toggleAccept(s.bullet_id)} className={`px-4 py-2 text-sm font-medium rounded-lg ${no ? "bg-red-600 text-white" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 hover:bg-zinc-200"}`}>{no ? "✗ Rejected" : "Reject"}</button>
                  </div>
                </div>
              );
            })}
            <div className="sticky bottom-4 bg-white dark:bg-zinc-900 border border-zinc-200 rounded-xl p-4 shadow-lg">
              {applyError && <p className="text-red-600 text-sm mb-3">{applyError}</p>}
              <button onClick={handleApply} disabled={applyLoading || acceptedIds.size === 0} className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-lg flex items-center justify-center gap-2">
                {applyLoading ? <><Spinner /> Applying...</> : `Apply ${acceptedIds.size} Change${acceptedIds.size !== 1 ? "s" : ""} →`}
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: Result */}
        {step === "result" && (
          <div className="space-y-4">
            <div className="bg-white dark:bg-zinc-900 border border-emerald-200 dark:border-emerald-800 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold">&check; Tailored Resume Ready</h2>
              <p className="text-sm text-zinc-500 mt-1">{applyResult?.applied_count || 0} bullets updated</p>
            </div>
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-semibold">Tailored Resume LaTeX</h3>
                <div className="flex gap-2">
                  <button onClick={() => handleCopy(tailoredTex, setCopied)} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200">{copied ? "✓ Copied!" : "Copy"}</button>
                  <button onClick={() => handleDownload(tailoredTex, "resume_tailored.tex")} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Download .tex</button>
                </div>
              </div>
              <pre className="max-h-80 overflow-auto p-4 bg-zinc-950 text-zinc-300 text-xs font-mono rounded-lg">{tailoredTex || "Loading..."}</pre>
            </div>
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-semibold">Cover Letter</h3>
                {coverLetterText ? <div className="flex gap-2">
                  <button onClick={() => handleCopy(coverLetterText, setCoverCopied)} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200">{coverCopied ? "✓ Copied!" : "Copy Text"}</button>
                  <button onClick={handleDownloadCoverPDF} disabled={pdfLoading} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400 flex items-center gap-1">{pdfLoading ? <><Spinner /> PDF...</> : "Download PDF"}</button>
                </div> : <button onClick={handleGenerateCoverLetter} disabled={coverLoading} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-400 flex items-center gap-1">{coverLoading ? <><Spinner /> Generating...</> : "Generate Cover Letter"}</button>}
              </div>
              {coverError && <p className="text-red-600 text-sm mb-2">{coverError}</p>}
              {coverLetterText ? (
                <div className="max-h-80 overflow-auto p-4 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm text-zinc-900 dark:text-zinc-100 whitespace-pre-wrap font-sans leading-relaxed">{coverLetterText}</div>
              ) : <p className="text-sm text-zinc-400 italic">Click "Generate Cover Letter" to create one based on your resume and the JD.</p>}
            </div>
            <button onClick={handleReset} className="w-full py-3 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 text-zinc-700 font-medium rounded-lg">Start Over</button>
          </div>
        )}
      </div>
    </div>
  );
}
