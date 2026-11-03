import { useState } from "react";
import {
  PlusCircle,
  Trash2,
  Send,
  AlertCircle,
  BookOpen,
  Sparkles,
  Bot,
  Info,
  CheckCircle,
} from "lucide-react";
import LoadingSpinner from "../components/LoadingSpinner";
import { createEvaluation } from "../api/endpoints";
import type { Page } from "../types/navigation";

interface SourceFormItem {
  id: string;
  text: string;
  title: string;
  url: string;
}

interface Props {
  navigate: (p: Page) => void;
}

const SAMPLE_DATA = {
  question: "When was the Eiffel Tower constructed and how tall is it?",
  answer:
    "The Eiffel Tower was completed in 1889 for the Exposition Universelle. It stands at approximately 330 meters tall, including antennas. The tower is constructed out of solid concrete.",
  sources: [
    {
      id: "S1",
      title: "Eiffel Tower History & Architecture",
      url: "https://www.toureiffel.paris/en/history",
      text: "The Eiffel Tower was constructed between 1887 and 1889 to serve as the entrance to the 1889 World's Fair (Exposition Universelle). Standing at 330 metres tall with its broadcast antennas, the tower is built entirely of puddling iron (wrought iron), not steel or concrete.",
    },
  ],
};

export default function NewEvaluation({ navigate }: Props) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceFormItem[]>([
    { id: "S1", text: "", title: "", url: "" },
  ]);
  const [verifierType, setVerifierType] = useState<"rule_based" | "llm">("rule_based");
  const [providerId, setProviderId] = useState("gemini");
  const [modelId, setModelId] = useState("");
  const [concurrency, setConcurrency] = useState(4);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const addSource = () => {
    const nextIdx = sources.length + 1;
    setSources((prev) => [
      ...prev,
      { id: `S${nextIdx}`, text: "", title: "", url: "" },
    ]);
  };

  const removeSource = (index: number) => {
    if (sources.length <= 1) return;
    setSources((prev) => prev.filter((_, idx) => idx !== index));
  };

  const updateSource = (
    index: number,
    field: keyof SourceFormItem,
    value: string
  ) => {
    setSources((prev) =>
      prev.map((s, idx) => (idx === index ? { ...s, [field]: value } : s))
    );
  };

  const fillSample = () => {
    setQuestion(SAMPLE_DATA.question);
    setAnswer(SAMPLE_DATA.answer);
    setSources(SAMPLE_DATA.sources);
    setVerifierType("rule_based");
    setError(null);
  };

  const validate = (): string | null => {
    if (!question.trim()) return "Question is required.";
    if (!answer.trim()) return "AI-generated answer is required.";
    if (sources.length === 0) return "At least one source document is required.";

    for (let i = 0; i < sources.length; i++) {
      const s = sources[i];
      if (!s.text.trim()) {
        return `Source ${s.id || `#${i + 1}`} text cannot be empty.`;
      }
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || submitted) return;

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);
    setSubmitted(true);

    try {
      const payload = {
        question: question.trim(),
        answer: answer.trim(),
        sources: sources.map((s) => ({
          id: s.id.trim() || undefined,
          text: s.text.trim(),
          title: s.title.trim() || undefined,
          url: s.url.trim() || undefined,
        })),
        config:
          verifierType === "rule_based"
            ? {
                verifier_type: "rule_based" as const,
                max_concurrency: concurrency,
              }
            : {
                verifier_type: "llm" as const,
                max_concurrency: concurrency,
                provider_id: providerId,
                model_id: modelId.trim() || undefined,
              },
      };

      const result = await createEvaluation(payload);
      navigate({ id: "result", runId: result.run_id });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to run evaluation";
      setError(message);
      setSubmitted(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Top Banner & Quick-Fill */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            New Claim Evaluation
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Extract claims from an AI output and evaluate each against trusted sources.
          </p>
        </div>
        <button
          type="button"
          onClick={fillSample}
          className="inline-flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent-light hover:bg-accent/20 transition-all self-start sm:self-auto"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Load Sample Data
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Question & AI Answer */}
        <div className="rounded-xl border border-border bg-bg-card p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <BookOpen className="h-4 w-4 text-accent-light" />
            Evaluation Input
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Question or Prompt <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. When was the Eiffel Tower constructed and how tall is it?"
              className="w-full rounded-lg border border-border bg-bg px-3.5 py-2.5 text-xs sm:text-sm text-text-primary placeholder:text-text-muted/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              AI-Generated Answer <span className="text-rose-400">*</span>
            </label>
            <textarea
              rows={4}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Paste the generated response to decompose into claims and verify…"
              className="w-full rounded-lg border border-border bg-bg px-3.5 py-2.5 text-xs sm:text-sm text-text-primary placeholder:text-text-muted/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent transition-all resize-y"
            />
            <p className="text-[11px] text-text-muted mt-1">
              TruthLens extracts declarative factual claims from this text.
            </p>
          </div>
        </div>

        {/* Section 2: Evidence Sources */}
        <div className="rounded-xl border border-border bg-bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <CheckCircle className="h-4 w-4 text-emerald-400" />
              Evidence Sources ({sources.length})
            </div>
            <button
              type="button"
              onClick={addSource}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-light hover:text-accent transition-colors"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              Add Another Source
            </button>
          </div>

          <div className="space-y-4">
            {sources.map((src, index) => (
              <div
                key={index}
                className="rounded-lg border border-border/80 bg-bg/50 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-text-secondary">
                    Source #{index + 1}
                  </span>
                  {sources.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeSource(index)}
                      className="p-1 text-text-muted hover:text-rose-400 transition-colors"
                      title="Remove source"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-text-muted mb-1">
                      Identifier
                    </label>
                    <input
                      type="text"
                      value={src.id}
                      onChange={(e) => updateSource(index, "id", e.target.value)}
                      placeholder={`S${index + 1}`}
                      className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] text-text-muted mb-1">
                      Title (Optional)
                    </label>
                    <input
                      type="text"
                      value={src.title}
                      onChange={(e) => updateSource(index, "title", e.target.value)}
                      placeholder="e.g. Official Encyclopedia entry"
                      className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    URL Reference (Optional - display only)
                  </label>
                  <input
                    type="url"
                    value={src.url}
                    onChange={(e) => updateSource(index, "url", e.target.value)}
                    placeholder="https://example.com/source-doc"
                    className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    Verbatim Source Text <span className="text-rose-400">*</span>
                  </label>
                  <textarea
                    rows={3}
                    value={src.text}
                    onChange={(e) => updateSource(index, "text", e.target.value)}
                    placeholder="Paste the factual reference text from this source…"
                    className="w-full rounded-md border border-border bg-bg px-3 py-2 text-xs text-text-primary focus:border-accent focus:outline-none resize-y"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Verifier Configuration */}
        <div className="rounded-xl border border-border bg-bg-card p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Bot className="h-4 w-4 text-accent-light" />
            Verification Engine
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Rule-based option */}
            <div
              onClick={() => setVerifierType("rule_based")}
              className={`rounded-lg border p-3.5 cursor-pointer transition-all ${
                verifierType === "rule_based"
                  ? "border-accent bg-accent/10"
                  : "border-border bg-bg hover:border-border-light"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-text-primary">
                  Rule-based Verifier
                </span>
                <span className="text-[10px] bg-emerald-950/80 text-emerald-400 border border-emerald-800 px-1.5 py-0.2 rounded font-medium">
                  Recommended / Offline
                </span>
              </div>
              <p className="text-[11px] text-text-muted leading-relaxed">
                Deterministic lexical, numeric, and negation overlap matching. Fast, private, and works with zero API keys.
              </p>
            </div>

            {/* LLM Verifier option */}
            <div
              onClick={() => setVerifierType("llm")}
              className={`rounded-lg border p-3.5 cursor-pointer transition-all ${
                verifierType === "llm"
                  ? "border-accent bg-accent/10"
                  : "border-border bg-bg hover:border-border-light"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-text-primary">
                  LLM Provider Verifier
                </span>
                <span className="text-[10px] bg-amber-950/80 text-amber-400 border border-amber-800 px-1.5 py-0.2 rounded font-medium">
                  Requires Config
                </span>
              </div>
              <p className="text-[11px] text-text-muted leading-relaxed">
                Uses external or local LLM inference adapters (Gemini, Groq, OpenRouter, Ollama) configured in backend.
              </p>
            </div>
          </div>

          {verifierType === "llm" && (
            <div className="rounded-lg border border-border bg-bg p-4 space-y-3 animate-fadeIn">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-text-muted mb-1 font-medium">
                    LLM Provider
                  </label>
                  <select
                    value={providerId}
                    onChange={(e) => setProviderId(e.target.value)}
                    className="w-full rounded-md border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="groq">Groq (Ultra-fast)</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="ollama">Ollama (Local)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-text-muted mb-1 font-medium">
                    Model ID (Optional override)
                  </label>
                  <input
                    type="text"
                    value={modelId}
                    onChange={(e) => setModelId(e.target.value)}
                    placeholder="Leave empty to use .env model"
                    className="w-full rounded-md border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex items-start gap-2 text-[11px] text-text-muted">
                <Info className="h-3.5 w-3.5 text-accent-light flex-shrink-0 mt-0.5" />
                <span>
                  Check the <strong>Providers</strong> tab to inspect which providers are currently configured in your backend environment.
                </span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] text-text-muted mb-1">
              Max Concurrency ({concurrency})
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2.5 rounded-xl border border-rose-900/60 bg-rose-950/30 p-4 text-rose-300">
            <AlertCircle className="h-4.5 w-4.5 flex-shrink-0 text-rose-400 mt-0.5" />
            <div className="text-xs leading-relaxed">{error}</div>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="submit"
            disabled={loading || submitted}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/20 hover:bg-accent-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Evaluating Claims…</span>
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                <span>Run Evaluation</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
