import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook for managing translation state and WebSocket connection
 */
export const useTranslation = (documentId) => {
  const [document, setDocument] = useState(null);
  const [terms, setTerms] = useState([]);
  const [stats, setStats] = useState(null);
  const [translationStatus, setTranslationStatus] = useState('idle'); // idle, translating, validating, complete, error
  const [progress, setProgress] = useState({ stage: '', progress: 0, message: '' });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [translatedSegments, setTranslatedSegments] = useState([]); // Live segments during translation

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  // Fetch document details
  const fetchDocument = useCallback(async () => {
    try {
      const response = await fetch(`https://ecthr-translator.onrender.com/api/documents/${documentId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch document');
      }
      const data = await response.json();
      setDocument(data);
      setTranslationStatus(data.status || 'idle');
    } catch (err) {
      setError(err.message);
    }
  }, [documentId]);

  // Fetch translation segments
  const fetchSegments = useCallback(async () => {
    try {
      const response = await fetch(`https://ecthr-translator.onrender.com/api/documents/${documentId}/segments`);
      if (!response.ok) {
        throw new Error('Failed to fetch segments');
      }
      const segments = await response.json();

      // Convert to translatedSegments format
      const formattedSegments = segments.map(seg => ({
        index: seg.index,
        source: seg.source_text,
        target: seg.target_text
      }));
      setTranslatedSegments(formattedSegments);
    } catch (err) {
      console.error('Failed to fetch segments:', err);
    }
  }, [documentId]);

  // Fetch glossary terms
  const fetchTerms = useCallback(async () => {
    try {
      const response = await fetch(`https://ecthr-translator.onrender.com/api/glossary/${documentId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch terms');
      }
      const data = await response.json();
      setTerms(data.terms);
      setStats(data.stats);
    } catch (err) {
      console.error('Failed to fetch terms:', err);
    }
  }, [documentId]);

  // Start translation
  const startTranslation = useCallback(async (config = {}) => {
    try {
      setTranslationStatus('translating');
      setError(null);

      const response = await fetch(`https://ecthr-translator.onrender.com/api/translation/${documentId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_mode: config.workflowMode || 'full',
          use_hudoc: config.useHudoc !== false,
          use_curia: config.useCuria !== false,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start translation');
      }

      const data = await response.json();
      return data;
    } catch (err) {
      setError(err.message);
      setTranslationStatus('error');
      throw err;
    }
  }, [documentId]);

  // Finalize translation after validation
  const finalizeTranslation = useCallback(async () => {
    try {
      const response = await fetch(`https://ecthr-translator.onrender.com/api/translation/${documentId}/finalize`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to finalize translation');
      }

      const data = await response.json();
      setTranslationStatus('complete');
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, [documentId]);

  // Update a term
  const updateTerm = useCallback(async (termId, update) => {
    try {
      const response = await fetch(
        `https://ecthr-translator.onrender.com/api/glossary/${documentId}/${termId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(update),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update term');
      }

      const updatedTerm = await response.json();

      // Update local state
      setTerms((prevTerms) =>
        prevTerms.map((term) => (term.id === termId ? updatedTerm : term))
      );

      // Refresh stats
      await fetchTerms();

      return updatedTerm;
    } catch (err) {
      console.error('Failed to update term:', err);
      throw err;
    }
  }, [documentId, fetchTerms]);

  // WebSocket connection
  useEffect(() => {
    if (!documentId) return;

    const connectWebSocket = () => {
      const ws = new WebSocket(`wss://ecthr-translator.onrender.com/ws/${documentId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');

        // If reconnecting during active translation, refresh state from API
        if (translationStatus === 'translating') {
          console.log('Reconnected during translation - refreshing state');
          fetchDocument();
          fetchTerms();
        }

        // Start keepalive ping every 30 seconds
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            console.log('Sending keepalive ping');
            ws.send('ping');
          }
        }, 30000); // 30 seconds
      };

      ws.onmessage = async (event) => {
        try {
          // Ignore keepalive messages (plain text, not JSON)
          if (event.data === 'pong' || event.data === 'keepalive') {
            console.log('Received keepalive:', event.data);
            return;
          }

          const message = JSON.parse(event.data);

          switch (message.type) {
            case 'connected':
              console.log('WebSocket connection confirmed');
              break;

            case 'progress':
              setProgress({
                stage: message.stage,
                progress: message.progress,
                message: message.message,
              });
              break;

            case 'term_update':
              setTerms((prevTerms) =>
                prevTerms.map((term) =>
                  term.id === message.term_id ? message.term : term
                )
              );
              fetchTerms(); // Refresh to update stats
              break;

            case 'segment_translated':
              // Live segment translation update
              setTranslatedSegments((prevSegments) => {
                const newSegments = [...prevSegments];
                newSegments[message.segment_index] = {
                  index: message.segment_index,
                  source: message.source_text,
                  target: message.target_text
                };
                return newSegments;
              });
              setProgress({
                stage: 'translating',
                progress: message.progress,
                message: `Translating segment ${message.segment_index + 1}/${message.total_segments}...`,
              });
              break;

            case 'batch_ready':
              // New batch of terms is ready for validation
              console.log(`Batch ready: ${message.data.terms_count} terms, ${message.data.segments_count} segments`);
              setTranslationStatus('validating'); // Allow user to start validating
              fetchTerms(); // Refresh terms list to show new batch
              fetchSegments(); // Fetch segments to show live preview
              if (!message.data.is_last) {
                setProgress({
                  stage: 'batch_extraction',
                  progress: 0.5,
                  message: `New batch ready! ${message.data.terms_count} terms available. Extraction continues in background...`,
                });
              }
              break;

            case 'translation_complete':
              console.log('Translation complete - fetching segments');
              await fetchDocument();
              await fetchSegments();  // Fetch segments from database
              await fetchTerms();
              break;

            case 'error':
              setError(message.error);
              setTranslationStatus('error');
              break;

            default:
              console.log('Unknown message type:', message.type);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        wsRef.current = null;

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect WebSocket...');
          connectWebSocket();
        }, 3000);
      };
    };

    connectWebSocket();

    // Cleanup
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [documentId, fetchDocument, fetchTerms]);

  // Initial data load
  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      try {
        await Promise.all([fetchDocument(), fetchTerms()]);
      } catch (err) {
        console.error('Failed to load initial data:', err);
      } finally {
        setLoading(false);
      }
    };

    if (documentId) {
      loadInitialData();
    }
  }, [documentId, fetchDocument, fetchTerms]);

  return {
    document,
    terms,
    stats,
    translationStatus,
    progress,
    error,
    loading,
    translatedSegments,
    startTranslation,
    finalizeTranslation,
    updateTerm,
    refreshTerms: fetchTerms,
    refreshDocument: fetchDocument,
  };
};
