import React, { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../config';

const TMManager = () => {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Fetch TM list
  const fetchMemories = async () => {
    try {
      setLoading(true);
      const response = await authFetch(`${API_BASE_URL}/tm/list');

      if (!response.ok) {
        throw new Error('Failed to fetch translation memories');
      }

      const data = await response.json();
      setMemories(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching memories:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, []);

  // Upload new TM
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.tmx') && !file.name.endsWith('.tbx')) {
      setError('Only TMX and TBX files are allowed');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('priority', '4'); // Default priority
      formData.append('enabled', 'true');

      const response = await authFetch(`${API_BASE_URL}/tm/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setSuccess(`✓ Successfully uploaded: ${data.name} (${data.entries_count} entries)`);

      // Refresh list
      await fetchMemories();
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      // Reset file input
      e.target.value = '';
    }
  };

  // Toggle enabled/disabled
  const handleToggleEnabled = async (tmName, currentEnabled) => {
    try {
      const endpoint = currentEnabled ? 'disable' : 'enable';
      const response = await fetch(
        `${API_BASE_URL}/tm/${tmName}/${endpoint}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error(`Failed to ${endpoint} TM`);
      }

      setSuccess(`✓ ${currentEnabled ? 'Disabled' : 'Enabled'} TM: ${tmName}`);
      await fetchMemories();
    } catch (err) {
      setError(err.message);
    }
  };

  // Update priority
  const handlePriorityChange = async (tmName, newPriority) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/tm/${tmName}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ priority: parseInt(newPriority) }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update priority');
      }

      setSuccess(`✓ Updated priority for: ${tmName}`);
      await fetchMemories();
    } catch (err) {
      setError(err.message);
    }
  };

  // Download TM
  const handleDownload = async (tmName) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/tm/${tmName}/download`
      );

      if (!response.ok) {
        throw new Error('Failed to download TM');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tmName}.tmx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err.message);
    }
  };

  // Delete TM
  const handleDelete = async (tmName) => {
    if (!confirm(`Are you sure you want to remove TM: ${tmName}?\n\nThe file will be kept on disk.`)) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/tm/${tmName}?delete_file=false`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw new Error('Failed to delete TM');
      }

      setSuccess(`✓ Removed TM: ${tmName}`);
      await fetchMemories();
    } catch (err) {
      setError(err.message);
    }
  };

  // Get priority badge color
  const getPriorityColor = (priority) => {
    const colors = {
      1: 'bg-red-100 text-red-800 border-red-300',
      2: 'bg-orange-100 text-orange-800 border-orange-300',
      3: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      4: 'bg-blue-100 text-blue-800 border-blue-300',
      5: 'bg-gray-100 text-gray-800 border-gray-300',
    };
    return colors[priority] || colors[4];
  };

  // Get priority label
  const getPriorityLabel = (priority) => {
    const labels = {
      1: 'Najwyższy',
      2: 'Wysoki',
      3: 'Średni',
      4: 'Niski',
      5: 'Najniższy',
    };
    return labels[priority] || 'Niski';
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">
          📚 Translation Memory Management
        </h2>
        <div className="text-sm text-gray-600">
          {memories.length} {memories.length === 1 ? 'pamięć' : 'pamięci'}
        </div>
      </div>

      {/* Upload Section */}
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-3">➕ Dodaj nową pamięć tłumaczeniową</h3>
        <div className="flex items-center gap-4">
          <label className="flex-1">
            <input
              type="file"
              accept=".tmx,.tbx"
              onChange={handleUpload}
              disabled={uploading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-600 file:text-white
                hover:file:bg-blue-700
                disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </label>
        </div>
        <p className="mt-2 text-xs text-blue-700">
          Obsługiwane formaty: .tmx, .tbx | Nowa pamięć otrzyma domyślny priorytet 4 (Niski)
        </p>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="mb-4 bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg">
          {success}
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          ❌ {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12 text-gray-500">
          <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mb-2"></div>
          <p>Ładowanie pamięci tłumaczeniowych...</p>
        </div>
      )}

      {/* TM List */}
      {!loading && memories.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg mb-2">Brak załadowanych pamięci tłumaczeniowych</p>
          <p className="text-sm">Dodaj plik TMX lub TBX aby rozpocząć</p>
        </div>
      )}

      {!loading && memories.length > 0 && (
        <div className="space-y-3">
          {memories.map((tm) => (
            <div
              key={tm.name}
              className={`border-2 rounded-lg p-4 transition-all ${
                tm.enabled
                  ? 'border-gray-200 bg-white'
                  : 'border-gray-100 bg-gray-50 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                {/* TM Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-gray-900 truncate">
                      {tm.name}
                    </h3>
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded border ${getPriorityColor(
                        tm.priority
                      )}`}
                    >
                      P{tm.priority}: {getPriorityLabel(tm.priority)}
                    </span>
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded ${
                        tm.enabled
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {tm.enabled ? '✓ Włączona' : '✗ Wyłączona'}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span>📄 {tm.entries_count} wpisów</span>
                    <span className="text-xs truncate" title={tm.file_path}>
                      {tm.file_path.split('/').pop()}
                    </span>
                  </div>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-2">
                  {/* Priority Selector */}
                  <select
                    value={tm.priority}
                    onChange={(e) => handlePriorityChange(tm.name, e.target.value)}
                    className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    title="Zmień priorytet"
                  >
                    <option value="1">P1: Najwyższy</option>
                    <option value="2">P2: Wysoki</option>
                    <option value="3">P3: Średni</option>
                    <option value="4">P4: Niski</option>
                    <option value="5">P5: Najniższy</option>
                  </select>

                  {/* Enable/Disable Toggle */}
                  <button
                    onClick={() => handleToggleEnabled(tm.name, tm.enabled)}
                    className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                      tm.enabled
                        ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                    title={tm.enabled ? 'Wyłącz TM' : 'Włącz TM'}
                  >
                    {tm.enabled ? '⏸ Wyłącz' : '▶ Włącz'}
                  </button>

                  {/* Download Button */}
                  <button
                    onClick={() => handleDownload(tm.name)}
                    className="px-4 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    title="Pobierz TMX"
                  >
                    ⬇ Pobierz
                  </button>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDelete(tm.name)}
                    className="px-4 py-1.5 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    title="Usuń TM"
                  >
                    🗑 Usuń
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Section */}
      <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700">
        <h4 className="font-semibold mb-2">ℹ️ Informacje o priorytetach:</h4>
        <ul className="space-y-1 ml-4 list-disc">
          <li>
            <strong>P1 (Najwyższy):</strong> Terminologia prawnicza, sądowa - używana jako pierwsza
          </li>
          <li>
            <strong>P2 (Wysoki):</strong> Terminologia specyficzna dla ECTHR/CJEU
          </li>
          <li>
            <strong>P3 (Średni):</strong> Terminologia projektowa
          </li>
          <li>
            <strong>P4 (Niski):</strong> Ogólna terminologia
          </li>
          <li>
            <strong>P5 (Najniższy):</strong> Aktualizacje z tłumaczeń (runtime)
          </li>
        </ul>
        <p className="mt-3 text-amber-700">
          <strong>💡 Wskazówka:</strong> System przeszukuje pamięci w kolejności priorytetów. Przy
          dokładnym dopasowaniu wybierany jest wpis z TM o najwyższym priorytecie.
        </p>
      </div>
    </div>
  );
};

export default TMManager;
