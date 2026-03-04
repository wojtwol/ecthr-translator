import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../hooks/useTranslation';
import GlossaryPanel from '../components/GlossaryPanel';
import TermEditor from '../components/TermEditor';
import TranslationPreview from '../components/TranslationPreview';
import ProgressBar from '../components/ProgressBar';
import SourcesReport from '../components/SourcesReport';

const TranslationPage = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const {
    document,
    terms,
    stats,
    translationStatus,
    progress,
    error,
    loading,
    translatedSegments,
    extractionComplete,
    batchInfo,
    startTranslation,
    finalizeTranslation,
    updateTerm,
    applyTermToTranslation,
    refreshTerms,
    refreshSegments,
  } = useTranslation(documentId);

  const [selectedTerm, setSelectedTerm] = useState(null);
  const [view, setView] = useState('split'); // split, glossary, preview
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [workflowMode, setWorkflowMode] = useState('full'); // full or quick
  const [useHudoc, setUseHudoc] = useState(true);
  const [useCuria, setUseCuria] = useState(true);
  const [useIate, setUseIate] = useState(true);
  const [documentStats, setDocumentStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [glossaryRefreshTrigger, setGlossaryRefreshTrigger] = useState(0);

  // State for adding term from text selection
  const [pendingTermSource, setPendingTermSource] = useState('');
  const [pendingTermTarget, setPendingTermTarget] = useState('');

  // Callback from TranslationPreview when user selects text
  const handleAddTermFromSelection = (sourceTerm, targetTerm) => {
    setPendingTermSource(sourceTerm);
    setPendingTermTarget(targetTerm);
    // Switch to split view if in preview-only mode
    if (view === 'preview') {
      setView('split');
    }
  };

  // Callback when term is added successfully
  const handleTermAdded = () => {
    setPendingTermSource('');
    setPendingTermTarget('');
    setGlossaryRefreshTrigger(prev => prev + 1);
  };

  // Polling backup for terms when WebSocket fails during validation
  // IMPORTANT: Also refresh GlossaryPanel to show newly extracted terms
  useEffect(() => {
    if (translationStatus === 'validating' || translationStatus === 'translating') {
      const interval = setInterval(() => {
        console.log('[Polling] Refreshing terms and segments as backup...');
        refreshTerms();
        setGlossaryRefreshTrigger(prev => prev + 1); // Trigger GlossaryPanel refresh
      }, 5000); // Poll every 5 seconds

      return () => clearInterval(interval);
    }
  }, [translationStatus, refreshTerms]);

  // Auto-refresh GlossaryPanel when new terms are extracted (stats.total changes)
  useEffect(() => {
    if (stats && stats.total > 0 && translationStatus === 'validating') {
      console.log('[Auto-refresh] New terms detected, refreshing GlossaryPanel...');
      setGlossaryRefreshTrigger(prev => prev + 1);
    }
  }, [stats?.total, translationStatus]);

  // Remove auto-start - user must click "Translate" button

  // Fetch document statistics when document is ready
  useEffect(() => {
    if (document && (document.status === 'uploaded' || translationStatus === 'uploaded')) {
      fetchDocumentStats();
    }
  }, [document, translationStatus]);

  const fetchDocumentStats = async () => {
    try {
      setLoadingStats(true);
      const response = await fetch(`https://ecthr-translator.onrender.com/api/documents/${documentId}/analyze`);
      if (response.ok) {
        const stats = await response.json();
        setDocumentStats(stats);
      }
    } catch (err) {
      console.error('Failed to fetch document stats:', err);
    } finally {
      setLoadingStats(false);
    }
  };

  const handleStartTranslation = async () => {
    try {
      await startTranslation({
        workflowMode: workflowMode,
        useHudoc: useHudoc,
        useCuria: useCuria,
        useIate: useIate,
      });
    } catch (err) {
      console.error('Failed to start translation:', err);
    }
  };

  const handleTermSelect = (term) => {
    setSelectedTerm(term);
  };

  const handleTermSave = async (updatedTerm) => {
    setSelectedTerm(null);
    await refreshTerms();
    setGlossaryRefreshTrigger(prev => prev + 1); // Trigger GlossaryPanel refresh
  };

  const handleFinalize = async () => {
    if (!stats || stats.pending > 0) {
      if (!confirm(`Masz jeszcze ${stats.pending} terminów do zatwierdzenia. Czy na pewno chcesz przetłumaczyć dokument z niezatwierdzoną terminologią?`)) {
        return;
      }
    }

    try {
      const result = await finalizeTranslation();
      setShowSuccessModal(true);
    } catch (err) {
      console.error('Failed to finalize translation:', err);
      alert('Nie udało się sfinalizować tłumaczenia');
    }
  };

  const handleDownload = () => {
    window.location.href = `https://ecthr-translator.onrender.com/api/documents/${documentId}/download`;
  };

  const handleExportTM = () => {
    window.location.href = `https://ecthr-translator.onrender.com/api/tm/export/${documentId}`;
  };

  const handleUpdateTM = async () => {
    try {
      const response = await fetch(`https://ecthr-translator.onrender.com/api/tm/update-from-project/${documentId}`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to update TM');
      }

      const result = await response.json();
      alert(`✅ Pamięć tłumaczeniowa zaktualizowana!\n\nDodano: ${result.added} segmentów\nPominięto duplikaty: ${result.skipped}\nŁączna liczba wpisów: ${result.total_entries}`);
    } catch (err) {
      console.error('Failed to update TM:', err);
      alert('❌ Nie udało się zaktualizować pamięci tłumaczeniowej');
    }
  };

  const handleExportGlossaryAll = () => {
    window.location.href = `https://ecthr-translator.onrender.com/api/glossary/${documentId}/export/all/xlsx`;
  };

  const handleExportGlossaryApproved = () => {
    window.location.href = `https://ecthr-translator.onrender.com/api/glossary/${documentId}/export/approved/xlsx`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Ładowanie...</p>
        </div>
      </div>
    );
  }

  if (error && !document) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <div className="text-red-600 text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Błąd</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Powrót do strony głównej
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="text-gray-500 hover:text-gray-700"
              >
                ← Powrót
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {document?.filename || 'Dokument'}
                </h1>
                <p className="text-sm text-gray-500">
                  Status: {getStatusLabel(translationStatus)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* View toggle */}
              <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                <button
                  onClick={() => setView('split')}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    view === 'split' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Podzielony
                </button>
                <button
                  onClick={() => setView('glossary')}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    view === 'glossary' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Terminologia
                </button>
                <button
                  onClick={() => setView('preview')}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    view === 'preview' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Podgląd
                </button>
              </div>

              {(translationStatus === 'validating' || translationStatus === 'completed') && stats && (stats.pending === 0 || (stats.approved > 0 || stats.edited > 0)) && (
                <button
                  onClick={handleFinalize}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium shadow-md"
                  title={translationStatus === 'completed'
                    ? 'Ponów tłumaczenie ze zaktualizowaną terminologią'
                    : (stats.pending > 0 ? `Uwaga: ${stats.pending} terminów wciąż do zatwierdzenia` : 'Wszystkie terminy zatwierdzone - gotowe do finalizacji')}
                >
                  🔄 Przetłumacz z zatwierdzoną terminologią
                  {stats.approved + stats.edited > 0 && ` (${stats.approved + stats.edited} terminów)`}
                </button>
              )}
            </div>
          </div>

          {/* Progress indicator */}
          {translationStatus === 'translating' && progress && (
            <div className="mt-4">
              <ProgressBar
                current={progress.progress}
                total={100}
                label={progress.stage || 'Tłumaczenie w toku'}
              />
              {progress.message && (
                <p className="text-sm text-gray-600 mt-2">{progress.message}</p>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {translationStatus === 'idle' || translationStatus === 'uploaded' ? (
          <div className="bg-white rounded-lg shadow p-8 max-w-2xl mx-auto">
            <div className="text-center mb-6">
              <div className="text-6xl mb-4">📄</div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                Dokument gotowy do tłumaczenia
              </h2>
              <p className="text-gray-600">
                Przejrzyj informacje o dokumencie i rozpocznij tłumaczenie
              </p>
            </div>

            {/* Document Statistics */}
            <div className="bg-gray-50 rounded-lg p-6 mb-6">
              <h3 className="font-semibold text-gray-900 mb-4">Informacje o dokumencie</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Nazwa pliku:</span>
                  <span className="font-medium text-gray-900">{document?.filename || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Typ:</span>
                  <span className="font-medium text-gray-900">DOCX</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    Gotowy
                  </span>
                </div>
                {document?.upload_timestamp && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Przesłano:</span>
                    <span className="font-medium text-gray-900">
                      {new Date(document.upload_timestamp).toLocaleString('pl-PL')}
                    </span>
                  </div>
                )}

                {/* Document Statistics */}
                {loadingStats ? (
                  <div className="flex justify-center py-2">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  </div>
                ) : documentStats && (
                  <>
                    <div className="border-t pt-3 mt-3"></div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Liczba segmentów:</span>
                      <span className="font-medium text-gray-900">{documentStats.total_segments}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Liczba słów:</span>
                      <span className="font-medium text-gray-900">{documentStats.total_words}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Liczba znaków:</span>
                      <span className="font-medium text-gray-900">{documentStats.total_characters}</span>
                    </div>
                    {documentStats.estimated_translation_time_minutes && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Szacowany czas:</span>
                        <span className="font-medium text-gray-900">
                          ~{documentStats.estimated_translation_time_minutes} min
                        </span>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Translation Workflow Mode Selection */}
            <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Wybierz tryb tłumaczenia</h3>

              {/* Full Workflow Option */}
              <label className="flex items-start p-4 mb-3 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                     style={{ borderColor: workflowMode === 'full' ? '#3B82F6' : '#E5E7EB' }}>
                <input
                  type="radio"
                  name="workflowMode"
                  value="full"
                  checked={workflowMode === 'full'}
                  onChange={(e) => setWorkflowMode(e.target.value)}
                  className="mt-1 mr-3"
                />
                <div className="flex-1">
                  <div className="flex items-center mb-1">
                    <span className="font-semibold text-gray-900">Pełny workflow z walidacją terminologii</span>
                    <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">Zalecany</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    Dokładne tłumaczenie oparte na pamięci tłumaczeniowej z kontrolą jakości i walidacją użytkownika
                  </p>
                  <ul className="text-xs text-gray-500 space-y-1">
                    <li>✓ <strong>Pamięć tłumaczeniowa (TM)</strong> jako fundament tłumaczenia</li>
                    <li>✓ Wzbogacanie terminologii bazami HUDOC, CURIA i IATE</li>
                    <li>✓ Ekstrakcja i walidacja terminologii prawniczej</li>
                    <li>✓ Możliwość zatwierdzenia/edycji/odrzucenia terminów</li>
                    <li>✓ Kontrola jakości (QA Review)</li>
                    <li>✓ Automatyczna aktualizacja TM po zakończeniu</li>
                  </ul>
                </div>
              </label>

              {/* Quick Workflow Option */}
              <label className="flex items-start p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                     style={{ borderColor: workflowMode === 'quick' ? '#3B82F6' : '#E5E7EB' }}>
                <input
                  type="radio"
                  name="workflowMode"
                  value="quick"
                  checked={workflowMode === 'quick'}
                  onChange={(e) => setWorkflowMode(e.target.value)}
                  className="mt-1 mr-3"
                />
                <div className="flex-1">
                  <div className="flex items-center mb-1">
                    <span className="font-semibold text-gray-900">Szybkie tłumaczenie bez walidacji</span>
                    <span className="ml-2 px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded">Szybki</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    Natychmiastowe tłumaczenie oparte w pełni na pamięci tłumaczeniowej (TM)
                  </p>
                  <ul className="text-xs text-gray-500 space-y-1">
                    <li>✓ <strong>Pamięć tłumaczeniowa (TM)</strong> jako główne źródło tłumaczenia</li>
                    <li>✓ Opcjonalne wzbogacanie o HUDOC/CURIA/IATE (poniżej)</li>
                    <li>✓ Automatyczne tłumaczenie bez ekstrakcji terminów</li>
                    <li>✓ Brak etapu walidacji - gotowy dokument od razu</li>
                    <li>✓ Automatyczna aktualizacja TM po zakończeniu</li>
                    <li>⚠ Brak kontroli jakości i walidacji terminologii</li>
                  </ul>
                </div>
              </label>

              {/* Optional HUDOC/CURIA for Quick Mode */}
              {workflowMode === 'quick' && (
                <div className="mt-3 ml-9 pl-4 border-l-2 border-gray-300">
                  <p className="text-sm font-medium text-gray-700 mb-2">Opcjonalne wzbogacenie TM o dodatkowe źródła:</p>
                  <div className="space-y-2">
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useHudoc}
                        onChange={(e) => setUseHudoc(e.target.checked)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">
                        + HUDOC (orzeczenia ETPCz)
                      </span>
                    </label>
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useCuria}
                        onChange={(e) => setUseCuria(e.target.checked)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">
                        + CURIA (orzeczenia TSUE)
                      </span>
                    </label>
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useIate}
                        onChange={(e) => setUseIate(e.target.checked)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">
                        + IATE 🇪🇺 (terminologia UE)
                      </span>
                    </label>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    💡 TM jest zawsze używana jako baza. Dodatkowe źródła mogą poprawić jakość terminologii, ale wydłużą czas tłumaczenia
                  </p>
                </div>
              )}
            </div>

            {/* Start Translation Button */}
            <button
              onClick={handleStartTranslation}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold text-lg transition-colors shadow-md hover:shadow-lg"
            >
              🚀 Rozpocznij tłumaczenie
            </button>
          </div>
        ) : translationStatus === 'translating' ? (
          <div className="space-y-4">
            {/* Progress Bar */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">
                      Tłumaczenie w toku
                    </h2>
                    <p className="text-sm text-gray-600">
                      {progress.message || 'Przetwarzanie dokumentu...'}
                    </p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-blue-600">
                  {Math.round((progress.progress || 0) * 100)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${(progress.progress || 0) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Live Translation Preview - Two Columns */}
            {translatedSegments.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Podgląd tłumaczenia na żywo
                </h3>
                <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                  {/* Left Column - Source (EN) */}
                  <div className="border-r border-gray-200 pr-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-gray-700">Tekst źródłowy (EN)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-800 p-2 bg-gray-50 rounded">
                            <span className="text-xs text-gray-500 font-medium mr-2">[{idx + 1}]</span>
                            {segment.source}
                          </div>
                        )
                      ))}
                    </div>
                  </div>

                  {/* Right Column - Target (PL) */}
                  <div className="pl-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-blue-700">Tłumaczenie (PL)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-900 p-2 bg-blue-50 rounded border-l-2 border-blue-500">
                            <span className="text-xs text-blue-600 font-medium mr-2">[{idx + 1}]</span>
                            {segment.target}
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : translationStatus === 'error' ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="text-red-600 text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Wystąpił błąd
            </h2>
            <p className="text-gray-600 mb-4">{error}</p>
            <button
              onClick={handleStartTranslation}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Spróbuj ponownie
            </button>
          </div>
        ) : (translationStatus === 'completed' || translationStatus === 'complete') ? (
          <>
            {/* Completion Banner */}
            <div className="bg-green-50 border-l-4 border-green-500 p-6 mb-6 rounded-r-lg shadow-sm">
              <div className="flex items-center">
                <div className="text-green-600 text-4xl mr-4">✓</div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-green-900 mb-1">
                    Tłumaczenie zakończone!
                  </h3>
                  <p className="text-sm text-green-700">
                    Możesz przejrzeć przetłumaczone segmenty i terminologię poniżej, lub pobrać gotowy dokument.
                  </p>
                </div>
                <div className="ml-4 flex gap-3">
                  <button
                    onClick={handleDownload}
                    className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold shadow-md hover:shadow-lg transition-all"
                  >
                    ⬇ Pobierz DOCX
                  </button>
                  <button
                    onClick={handleExportGlossaryApproved}
                    className="px-4 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 font-semibold shadow-md hover:shadow-lg transition-all text-sm"
                    title="Eksportuj zatwierdzoną terminologię do CSV"
                  >
                    📚 Glosariusz
                  </button>
                  <button
                    onClick={handleExportTM}
                    className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md hover:shadow-lg transition-all text-sm"
                    title="Eksportuj pamięć tłumaczeniową tylko z tego projektu"
                  >
                    📥 TM
                  </button>
                  <button
                    onClick={handleUpdateTM}
                    className="px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-semibold shadow-md hover:shadow-lg transition-all text-sm"
                    title="Aktualizuj globalną pamięć tłumaczeniową segmentami z tego projektu"
                  >
                    🔄 Aktualizuj TM
                  </button>
                </div>
              </div>
            </div>

            {/* Translated Segments Preview */}
            {translatedSegments.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6 mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  📝 Przetłumaczone segmenty ({translatedSegments.length})
                </h3>
                <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                  {/* Left Column - Source (EN) */}
                  <div className="border-r border-gray-200 pr-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-gray-700">Tekst źródłowy (EN)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-800 p-2 bg-gray-50 rounded">
                            <span className="text-xs text-gray-500 font-medium mr-2">[{idx + 1}]</span>
                            {segment.source}
                          </div>
                        )
                      ))}
                    </div>
                  </div>

                  {/* Right Column - Target (PL) */}
                  <div className="pl-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-blue-700">Tłumaczenie (PL)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-900 p-2 bg-blue-50 rounded border-l-2 border-blue-500">
                            <span className="text-xs text-blue-600 font-medium mr-2">[{idx + 1}]</span>
                            {segment.target}
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Sources Report Section */}
            <div className="mb-6">
              <SourcesReport documentId={documentId} />
            </div>

            {/* View Terminology Section */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  📚 Terminologia
                </h3>
                <button
                  onClick={handleExportGlossaryApproved}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold shadow-md hover:shadow-lg transition-all text-sm"
                  title="Eksportuj zatwierdzone terminy do CSV"
                >
                  📥 Eksportuj zatwierdzone
                </button>
              </div>
              <GlossaryPanel
                documentId={documentId}
                onTermSelect={handleTermSelect}
                onApproveAll={refreshTerms}
                refreshTrigger={glossaryRefreshTrigger}
                initialSourceTerm={pendingTermSource}
                initialTargetTerm={pendingTermTarget}
                onTermAdded={handleTermAdded}
              />
            </div>
          </>
        ) : (
          <>
            {/* Batch Extraction Progress Banner */}
            {progress.stage === 'batch_extraction' && (
              <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6 rounded-r-lg shadow-sm">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  </div>
                  <div className="ml-3 flex-1">
                    <p className="text-sm font-medium text-blue-800">
                      {progress.message || 'Ekstrakcja kolejnych terminów w tle...'}
                    </p>
                    <p className="text-xs text-blue-600 mt-1">
                      💡 Możesz już zacząć walidować dostępne terminy - nowe będą pojawiać się automatycznie
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Extraction In Progress Banner - Show while batches are being processed */}
            {translationStatus === 'validating' && !extractionComplete && stats && stats.total > 0 && (
              <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6 rounded-r-lg shadow-sm">
                <div className="flex items-center">
                  <div className="flex-shrink-0 text-blue-600 text-2xl">
                    ⏳
                  </div>
                  <div className="ml-3 flex-1">
                    <div className="flex items-center gap-3">
                      <p className="text-sm font-medium text-blue-900">
                        Ekstrakcja w toku...
                      </p>
                      {batchInfo.total > 0 && (
                        <span className="px-3 py-1 bg-blue-600 text-white rounded-full text-xs font-bold">
                          Batch {batchInfo.current}/{batchInfo.total}
                        </span>
                      )}
                    </div>
                    {batchInfo.total > 0 && (
                      <div className="mt-2 mb-1">
                        <ProgressBar
                          current={batchInfo.current}
                          total={batchInfo.total}
                          label="Postęp ekstrakcji"
                        />
                      </div>
                    )}
                    <p className="text-xs text-blue-700 mt-1">
                      📚 Dotychczas znaleziono <strong>{stats.total}</strong> terminów
                      {stats.from_hudoc > 0 && ` (⚖️ ${stats.from_hudoc} z HUDOC`}
                      {stats.from_curia > 0 && `, 🏛️ ${stats.from_curia} z CURIA`}
                      {stats.from_tm_exact > 0 && `, ✓ ${stats.from_tm_exact} z TM 100%`}
                      {stats.from_tm_fuzzy > 0 && `, ≈ ${stats.from_tm_fuzzy} z TM 95%+`}
                      {stats.from_proposed > 0 && `, 🤖 ${stats.from_proposed} AI`}
                      {(stats.from_hudoc > 0 || stats.from_curia > 0 || stats.from_tm_exact > 0 || stats.from_tm_fuzzy > 0 || stats.from_proposed > 0) && ')'}
                    </p>
                    <p className="text-xs text-blue-700 mt-1">
                      💡 Możesz już zacząć zatwierdzać terminy - ekstrakcja kontynuowana w tle
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Extraction Complete Banner - Show summary of extracted terms */}
            {translationStatus === 'validating' && extractionComplete && stats && stats.total > 0 && (
              <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-6 rounded-r-lg shadow-sm">
                <div className="flex items-center">
                  <div className="flex-shrink-0 text-green-600 text-2xl">
                    ✓
                  </div>
                  <div className="ml-3 flex-1">
                    <p className="text-sm font-medium text-green-900">
                      Ekstrakcja terminologii zakończona!
                    </p>
                    <p className="text-xs text-green-700 mt-1">
                      📚 Znaleziono <strong>{stats.total}</strong> terminów do zatwierdzenia
                      {stats.from_hudoc > 0 && ` (⚖️ ${stats.from_hudoc} z HUDOC`}
                      {stats.from_curia > 0 && `, 🏛️ ${stats.from_curia} z CURIA`}
                      {stats.from_tm_exact > 0 && `, ✓ ${stats.from_tm_exact} z TM 100%`}
                      {stats.from_tm_fuzzy > 0 && `, ≈ ${stats.from_tm_fuzzy} z TM 95%+`}
                      {stats.from_proposed > 0 && `, 🤖 ${stats.from_proposed} AI`}
                      {(stats.from_hudoc > 0 || stats.from_curia > 0 || stats.from_tm_exact > 0 || stats.from_tm_fuzzy > 0 || stats.from_proposed > 0) && ')'}
                    </p>
                    {stats.pending > 0 ? (
                      <p className="text-xs text-green-700 mt-1">
                        ⏳ Pozostało do zatwierdzenia: <strong>{stats.pending}</strong> terminów
                      </p>
                    ) : (
                      <p className="text-xs text-green-800 mt-1 font-medium">
                        ✅ Wszystkie terminy zatwierdzone! Kliknij "Przetłumacz z zatwierdzoną terminologią" aby wygenerować finalne tłumaczenie z poprawną terminologią.
                      </p>
                    )}
                  </div>
                  <button
                    onClick={handleExportGlossaryAll}
                    className="ml-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md hover:shadow-lg transition-all text-sm whitespace-nowrap"
                    title="Eksportuj wszystkie terminy do CSV"
                  >
                    📥 Eksportuj glosariusz
                  </button>
                </div>
              </div>
            )}

            {/* Finalization In Progress Banner - Show during final translation */}
            {translationStatus === 'finalizing' && (
              <div className="bg-purple-50 border-l-4 border-purple-500 p-4 mb-6 rounded-r-lg shadow-sm">
                <div className="flex items-center">
                  <div className="flex-shrink-0 text-purple-600 text-2xl">
                    🔄
                  </div>
                  <div className="ml-3 flex-1">
                    <p className="text-sm font-medium text-purple-900">
                      Generowanie finalnego tłumaczenia...
                    </p>
                    <p className="text-xs text-purple-700 mt-1">
                      📝 Aplikowanie zatwierdzonej terminologii i generowanie dokumentu
                    </p>
                    <p className="text-xs text-purple-700 mt-1">
                      ⏱️ To może potrwać kilka minut - proszę czekać...
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Translated Segments Preview - Show after translation complete */}
            {translatedSegments.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6 mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Przetłumaczone segmenty
                </h3>
                <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                  {/* Left Column - Source (EN) */}
                  <div className="border-r border-gray-200 pr-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-gray-700">Tekst źródłowy (EN)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-800 p-2 bg-gray-50 rounded">
                            <span className="text-xs text-gray-500 font-medium mr-2">[{idx + 1}]</span>
                            {segment.source}
                          </div>
                        )
                      ))}
                    </div>
                  </div>

                  {/* Right Column - Target (PL) */}
                  <div className="pl-4">
                    <div className="sticky top-0 bg-white pb-2 mb-2 border-b border-gray-300">
                      <h4 className="font-semibold text-sm text-blue-700">Tłumaczenie (PL)</h4>
                    </div>
                    <div className="space-y-3">
                      {translatedSegments.map((segment, idx) => (
                        segment && (
                          <div key={idx} className="text-sm text-gray-900 p-2 bg-blue-50 rounded border-l-2 border-blue-500">
                            <span className="text-xs text-blue-600 font-medium mr-2">[{idx + 1}]</span>
                            {segment.target}
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className={`grid gap-6 ${view === 'split' ? 'grid-cols-2' : 'grid-cols-1'}`}>
              {/* Glossary Panel */}
            {(view === 'split' || view === 'glossary') && (
              <div className={view === 'glossary' ? 'max-w-4xl mx-auto w-full' : ''}>
                <GlossaryPanel
                  documentId={documentId}
                  onTermSelect={handleTermSelect}
                  onApproveAll={refreshTerms}
                  refreshTrigger={glossaryRefreshTrigger}
                  initialSourceTerm={pendingTermSource}
                  initialTargetTerm={pendingTermTarget}
                  onTermAdded={handleTermAdded}
                />
              </div>
            )}

            {/* Translation Preview */}
            {(view === 'split' || view === 'preview') && (
              <div className={view === 'preview' ? 'max-w-4xl mx-auto w-full' : ''}>
                <TranslationPreview
                  segments={translatedSegments || []}
                  terms={terms}
                  onTermClick={handleTermSelect}
                  documentId={documentId}
                  onSegmentUpdate={refreshSegments}
                  onAddTermFromSelection={handleAddTermFromSelection}
                />
              </div>
            )}
            </div>
          </>
        )}
      </main>

      {/* Term Editor Modal */}
      {selectedTerm && (
        <TermEditor
          term={selectedTerm}
          documentId={documentId}
          onClose={() => setSelectedTerm(null)}
          onSave={handleTermSave}
          translationStatus={translationStatus}
          onApplyToTranslation={applyTermToTranslation}
        />
      )}

      {/* Success Modal */}
      {showSuccessModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-8 text-center">
            <div className="text-green-600 text-6xl mb-4">✓</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Tłumaczenie zakończone!
            </h2>
            <p className="text-gray-600 mb-6">
              Dokument został przetłumaczony z zatwierdzoną terminologią i jest gotowy do pobrania.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => setShowSuccessModal(false)}
                className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md transition-colors"
              >
                👁️ Zobacz tłumaczenie
              </button>
              <button
                onClick={() => {
                  handleDownload();
                  setShowSuccessModal(false);
                }}
                className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold shadow-md transition-colors"
              >
                ⬇️ Pobierz DOCX
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    handleExportGlossaryApproved();
                    setShowSuccessModal(false);
                  }}
                  className="flex-1 px-3 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 font-semibold shadow-md transition-colors text-sm"
                  title="Eksportuj glosariusz"
                >
                  📚 Glosariusz
                </button>
                <button
                  onClick={() => {
                    handleExportTM();
                    setShowSuccessModal(false);
                  }}
                  className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md transition-colors text-sm"
                  title="Eksportuj TM projektu"
                >
                  📥 TM
                </button>
                <button
                  onClick={async () => {
                    await handleUpdateTM();
                    setShowSuccessModal(false);
                  }}
                  className="flex-1 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-semibold shadow-md transition-colors text-sm"
                  title="Aktualizuj globalną TM"
                >
                  🔄 Aktualizuj TM
                </button>
              </div>
              <button
                onClick={() => navigate('/')}
                className="w-full px-4 py-2 text-gray-600 hover:text-gray-900 text-sm transition-colors"
              >
                ← Wróć do strony głównej
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Helper function to get status label in Polish
const getStatusLabel = (status) => {
  const labels = {
    idle: 'Oczekuje',
    uploaded: 'Przesłany',
    translating: 'Tłumaczenie w toku',
    validating: 'Walidacja terminów',
    complete: 'Zakończone',
    completed: 'Zakończone',
    error: 'Błąd',
  };
  return labels[status] || status;
};

export default TranslationPage;
