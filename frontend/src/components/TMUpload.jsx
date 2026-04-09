import React, { useState } from 'react';
import { API_BASE_URL, authFetch } from '../config';

const TMUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.tmx')) {
      setError('Only TMX files are allowed');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);
    setStats(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await authFetch(`${API_BASE_URL}/tm/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data = await response.json();
      setSuccess(`Uploaded successfully: ${data.entries_loaded} entries loaded`);
      setStats(data.tm_stats);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Translation Memory Upload</h2>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Upload TMX File
        </label>
        <input
          type="file"
          accept=".tmx"
          onChange={handleUpload}
          disabled={uploading}
          className="block w-full text-sm text-gray-500
            file:mr-4 file:py-2 file:px-4
            file:rounded file:border-0
            file:text-sm file:font-semibold
            file:bg-blue-50 file:text-blue-700
            hover:file:bg-blue-100
            disabled:opacity-50"
        />
      </div>

      {uploading && (
        <div className="text-blue-600">
          Uploading...
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
          {success}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {stats && (
        <div className="mt-4 bg-gray-50 p-4 rounded">
          <h3 className="font-semibold mb-2">TM Statistics:</h3>
          <ul className="text-sm space-y-1">
            <li>Total Entries: <span className="font-mono">{stats.total_entries}</span></li>
            {stats.sources && (
              <>
                <li>From TM: <span className="font-mono">{stats.sources.tm || 0}</span></li>
                <li>From HUDOC: <span className="font-mono">{stats.sources.hudoc || 0}</span></li>
                <li>From CURIA: <span className="font-mono">{stats.sources.curia || 0}</span></li>
              </>
            )}
          </ul>
        </div>
      )}

      <div className="mt-6 text-sm text-gray-600">
        <p className="mb-2">
          <strong>Note:</strong> The translation memory will be used to:
        </p>
        <ul className="list-disc list-inside space-y-1">
          <li>Find exact matches for segments during translation</li>
          <li>Suggest terminology for new terms</li>
          <li>Grow automatically with each validated translation</li>
        </ul>
        <p className="mt-4 text-amber-600">
          <strong>⚠️ Remember:</strong> Download the updated TMX after each translation to keep your TM up to date!
        </p>
      </div>
    </div>
  );
};

export default TMUpload;
