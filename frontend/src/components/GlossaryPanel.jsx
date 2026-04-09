import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL, authFetch } from '../config';
import ProgressBar from './ProgressBar';

const GlossaryPanel = ({ documentId, onTermSelect, onApproveAll, refreshTrigger, initialSourceTerm, initialTargetTerm, onTermAdded }) => {
  const [terms, setTerms] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [sessionId, setSessionId] = useState(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const [showSessionInfo, setShowSessionInfo] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'saving', 'saved', 'error'
  const fileInputRef = useRef(null);

  // Modal state for adding manual terms
  const [showAddTermModal, setShowAddTermModal] = useState(false);
  const [newTermSource, setNewTermSource] = useState('');
  const [newTermTarget, setNewTermTarget] = useState('');
  const [newTermContext, setNewTermContext] = useState('');
  const [addingTerm, setAddingTerm] = useState(false);

  // Handle initial term from text selection
  useEffect(() => {
    if (initialSourceTerm || initialTargetTerm) {
      setNewTermSource(initialSourceTerm || '');
      setNewTermTarget(initialTargetTerm || '');
      setShowAddTermModal(true);
    }
  }, [initialSourceTerm, initialTargetTerm]);

  // Load saved session on mount
  useEffect(() => {
    loadSession();
  }, [documentId]);

  // Save session on filter/page change (debounced)
  useEffect(() => {
    if (sessionLoaded) {
      const timeout = setTimeout(() => {
        saveSession();
      }, 1000); // Debounce 1 second
      return () => clearTimeout(timeout);
    }
  }, [filter, currentPage, sessionLoaded]);

  useEffect(() => {
    if (sessionLoaded) {
      fetchTerms();
    }
  }, [documentId, filter, currentPage, refreshTrigger, sessionLoaded]);

  const loadSession = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/sessions/active`
      );
      if (response.ok) {
        const session = await response.json();
        setSessionId(session.id);
        setFilter(session.status_filter || 'all');
        setCurrentPage(session.current_page || 1);
        setShowSessionInfo(true);
        console.log('[GlossaryPanel] Restored session:', session);
      }
    } catch (error) {
      console.log('[GlossaryPanel] No active session, starting fresh');
    }
    setSessionLoaded(true);
  };

  const saveSession = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/sessions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_page: currentPage,
            status_filter: filter,
          }),
        }
      );
      if (response.ok) {
        const session = await response.json();
        setSessionId(session.id);
      }
    } catch (error) {
      console.error('[GlossaryPanel] Failed to save session:', error);
    }
  };

  const completeSession = async () => {
    if (!sessionId) return;
    if (!confirm('Czy zakończyć tę sesję pracy nad glosariuszem?')) return;

    try {
      await fetch(
        `${API_BASE_URL}/glossary/${documentId}/sessions/${sessionId}/complete`,
        { method: 'POST' }
      );
      setSessionId(null);
      setShowSessionInfo(false);
      alert('Sesja została zakończona. Przy następnym wejściu rozpoczniesz od nowa.');
    } catch (error) {
      console.error('[GlossaryPanel] Failed to complete session:', error);
    }
  };

  const fetchTerms = async (retryCount = 0) => {
    setLoading(true);
    try {
      const controller = new AbortController();
      // Increased timeout to 120s for Render Free tier cold start (can take 50-60s)
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}?status=${filter}&page=${currentPage}&per_page=200`,
        { signal: controller.signal }
      );
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('[GlossaryPanel] API Response:', {
        url: `${filter}&page=${currentPage}&per_page=200`,
        stats: data.stats,
        termsCount: data.terms?.length,
        firstTerm: data.terms?.[0]
      });
      setTerms(data.terms);
      setStats(data.stats);
    } catch (error) {
      console.error('Failed to fetch terms:', error);

      // Retry up to 2 times with longer delays for cold start
      if (retryCount < 2 && (error.name === 'AbortError' || error.message.includes('fetch') || error.message.includes('network'))) {
        const delay = retryCount === 0 ? 5000 : 10000; // 5s, then 10s
        console.log(`Retrying terms fetch after backend cold start (attempt ${retryCount + 1}/2)...`);
        setTimeout(() => fetchTerms(retryCount + 1), delay);
      }
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

  // Pobierz stan projektu jako JSON
  const handleDownloadProject = async () => {
    setSaveStatus('saving');
    try {
      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/export/project-state`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Pobierz nazwę pliku z headera lub użyj domyślnej
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `project_state_${documentId}.json`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) filename = match[1];
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      console.error('Failed to download project:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  // Wczytaj stan projektu z JSON
  const handleLoadProject = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setSaveStatus('saving');
    try {
      const text = await file.text();
      const projectState = JSON.parse(text);

      // Walidacja
      if (!projectState.terms || !Array.isArray(projectState.terms)) {
        throw new Error('Nieprawidłowy format pliku');
      }

      // Wyślij do backendu
      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/restore-terms`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(projectState.terms),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      setSaveStatus('saved');
      alert(`Wczytano projekt: ${result.updated} terminow przywroconych`);

      // Odswież liste
      fetchTerms();

      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      console.error('Failed to load project:', error);
      setSaveStatus('error');
      alert(`Blad wczytywania projektu: ${error.message}`);
      setTimeout(() => setSaveStatus(null), 3000);
    }

    // Reset input
    event.target.value = '';
  };

  // Add manual term
  const handleAddManualTerm = async () => {
    if (!newTermSource.trim() || !newTermTarget.trim()) {
      alert('Wypelnij termin zrodlowy i docelowy');
      return;
    }

    setAddingTerm(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/terms`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_term: newTermSource.trim(),
            target_term: newTermTarget.trim(),
            context: newTermContext.trim() || null,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      // Reset form and close modal
      setNewTermSource('');
      setNewTermTarget('');
      setNewTermContext('');
      setShowAddTermModal(false);

      // Refresh terms list
      fetchTerms();

      // Notify parent if callback provided
      if (onTermAdded) onTermAdded();

    } catch (error) {
      console.error('Failed to add term:', error);
      alert(`Blad dodawania terminu: ${error.message}`);
    } finally {
      setAddingTerm(false);
    }
  };

  const handleApproveAll = async () => {
    if (!confirm(`Czy na pewno zatwierdzic wszystkie ${stats?.pending} oczekujace terminy?`)) {
      return;
    }

    try {
      await authFetch(`${API_BASE_URL}/glossary/${documentId}/approve-all`, {
        method: 'POST',
      });
      fetchTerms();
      if (onApproveAll) onApproveAll();
    } catch (error) {
      console.error('Failed to approve all terms:', error);
    }
  };

  const handleQuickAction = async (term, action, e) => {
    e.stopPropagation(); // Prevent opening modal

    try {
      // Create timeout signal for long cold start
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

      const response = await fetch(
        `${API_BASE_URL}/glossary/${documentId}/${term.id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_term: term.target_term,
            status: action, // 'approved' or 'rejected'
          }),
          signal: controller.signal,
        }
      );

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      fetchTerms(); // Refresh list
    } catch (error) {
      console.error(`Failed to ${action} term:`, error);

      // Better error message for timeout/cold start
      if (error.name === 'AbortError') {
        alert(`Backend sie budzi (cold start). Sprobuj ponownie za chwile.`);
      } else {
        alert(`Nie udalo sie ${action === 'approved' ? 'zatwierdzic' : 'odrzucic'} terminu: ${error.message}`);
      }
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
      {/* Session info banner */}
      {showSessionInfo && sessionId && (
        <div className="px-6 py-2 bg-blue-50 border-b border-blue-200 flex items-center justify-between">
          <span className="text-sm text-blue-700">
            Przywrocono poprzednia sesje pracy (strona {currentPage}, filtr: {filter === 'all' ? 'wszystkie' : filter})
          </span>
          <button
            onClick={() => setShowSessionInfo(false)}
            className="text-blue-500 hover:text-blue-700 text-sm"
          >
            x
          </button>
        </div>
      )}

      {/* Header with stats */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Terminologia ({stats?.total || 0})
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Przycisk dodawania terminu */}
            <button
              onClick={() => setShowAddTermModal(true)}
              className="h-9 px-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium flex items-center"
              title="Dodaj nowy termin recznie"
            >
              + Dodaj termin
            </button>

            {/* Przyciski zapisu/wczytania projektu */}
            <button
              onClick={handleDownloadProject}
              disabled={saveStatus === 'saving'}
              className={`h-9 px-3 rounded-lg transition-colors text-sm font-medium flex items-center ${
                saveStatus === 'saved'
                  ? 'bg-green-100 text-green-700'
                  : saveStatus === 'error'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
              }`}
              title="Pobierz stan projektu (JSON)"
            >
              {saveStatus === 'saving' ? 'Zapisuje...' :
               saveStatus === 'saved' ? 'Zapisano!' :
               saveStatus === 'error' ? 'Blad' :
               'Pobierz projekt'}
            </button>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleLoadProject}
              accept=".json"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={saveStatus === 'saving'}
              className="h-9 px-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium flex items-center"
              title="Wczytaj zapisany projekt (JSON)"
            >
              Wczytaj projekt
            </button>

            {sessionId && (
              <button
                onClick={completeSession}
                className="h-9 px-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm font-medium flex items-center"
                title="Zakoncz sesje i zacznij od nowa przy nastepnym wejsciu"
              >
                Zakoncz sesje
              </button>
            )}

            {stats && stats.pending > 0 && (
              <button
                onClick={handleApproveAll}
                className="h-9 px-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium flex items-center"
              >
                Zatwierdz wszystkie ({stats.pending})
              </button>
            )}
          </div>
        </div>

        {stats && (
          <ProgressBar
            current={stats.approved + stats.edited}
            total={stats.total}
            label="Postep walidacji"
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
            {filter === 'all' ? 'Brak terminow' : `Brak terminow z filtrem: ${getStatusLabel(filter)}`}
          </div>
        ) : (
          terms.map((term) => (
            <div
              key={term.id}
              className="p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-900">
                      {term.source_term}
                    </span>
                    <span className="text-gray-400">-&gt;</span>
                    <span className="text-sm font-medium text-blue-600">
                      {term.target_term}
                    </span>
                    {/* Main source type badge */}
                    {term.source_type && (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        term.source_type === 'hudoc' ? 'bg-blue-100 text-blue-800' :
                        term.source_type === 'curia' ? 'bg-indigo-100 text-indigo-800' :
                        term.source_type === 'iate' ? 'bg-purple-100 text-purple-800' :
                        term.source_type === 'tm_exact' ? 'bg-green-100 text-green-800' :
                        term.source_type === 'tm_prefix' ? 'bg-green-100 text-green-800' :
                        term.source_type === 'tm_fuzzy' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {term.source_type === 'hudoc' ? 'HUDOC' :
                         term.source_type === 'curia' ? 'CURIA' :
                         term.source_type === 'iate' ? 'IATE' :
                         term.source_type === 'tm_exact' ? 'TM (100%)' :
                         term.source_type === 'tm_prefix' ? 'TM (prefix)' :
                         term.source_type === 'tm_fuzzy' ? 'TM (fuzzy)' :
                         term.source_type === 'proposed' ? 'Propozycja' :
                         term.source_type}
                      </span>
                    )}
                  </div>

                  {term.context && (
                    <p className="text-xs text-gray-500 truncate">
                      "{term.context}"
                    </p>
                  )}

                  {/* Additional sources from case law research */}
                  {term.sources && term.sources.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      <span className="text-xs text-gray-500 mr-1">Znaleziono tez w:</span>
                      {term.sources.map((source, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                        >
                          {source.source_type === 'hudoc' ? 'HUDOC' :
                           source.source_type === 'curia' ? 'CURIA' :
                           source.source_type === 'iate' ? 'IATE' :
                           source.source_type}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {term.status === 'pending' && (
                    <>
                      <button
                        onClick={(e) => handleQuickAction(term, 'approved', e)}
                        className="px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-xs font-medium"
                        title="Zatwierdz"
                      >
                        OK
                      </button>
                      <button
                        onClick={(e) => handleQuickAction(term, 'rejected', e)}
                        className="px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-xs font-medium"
                        title="Odrzuc"
                      >
                        X
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => onTermSelect && onTermSelect(term)}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-xs font-medium"
                    title="Edytuj"
                  >
                    Edit
                  </button>
                  <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${getStatusBadge(term.status)}`}>
                    {getStatusLabel(term.status)}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination controls */}
      {stats && stats.total > 0 && (
        <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-t border-gray-200">
          <div className="text-sm text-gray-700">
            Pokazuje terminy {(currentPage - 1) * 200 + 1}-{Math.min(currentPage * 200, stats.total)} z {stats.total}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className={`px-3 py-1 rounded text-sm font-medium ${
                currentPage === 1
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              Poprzednia
            </button>
            <span className="px-3 py-1 text-sm font-medium text-gray-700">
              Strona {currentPage} / {Math.ceil(stats.total / 200)}
            </span>
            <button
              onClick={() => setCurrentPage(p => p + 1)}
              disabled={currentPage >= Math.ceil(stats.total / 200)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                currentPage >= Math.ceil(stats.total / 200)
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              Nastepna
            </button>
          </div>
        </div>
      )}

      {/* Modal for adding manual term */}
      {showAddTermModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Dodaj nowy termin
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Termin zrodlowy (EN) *
                </label>
                <input
                  type="text"
                  value={newTermSource}
                  onChange={(e) => setNewTermSource(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="np. applicant"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Termin docelowy (PL) *
                </label>
                <input
                  type="text"
                  value={newTermTarget}
                  onChange={(e) => setNewTermTarget(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="np. skarżący"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Kontekst (opcjonalnie)
                </label>
                <textarea
                  value={newTermContext}
                  onChange={(e) => setNewTermContext(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  rows={2}
                  placeholder="np. zdanie w ktorym wystepuje termin"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowAddTermModal(false);
                  setNewTermSource('');
                  setNewTermTarget('');
                  setNewTermContext('');
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                disabled={addingTerm}
              >
                Anuluj
              </button>
              <button
                onClick={handleAddManualTerm}
                disabled={addingTerm || !newTermSource.trim() || !newTermTarget.trim()}
                className={`px-4 py-2 text-white rounded-lg transition-colors ${
                  addingTerm || !newTermSource.trim() || !newTermTarget.trim()
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-purple-600 hover:bg-purple-700'
                }`}
              >
                {addingTerm ? 'Dodawanie...' : 'Dodaj termin'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GlossaryPanel;
