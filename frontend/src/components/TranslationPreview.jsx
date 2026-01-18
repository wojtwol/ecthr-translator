import React from 'react';

const TranslationPreview = ({ sourceText, translatedText, terms, onTermClick }) => {
  // Highlight terms in the text
  const highlightTerms = (text, termsList, useSourceTerms = false) => {
    if (!text || !termsList || termsList.length === 0) {
      return <p className="whitespace-pre-wrap">{text}</p>;
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

    return <p className="whitespace-pre-wrap">{result}</p>;
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          📄 Podgląd tłumaczenia
        </h3>
      </div>

      {/* Parallel Content - Two Columns */}
      <div className="grid grid-cols-2 gap-0 max-h-[600px] overflow-y-auto">
        {/* Left Column - Source (EN) */}
        <div className="border-r border-gray-200 p-6 bg-gray-50">
          <div className="sticky top-0 bg-gray-50 pb-3 mb-3 border-b-2 border-gray-300">
            <h4 className="font-semibold text-sm text-gray-700">📄 Tekst źródłowy (EN)</h4>
          </div>
          <div className="prose prose-sm max-w-none">
            {sourceText ? (
              highlightTerms(sourceText, terms, true)
            ) : (
              <p className="text-gray-400 italic">Brak tekstu źródłowego</p>
            )}
          </div>
        </div>

        {/* Right Column - Target (PL) */}
        <div className="p-6 bg-white">
          <div className="sticky top-0 bg-white pb-3 mb-3 border-b-2 border-blue-300">
            <h4 className="font-semibold text-sm text-blue-700">🌍 Tłumaczenie (PL)</h4>
          </div>
          <div className="prose prose-sm max-w-none">
            {translatedText ? (
              highlightTerms(translatedText, terms, false)
            ) : (
              <p className="text-gray-400 italic">Tłumaczenie w toku...</p>
            )}
          </div>
        </div>
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
