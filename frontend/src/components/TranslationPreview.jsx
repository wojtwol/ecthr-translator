import React, { useState } from 'react';

const TranslationPreview = ({ segments, terms, onTermClick, documentId, onSegmentUpdate }) => {
  const [editingSegment, setEditingSegment] = useState(null);
  const [editedText, setEditedText] = useState('');
  const [saving, setSaving] = useState(false);

  const handleDoubleClick = (segment) => {
    if (!segment.id) return; // Can't edit without segment ID
    setEditingSegment(segment);
    setEditedText(segment.target || '');
  };

  const handleCancelEdit = () => {
    setEditingSegment(null);
    setEditedText('');
  };

  const handleSaveEdit = async () => {
    if (!editingSegment || !documentId) return;

    setSaving(true);
    try {
      const response = await fetch(
        `https://ecthr-translator.onrender.com/api/documents/${documentId}/segments/${editingSegment.id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_text: editedText }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update segment');
      }

      // Notify parent component to refresh
      if (onSegmentUpdate) {
        await onSegmentUpdate();
      }

      setEditingSegment(null);
      setEditedText('');
    } catch (error) {
      console.error('Failed to save segment:', error);
      alert(`Nie udało się zapisać segmentu: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Highlight terms in a single segment's text
  const highlightTerms = (text, termsList, useSourceTerms = false) => {
    if (!text || !termsList || termsList.length === 0) {
      return <span className="whitespace-pre-wrap">{text}</span>;
    }

    // Sort terms by length (longest first) to avoid partial matches
    const sortedTerms = [...termsList].sort((a, b) =>
      b.target_term.length - a.target_term.length
    );

    let result = [];
    let lastIndex = 0;
    const processedIndices = new Set();

    // Find all term occurrences
    const occurrences = [];
    sortedTerms.forEach(term => {
      const searchTerm = useSourceTerms ? term.source_term : term.target_term;
      const regex = new RegExp(`\\b${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      let match;

      while ((match = regex.exec(text)) !== null) {
        // Check if this position is already processed
        let overlaps = false;
        for (let i = match.index; i < match.index + match[0].length; i++) {
          if (processedIndices.has(i)) {
            overlaps = true;
            break;
          }
        }

        if (!overlaps) {
          occurrences.push({
            index: match.index,
            length: match[0].length,
            text: match[0],
            term: term,
          });

          // Mark indices as processed
          for (let i = match.index; i < match.index + match[0].length; i++) {
            processedIndices.add(i);
          }
        }
      }
    });

    // Sort occurrences by index
    occurrences.sort((a, b) => a.index - b.index);

    // Build the highlighted text
    occurrences.forEach((occurrence, idx) => {
      // Add text before this occurrence
      if (occurrence.index > lastIndex) {
        result.push(
          <span key={`text-${idx}`}>
            {text.substring(lastIndex, occurrence.index)}
          </span>
        );
      }

      // Add highlighted term
      const statusColors = {
        pending: 'bg-yellow-200 hover:bg-yellow-300',
        approved: 'bg-green-200 hover:bg-green-300',
        edited: 'bg-blue-200 hover:bg-blue-300',
        rejected: 'bg-red-200 hover:bg-red-300',
      };

      result.push(
        <span
          key={`term-${idx}`}
          className={`${statusColors[occurrence.term.status] || 'bg-gray-200'} cursor-pointer rounded px-1 transition-colors`}
          onClick={() => onTermClick && onTermClick(occurrence.term)}
          title={`${occurrence.term.source_term} → ${occurrence.term.target_term}\nStatus: ${occurrence.term.status}`}
        >
          {occurrence.text}
        </span>
      );

      lastIndex = occurrence.index + occurrence.length;
    });

    // Add remaining text
    if (lastIndex < text.length) {
      result.push(
        <span key="text-end">
          {text.substring(lastIndex)}
        </span>
      );
    }

    return <span className="whitespace-pre-wrap">{result}</span>;
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          📄 Podgląd tłumaczenia
        </h3>
      </div>

      {/* Parallel Content - Two Columns with Synchronized Segments */}
      <div className="grid grid-cols-2 gap-0 max-h-[600px] overflow-y-auto">
        {/* Column Headers */}
        <div className="sticky top-0 z-10 bg-gray-50 border-r border-b border-gray-200 p-3">
          <h4 className="font-semibold text-sm text-gray-700">📄 Tekst źródłowy (EN)</h4>
        </div>
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 p-3">
          <h4 className="font-semibold text-sm text-blue-700">🌍 Tłumaczenie (PL)</h4>
        </div>

        {/* Segments - Display in parallel rows */}
        {segments && segments.length > 0 ? (
          segments.map((segment, index) => (
            <React.Fragment key={index}>
              {/* Source segment */}
              <div className="border-r border-b border-gray-200 p-4 bg-gray-50">
                <div className="text-sm text-gray-900">
                  {segment.source ? (
                    highlightTerms(segment.source, terms, true)
                  ) : (
                    <span className="text-gray-400 italic">Brak tekstu</span>
                  )}
                </div>
              </div>

              {/* Target segment */}
              <div
                className="border-b border-gray-200 p-4 bg-white hover:bg-blue-50 transition-colors cursor-pointer group relative"
                onDoubleClick={() => handleDoubleClick(segment)}
                title="Kliknij dwukrotnie aby edytować"
              >
                {editingSegment && editingSegment.id === segment.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={editedText}
                      onChange={(e) => setEditedText(e.target.value)}
                      className="w-full min-h-[100px] text-sm p-2 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                      autoFocus
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={handleCancelEdit}
                        disabled={saving}
                        className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                      >
                        Anuluj
                      </button>
                      <button
                        onClick={handleSaveEdit}
                        disabled={saving || !editedText.trim()}
                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {saving ? 'Zapisuję...' : '✓ Zapisz'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="text-sm text-gray-900">
                      {segment.target ? (
                        highlightTerms(segment.target, terms, false)
                      ) : (
                        <span className="text-gray-400 italic">Tłumaczenie w toku...</span>
                      )}
                    </div>
                    {segment.target && (
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-xs text-blue-600 font-medium">✎ Edytuj</span>
                      </div>
                    )}
                  </>
                )}
              </div>
            </React.Fragment>
          ))
        ) : (
          <>
            <div className="border-r border-gray-200 p-6 bg-gray-50 text-center">
              <p className="text-gray-400 italic">Brak segmentów źródłowych</p>
            </div>
            <div className="p-6 bg-white text-center">
              <p className="text-gray-400 italic">Tłumaczenie w toku...</p>
            </div>
          </>
        )}
      </div>

      {/* Legend */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-600 font-medium">Legenda:</span>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-yellow-200 rounded">Do zatwierdzenia</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-green-200 rounded">Zatwierdzony</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-blue-200 rounded">Edytowany</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-red-200 rounded">Odrzucony</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TranslationPreview;
