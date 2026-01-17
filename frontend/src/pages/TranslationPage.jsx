import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../hooks/useTranslation';
import GlossaryPanel from '../components/GlossaryPanel';
import TermEditor from '../components/TermEditor';
import TranslationPreview from '../components/TranslationPreview';
import ProgressBar from '../components/ProgressBar';

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
    startTranslation,
    finalizeTranslation,
    updateTerm,
    refreshTerms,
  } = useTranslation(documentId);

  const [selectedTerm, setSelectedTerm] = useState(null);
  const [view, setView] = useState('split'); // split, glossary, preview
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  // Remove auto-start - user must click "Translate" button

  const handleStartTranslation = async () => {
    try {
      await startTranslation({
        useHudoc: true,
        useCuria: true,
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
  };

  const handleFinalize = async () => {
    if (!stats || stats.pending > 0) {
      if (!confirm(`Masz jeszcze ${stats.pending} terminów do zatwierdzenia. Czy na pewno chcesz zakończyć?`)) {
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

              {translationStatus === 'validating' && stats && stats.pending === 0 && (
                <button
                  onClick={handleFinalize}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
                >
                  ✓ Zakończ tłumaczenie
                </button>
              )}

              {translationStatus === 'complete' && (
                <button
                  onClick={handleDownload}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                >
                  ⬇ Pobierz tłumaczenie
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
              </div>
            </div>

            {/* Translation Config */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="flex items-start">
                <div className="text-blue-600 text-xl mr-3">ℹ️</div>
                <div className="text-sm text-blue-800">
                  <p className="font-medium mb-1">Opcje tłumaczenia:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Wykorzystanie pamięci tłumaczeniowej (TM)</li>
                    <li>Wyszukiwanie w bazie HUDOC i CURIA</li>
                    <li>Ekstrakcja i walidacja terminologii</li>
                  </ul>
                </div>
              </div>
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
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mb-4"></div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Tłumaczenie w toku
            </h2>
            <p className="text-gray-600 mb-4">
              {progress.stage || 'Przetwarzanie dokumentu...'}
            </p>
            {progress.message && (
              <p className="text-sm text-gray-500">{progress.message}</p>
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
        ) : (
          <div className={`grid gap-6 ${view === 'split' ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {/* Glossary Panel */}
            {(view === 'split' || view === 'glossary') && (
              <div className={view === 'glossary' ? 'max-w-4xl mx-auto w-full' : ''}>
                <GlossaryPanel
                  documentId={documentId}
                  onTermSelect={handleTermSelect}
                  onApproveAll={refreshTerms}
                />
              </div>
            )}

            {/* Translation Preview */}
            {(view === 'split' || view === 'preview') && (
              <div className={view === 'preview' ? 'max-w-4xl mx-auto w-full' : ''}>
                <TranslationPreview
                  sourceText={document?.source_text}
                  translatedText={document?.translated_text}
                  terms={terms}
                  onTermClick={handleTermSelect}
                />
              </div>
            )}
          </div>
        )}
      </main>

      {/* Term Editor Modal */}
      {selectedTerm && (
        <TermEditor
          term={selectedTerm}
          documentId={documentId}
          onClose={() => setSelectedTerm(null)}
          onSave={handleTermSave}
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
              Dokument został przetłumaczony i jest gotowy do pobrania.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/')}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
              >
                Strona główna
              </button>
              <button
                onClick={handleDownload}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Pobierz
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
    error: 'Błąd',
  };
  return labels[status] || status;
};

export default TranslationPage;
