import React from 'react';

const DebugInfo = ({ quiz, attempts, loading }) => {
  return (
    <div className="card p-4 bg-yellow-50 border border-yellow-200">
      <h3 className="font-semibold text-yellow-800 mb-2">Debug Information</h3>
      <div className="text-sm text-yellow-700 space-y-1">
        <div><strong>Quiz ID:</strong> {quiz?.id}</div>
        <div><strong>Quiz Title:</strong> {quiz?.title}</div>
        <div><strong>Loading:</strong> {loading ? 'Yes' : 'No'}</div>
        <div><strong>Attempts Count:</strong> {attempts?.length || 0}</div>
        <div><strong>Quiz Data:</strong> {JSON.stringify(quiz, null, 2)}</div>
        <div><strong>Attempts Data:</strong> {JSON.stringify(attempts, null, 2)}</div>
      </div>
    </div>
  );
};

export default DebugInfo;