import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileUpload from '../components/FileUpload';
import TMUpload from '../components/TMUpload';

const HomePage = () => {
  const navigate = useNavigate();
  const [config, setConfig] = useState({
    useHudoc: true,
    useCuria: true,
  });

  const handleUploadSuccess = (data) => {
    console.log('Upload successful:', data);
    // Navigate to translation page (will be implemented in Sprint 4)
    navigate(`/translation/${data.id}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            ⚖️ ECTHR Translator
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-12">
        <div className="space-y-8">
          {/* Translation Memory Upload */}
          <TMUpload />

          {/* File Upload */}
          <FileUpload onUploadSuccess={handleUploadSuccess} />

          {/* Configuration */}
          <div className="max-w-2xl mx-auto bg-white rounded-lg shadow p-6 space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">
                  Kierunek
                </span>
                <select
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-600 focus:border-transparent"
                  defaultValue="EN-PL"
                >
                  <option value="EN-PL">English → Polski</option>
                </select>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.useHudoc}
                  onChange={(e) => setConfig({ ...config, useHudoc: e.target.checked })}
                  className="w-5 h-5 text-primary-600 rounded focus:ring-primary-600"
                />
                <span className="text-sm text-gray-700">
                  Przeszukuj HUDOC
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.useCuria}
                  onChange={(e) => setConfig({ ...config, useCuria: e.target.checked })}
                  className="w-5 h-5 text-primary-600 rounded focus:ring-primary-600"
                />
                <span className="text-sm text-gray-700">
                  Przeszukuj CURIA
                </span>
              </label>
            </div>
          </div>

          {/* Recent Documents (placeholder for Sprint 4) */}
          <div className="max-w-2xl mx-auto">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              📚 Ostatnie dokumenty
            </h2>
            <div className="bg-white rounded-lg shadow divide-y">
              <div className="p-4 text-center text-gray-500">
                Brak ostatnich dokumentów
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default HomePage;
