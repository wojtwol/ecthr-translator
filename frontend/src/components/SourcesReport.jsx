import React, { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../config';

const SourcesReport = ({ documentId }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    hudoc: true,
    curia: true,
    tm: true,
    proposed: false,
  });

  useEffect(() => {
    fetchReport();
  }, [documentId]);

  const fetchReport = async () => {
    setLoading(true);
    setError(null);
    try {
      // Create timeout signal for long cold start
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/sources-report`,
        { signal: controller.signal }
      );

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setReport(data);
    } catch (err) {
      console.error('Failed to fetch sources report:', err);

      // Better error message for timeout
      if (err.name === 'AbortError') {
        setError('Backend się budzi (cold start). Odśwież stronę za chwilę.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      approved: 'bg-green-100 text-green-800 border-green-300',
      edited: 'bg-blue-100 text-blue-800 border-blue-300',
      rejected: 'bg-red-100 text-red-800 border-red-300',
    };
    const labels = {
      pending: 'Do zatwierdzenia',
      approved: 'Zatwierdzony',
      edited: 'Edytowany',
      rejected: 'Odrzucony',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${badges[status] || 'bg-gray-100 text-gray-800'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const renderTermsList = (terms, emptyMessage) => {
    if (!terms || terms.length === 0) {
      return <p className="text-sm text-gray-500 italic p-4">{emptyMessage}</p>;
    }

    return (
      <div className="divide-y divide-gray-200">
        {terms.map((term, idx) => (
          <div key={idx} className="p-4 hover:bg-gray-50 transition-colors">
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-900">
                    {term.source_term}
                  </span>
                  <span className="text-gray-400">→</span>
                  <span className="text-sm font-medium text-blue-600">
                    {term.target_term || '(brak tłumaczenia)'}
                  </span>
                </div>
                {term.case_name && (
                  <div className="text-xs text-gray-600 mt-1">
                    <span className="font-medium">Wyrok:</span> {term.case_name}
                    {term.case_url && (
                      <a
                        href={term.case_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-blue-600 hover:underline"
                      >
                        [link →]
                      </a>
                    )}
                  </div>
                )}
                {term.context && (
                  <div className="text-xs text-gray-500 mt-1 italic">
                    "{term.context.length > 150 ? term.context.substring(0, 150) + '...' : term.context}"
                  </div>
                )}
              </div>
              <div className="ml-4">
                {getStatusBadge(term.status)}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-sm text-red-800">
          Błąd ładowania raportu źródeł: {error}
        </p>
      </div>
    );
  }

  if (!report) {
    return null;
  }

  const totalTerms = (report.hudoc_terms?.length || 0) +
                     (report.curia_terms?.length || 0) +
                     (report.tm_exact_terms?.length || 0) +
                     (report.tm_fuzzy_terms?.length || 0) +
                     (report.proposed_terms?.length || 0);

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          📊 Raport źródeł terminologii
        </h2>
        <p className="text-sm text-gray-600">
          Łącznie {totalTerms} terminów z różnych źródeł
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-6 bg-gray-50 border-b border-gray-200">
        <div className="text-center">
          <div className="text-2xl font-bold text-gray-900">
            {report.hudoc_terms?.length || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">⚖️ HUDOC</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-gray-900">
            {report.curia_terms?.length || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">🏛️ CURIA</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-700">
            {report.tm_exact_terms?.length || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">✓ TM 100%</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">
            {report.tm_fuzzy_terms?.length || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">≈ TM 95%+</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">
            {report.proposed_terms?.length || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">🤖 AI</div>
        </div>
      </div>

      {/* HUDOC Section */}
      {report.hudoc_terms && report.hudoc_terms.length > 0 && (
        <div className="border-b border-gray-200">
          <button
            onClick={() => toggleSection('hudoc')}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">⚖️</span>
              <div className="text-left">
                <h3 className="font-semibold text-gray-900">
                  HUDOC ({report.hudoc_terms.length})
                </h3>
                <p className="text-xs text-gray-600">
                  Terminy z wyroków Europejskiego Trybunału Praw Człowieka
                </p>
              </div>
            </div>
            <span className="text-gray-400">
              {expandedSections.hudoc ? '▼' : '▶'}
            </span>
          </button>
          {expandedSections.hudoc && renderTermsList(report.hudoc_terms, 'Brak terminów z HUDOC')}
        </div>
      )}

      {/* CURIA Section */}
      {report.curia_terms && report.curia_terms.length > 0 && (
        <div className="border-b border-gray-200">
          <button
            onClick={() => toggleSection('curia')}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">🏛️</span>
              <div className="text-left">
                <h3 className="font-semibold text-gray-900">
                  CURIA ({report.curia_terms.length})
                </h3>
                <p className="text-xs text-gray-600">
                  Terminy z wyroków Trybunału Sprawiedliwości UE
                </p>
              </div>
            </div>
            <span className="text-gray-400">
              {expandedSections.curia ? '▼' : '▶'}
            </span>
          </button>
          {expandedSections.curia && renderTermsList(report.curia_terms, 'Brak terminów z CURIA')}
        </div>
      )}

      {/* Translation Memory Section */}
      {((report.tm_exact_terms && report.tm_exact_terms.length > 0) ||
        (report.tm_fuzzy_terms && report.tm_fuzzy_terms.length > 0)) && (
        <div className="border-b border-gray-200">
          <button
            onClick={() => toggleSection('tm')}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">💾</span>
              <div className="text-left">
                <h3 className="font-semibold text-gray-900">
                  Pamięć tłumaczeniowa ({(report.tm_exact_terms?.length || 0) + (report.tm_fuzzy_terms?.length || 0)})
                </h3>
                <p className="text-xs text-gray-600">
                  Ponownie wykorzystane segmenty z poprzednich tłumaczeń
                </p>
              </div>
            </div>
            <span className="text-gray-400">
              {expandedSections.tm ? '▼' : '▶'}
            </span>
          </button>
          {expandedSections.tm && (
            <div>
              {report.tm_exact_terms && report.tm_exact_terms.length > 0 && (
                <div className="bg-green-50 px-6 py-2">
                  <h4 className="text-sm font-semibold text-green-900 mb-2">
                    ✓ Dokładne dopasowanie 100% ({report.tm_exact_terms.length})
                  </h4>
                  {renderTermsList(report.tm_exact_terms, 'Brak dokładnych dopasowań')}
                </div>
              )}
              {report.tm_fuzzy_terms && report.tm_fuzzy_terms.length > 0 && (
                <div className="bg-green-50 px-6 py-2">
                  <h4 className="text-sm font-semibold text-green-800 mb-2">
                    ≈ Dopasowanie rozmyte 95%+ ({report.tm_fuzzy_terms.length})
                  </h4>
                  {renderTermsList(report.tm_fuzzy_terms, 'Brak rozmytych dopasowań')}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Proposed by AI Section */}
      {report.proposed_terms && report.proposed_terms.length > 0 && (
        <div className="border-b border-gray-200">
          <button
            onClick={() => toggleSection('proposed')}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">🤖</span>
              <div className="text-left">
                <h3 className="font-semibold text-gray-900">
                  Zaproponowane przez AI ({report.proposed_terms.length})
                </h3>
                <p className="text-xs text-gray-600">
                  Terminy wygenerowane przez model tłumaczenia
                </p>
              </div>
            </div>
            <span className="text-gray-400">
              {expandedSections.proposed ? '▼' : '▶'}
            </span>
          </button>
          {expandedSections.proposed && renderTermsList(report.proposed_terms, 'Brak zaproponowanych terminów')}
        </div>
      )}
    </div>
  );
};

export default SourcesReport;
