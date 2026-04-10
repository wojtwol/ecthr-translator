import React, { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../config';

const TermEditor = ({ term, documentId, onClose, onSave, translationStatus, onApplyToTranslation }) => {
  const [editedTerm, setEditedTerm] = useState('');
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    if (term) {
      setEditedTerm(term.target_term);
    }
  }, [term]);

  if (!term) return null;

  const handleSave = async (status) => {
    setSaving(true);
    try {
      // Create timeout signal for long cold start
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

      const response = await authFetch(
        `${API_BASE_URL}/glossary/${documentId}/${term.id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_term: editedTerm,
            status: status,
          }),
          signal: controller.signal,
        }
      );

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error('Failed to save term');
      }

      const updatedTerm = await response.json();
      if (onSave) onSave(updatedTerm);
      onClose();
    } catch (error) {
      console.error('Failed to save term:', error);

      // Better error message for timeout/cold start
      if (error.name === 'AbortError') {
        alert('Backend się budzi (cold start). Spróbuj ponownie za chwilę.');
      } else {
        alert(`Nie udało się zapisać terminu: ${error.message}`);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleApplyToTranslation = async () => {
    if (!onApplyToTranslation) return;

    setApplying(true);
    try {
      const result = await onApplyToTranslation(term.id);
      alert(`✓ Zaktualizowano ${result.segments_updated} segmentów\n\n"${result.old_translation}" → "${result.new_translation}"`);
      onClose();
    } catch (error) {
      console.error('Failed to apply term to translation:', error);
      alert(`Nie udało się zaktualizować tłumaczenia: ${error.message}`);
    } finally {
      setApplying(false);
    }
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-gray-900">
              Edycja terminu
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Source term */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Termin źródłowy (EN)
            </label>
            <div className="px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-gray-900">
              {term.source_term}
            </div>
          </div>

          {/* Target term - editable */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tłumaczenie (PL)
            </label>
            <input
              type="text"
              value={editedTerm}
              onChange={(e) => setEditedTerm(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent"
              placeholder="Wprowadź tłumaczenie..."
            />
            {term.original_proposal && term.original_proposal !== editedTerm && (
              <p className="mt-2 text-sm text-gray-500">
                Oryginalna propozycja: <span className="font-medium">{term.original_proposal}</span>
              </p>
            )}
          </div>

          {/* Context */}
          {term.context && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Kontekst
              </label>
              <div className="px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-gray-700 text-sm">
                "{term.context}"
              </div>
            </div>
          )}

          {/* Sources from HUDOC/CURIA */}
          {term.sources && term.sources.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Źródła
              </label>
              <div className="space-y-3">
                {term.sources.map((source, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-blue-50 border border-blue-100 rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-blue-900">
                        {source.source_type === 'hudoc' ? '⚖️ HUDOC' :
                         source.source_type === 'curia' ? '🏛️ CURIA' :
                         source.source_type === 'iate' ? '🇪🇺 IATE' :
                         source.source_type}
                      </span>
                      {source.case_name && (
                        <span className="text-xs text-blue-700">
                          {source.case_name}
                        </span>
                      )}
                    </div>
                    {source.context && (
                      <p className="text-sm text-gray-700 italic">
                        "{source.context}"
                      </p>
                    )}
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                      >
                        Zobacz źródło →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Translation Memory matches */}
          {term.tm_matches && term.tm_matches.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Pamięć tłumaczeniowa
              </label>
              <div className="space-y-2">
                {term.tm_matches.map((match, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-green-50 border border-green-100 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900">
                        {match.source} → {match.target}
                      </span>
                      <span className="text-xs font-semibold text-green-700">
                        {Math.round(match.similarity * 100)}%
                      </span>
                    </div>
                    {match.context && (
                      <p className="text-xs text-gray-600 italic">
                        "{match.context}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          {/* Show "Apply to Translation" button if translation is completed and term was edited */}
          {translationStatus === 'completed' && term.original_proposal && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-900 mb-3">
                <strong>💡 Tłumaczenie zakończone:</strong> Ten termin został zmieniony po zakończeniu tłumaczenia.
                Kliknij poniżej, aby automatycznie zaktualizować wszystkie wystąpienia w już przetłumaczonych segmentach.
              </p>
              <button
                onClick={handleApplyToTranslation}
                disabled={applying || saving}
                className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {applying ? '⏳ Aktualizuję tłumaczenie...' : '🔄 Zaktualizuj tłumaczenie'}
              </button>
            </div>
          )}

          <div className="flex flex-wrap gap-3 justify-end">
            <button
              onClick={() => handleSave('rejected')}
              disabled={saving || applying}
              className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              ✗ Odrzuć
            </button>
            <button
              onClick={onClose}
              disabled={saving || applying}
              className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              Anuluj
            </button>
            <button
              onClick={() => handleSave(editedTerm === term.target_term ? 'approved' : 'edited')}
              disabled={saving || applying || !editedTerm.trim()}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {saving ? 'Zapisywanie...' : editedTerm === term.target_term ? '✓ Zatwierdź' : '✓ Zatwierdź ze zmianami'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TermEditor;
