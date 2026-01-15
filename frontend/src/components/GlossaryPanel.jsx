import React, { useState, useEffect } from 'react';
import ProgressBar from './ProgressBar';

const GlossaryPanel = ({ documentId, onTermSelect, onApproveAll }) => {
  const [terms, setTerms] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    fetchTerms();
  }, [documentId, filter, currentPage]);

  const fetchTerms = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/glossary/${documentId}?status=${filter}&page=${currentPage}`
      );
      const data = await response.json();
      setTerms(data.terms);
      setStats(data.stats);
    } catch (error) {
      console.error('Failed to fetch terms:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      edited: 'bg-blue-100 text-blue-800',
      rejected: 'bg-red-100 text-red-800',
    };
    return badges[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending: 'Do zatwierdzenia',
      approved: 'Zatwierdzony',
      edited: 'Edytowany',
      rejected: 'Odrzucony',
    };
    return labels[status] || status;
  };

  const handleApproveAll = async () => {
    if (!confirm(`Czy na pewno zatwierdzić wszystkie ${stats?.pending} oczekujące terminy?`)) {
      return;
    }

    try {
      await fetch(`http://localhost:8000/api/glossary/${documentId}/approve-all`, {
        method: 'POST',
      });
      fetchTerms();
      if (onApproveAll) onApproveAll();
    } catch (error) {
      console.error('Failed to approve all terms:', error);
    }
  };

  if (loading && !stats) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header with stats */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            📚 Terminologia ({stats?.total || 0})
          </h2>
          {stats && stats.pending > 0 && (
            <button
              onClick={handleApproveAll}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
            >
              ✓ Zatwierdź wszystkie ({stats.pending})
            </button>
          )}
        </div>

        {stats && (
          <ProgressBar
            current={stats.approved + stats.edited}
            total={stats.total}
            label="Postęp walidacji"
          />
        )}

        {/* Filter tabs */}
        <div className="flex gap-2 mt-4">
          {['all', 'pending', 'approved', 'edited', 'rejected'].map((status) => (
            <button
              key={status}
              onClick={() => {
                setFilter(status);
                setCurrentPage(1);
              }}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                filter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {status === 'all' ? 'Wszystkie' : getStatusLabel(status)}
              {stats && status !== 'all' && ` (${stats[status]})`}
            </button>
          ))}
        </div>
      </div>

      {/* Terms list */}
      <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
        {terms.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {filter === 'all' ? 'Brak terminów' : `Brak terminów z filtrem: ${getStatusLabel(filter)}`}
          </div>
        ) : (
          terms.map((term) => (
            <div
              key={term.id}
              onClick={() => onTermSelect && onTermSelect(term)}
              className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-900">
                      {term.source_term}
                    </span>
                    <span className="text-gray-400">→</span>
                    <span className="text-sm font-medium text-blue-600">
                      {term.target_term}
                    </span>
                  </div>

                  {term.context && (
                    <p className="text-xs text-gray-500 truncate">
                      "{term.context}"
                    </p>
                  )}

                  {term.sources && term.sources.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {term.sources.map((source, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
                        >
                          {source.source_type === 'hudoc' ? '⚖️ HUDOC' : '🏛️ CURIA'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <span className={`ml-4 px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${getStatusBadge(term.status)}`}>
                  {getStatusLabel(term.status)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default GlossaryPanel;
