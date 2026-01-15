import React from 'react';
import { useParams } from 'react-router-dom';

const TranslationPage = () => {
  const { documentId } = useParams();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            ⚖️ ECTHR Translator
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-12">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            Translation in progress
          </h2>
          <p className="text-gray-600">
            Document ID: {documentId}
          </p>
          <p className="text-sm text-gray-500 mt-4">
            Full translation UI will be implemented in Sprint 4
          </p>
        </div>
      </main>
    </div>
  );
};

export default TranslationPage;
